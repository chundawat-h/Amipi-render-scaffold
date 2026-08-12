"""
Dispatches a queued RenderJob to the right pipeline:
  - cad/stl/obj  -> Path A: headless Blender render (render_engine/blender_render.py)
  - jpeg         -> Path B: background removal + recomposition (services/image_normalize.py)

Runs as a FastAPI BackgroundTask at MVP scale. If throughput grows, swap this
call site for an RQ/Celery enqueue — the function signature stays the same.
"""
import json
import os
import subprocess
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app import models
from app.services.image_normalize import normalize_existing_image
from app.services.technical_image import build_technical_image

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BLENDER_SCRIPT = BASE_DIR / "render_engine" / "blender_render.py"

# --- env-configurable values (all set in .env) ---
_DEFAULT_OUTPUT = BASE_DIR / "storage" / "outputs"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(_DEFAULT_OUTPUT)))
BLENDER_EXECUTABLE = os.getenv("BLENDER_EXECUTABLE", "blender")
BLENDER_TIMEOUT = int(os.getenv("BLENDER_TIMEOUT", "600"))


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
            metal = (product.metal_type or "gold") if product else "gold"
            outputs = _run_blender(job.input_path, template.config, job_out_dir, metal=metal)
        else:
            outputs = normalize_existing_image(job.input_path, template.config, job_out_dir)

        if product is not None:
            # build_technical_image needs the filesystem hero path — pass it before URL conversion
            tech_path = build_technical_image(str(outputs["hero"]), product, job_out_dir)
            outputs["technical"] = tech_path

        # Convert all absolute filesystem paths → URL paths served by /outputs static mount
        job.output_paths = {k: _to_url_path(v, OUTPUT_DIR) for k, v in outputs.items()}
        job.status = "done"

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(exc)

    db.commit()


def _to_url_path(file_path, output_root: Path) -> str:
    """Convert an absolute output path to a URL path served by the /outputs static mount.
    e.g. /abs/path/storage/outputs/job_1/hero.png  →  /outputs/job_1/hero.png
    """
    return "/outputs/" + Path(str(file_path)).relative_to(output_root).as_posix()



def _run_blender(input_path: str, template_config: dict, out_dir: Path, metal: str = "gold") -> dict:
    """Shells out to headless Blender. Requires BLENDER_EXECUTABLE on PATH (or set in .env).
    Keeps this as a subprocess call so FastAPI never needs Blender's Python env."""
    config_path = out_dir / "template_config.json"
    config_path.write_text(json.dumps(template_config))

    cmd = [
        BLENDER_EXECUTABLE, "--background", "--python", str(BLENDER_SCRIPT), "--",
        "--input", input_path,
        "--config", str(config_path),
        "--outdir", str(out_dir),
        "--metal", metal,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=BLENDER_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"Blender render failed:\n{result.stderr[-2000:]}")

    # Collect all rendered view files the script produced
    views = template_config.get("camera", {}).get("views", ["hero_3quarter"])
    outputs: dict = {}
    for view in views:
        p = out_dir / f"{view}.png"
        if p.exists():
            outputs[view] = p

    # "hero" key is always required (technical image + job schema both reference it)
    if "hero_3quarter" in outputs:
        outputs["hero"] = outputs["hero_3quarter"]
    elif outputs:
        outputs["hero"] = next(iter(outputs.values()))

    # Generate thumbnail via Pillow from the hero — no need for a second full render
    hero_path = outputs.get("hero")
    if hero_path and Path(hero_path).exists():
        thumb_size = tuple(template_config.get("output_sizes", {}).get("thumbnail", [800, 800]))
        thumb_path = out_dir / "thumbnail.png"
        with Image.open(str(hero_path)) as img:
            thumb = img.copy()
            thumb.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            thumb.save(str(thumb_path))
        outputs["thumbnail"] = thumb_path

    return outputs
