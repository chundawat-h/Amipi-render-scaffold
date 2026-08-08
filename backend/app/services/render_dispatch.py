"""
Dispatches a queued RenderJob to the right pipeline:
  - cad/stl/obj  -> Path A: headless Blender render (render_engine/blender_render.py)
  - jpeg         -> Path B: background removal + recomposition (services/image_normalize.py)

Runs as a FastAPI BackgroundTask at MVP scale. If throughput grows past what a
single worker process can keep up with, swap this call site for an RQ/Celery
enqueue — the function signature doesn't need to change.
"""
import json
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.services.image_normalize import normalize_existing_image
from app.services.technical_image import build_technical_image

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BLENDER_SCRIPT = BASE_DIR / "render_engine" / "blender_render.py"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"


def run_job(job_id: int, db: Session):
    job = db.get(models.RenderJob, job_id)
    if job is None:
        return

    job.status = "processing"
    db.commit()

    try:
        template = db.get(models.RenderTemplate, job.template_id)
        product = db.get(models.Product, job.product_id) if job.product_id else None
        job_out_dir = OUTPUT_DIR / f"job_{job.id}"
        job_out_dir.mkdir(parents=True, exist_ok=True)

        if job.pipeline == "render_3d":
            outputs = _run_blender(job.input_path, template.config, job_out_dir)
        else:
            outputs = normalize_existing_image(job.input_path, template.config, job_out_dir)

        if product is not None:
            outputs["technical"] = str(
                build_technical_image(outputs["hero"], product, job_out_dir)
            )

        job.output_paths = {k: str(v) for k, v in outputs.items()}
        job.status = "done"

    except Exception as exc:  # noqa: BLE001 — surface any failure back to the job row
        job.status = "failed"
        job.error_message = str(exc)

    db.commit()


def _run_blender(input_path: str, template_config: dict, out_dir: Path) -> dict:
    """Shells out to headless Blender. Requires `blender` on PATH (free install,
    no license). Keeping this as a subprocess call (rather than importing bpy
    directly) means the FastAPI process never needs Blender's Python env."""
    config_path = out_dir / "template_config.json"
    config_path.write_text(json.dumps(template_config))

    cmd = [
        "blender", "--background", "--python", str(BLENDER_SCRIPT), "--",
        "--input", input_path,
        "--config", str(config_path),
        "--outdir", str(out_dir),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Blender render failed: {result.stderr[-2000:]}")

    return {
        "hero": out_dir / "hero.png",
        "thumbnail": out_dir / "thumbnail.png",
    }
