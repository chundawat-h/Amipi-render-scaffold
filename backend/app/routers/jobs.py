import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.render_dispatch import run_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

_DEFAULT_UPLOAD = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_DEFAULT_UPLOAD)))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INPUT_TYPE_BY_EXT = {
    ".stl": ("stl", "render_3d"),
    ".obj": ("obj", "render_3d"),
    ".3dm": ("cad", "render_3d"),   # note: only true if it's an actual mesh export, not a screenshot
    ".jpg": ("jpeg", "normalize_2d"),
    ".jpeg": ("jpeg", "normalize_2d"),
    ".png": ("jpeg", "normalize_2d"),
}


@router.post("", response_model=schemas.RenderJobOut)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sku: str | None = Form(None),
    requested_by: str | None = Form(None),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in INPUT_TYPE_BY_EXT:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    input_type, pipeline = INPUT_TYPE_BY_EXT[ext]

    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    product = db.query(models.Product).filter_by(sku=sku).first() if sku else None
    active_template = db.query(models.RenderTemplate).filter_by(is_active=True).first()
    if active_template is None:
        raise HTTPException(500, "No active render template configured — seed schema.sql first")

    job = models.RenderJob(
        product_id=product.id if product else None,
        input_type=input_type,
        input_path=str(dest),
        pipeline=pipeline,
        template_id=active_template.id,
        status="queued",
        requested_by=requested_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_job, job.id, db)
    return job


@router.get("/{job_id}", response_model=schemas.RenderJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("", response_model=list[schemas.RenderJobOut])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.RenderJob)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(models.RenderJob.created_at.desc()).limit(200).all()
