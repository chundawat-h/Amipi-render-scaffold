import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # reads .env from CWD (backend/) — no-op if file doesn't exist

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import products, jobs

# Ensure storage dirs exist before anything tries to use them
_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "storage/outputs"))
_UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/uploads"))
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

try:
    Base.metadata.create_all(bind=engine)  # move to Alembic migrations once schema stabilizes

    # Auto-seed the default render template if none exists
    from app.database import SessionLocal
    from app import models
    _seed_db = SessionLocal()
    try:
        if _seed_db.query(models.RenderTemplate).count() == 0:
            _seed_db.add(models.RenderTemplate(
                name="AMIPI Standard",
                version=1,
                is_active=True,
                config={
                    "camera": {
                        "views": ["hero_3quarter", "front", "top"],
                        "focal_length_mm": 85,
                        "distance_factor": 2.2
                    },
                    "lighting": {
                        "type": "studio_hdri",
                        "hdri": "studio_soft_01",
                        "key_intensity": 1.0,
                        "fill_intensity": 0.4,
                        "rim_intensity": 0.6
                    },
                    "background": {
                        "type": "gradient",
                        "color_top": "#FFFFFF",
                        "color_bottom": "#F2EFEA"
                    },
                    "output_sizes": {
                        "hero": [2000, 2000],
                        "thumbnail": [800, 800],
                        "technical": [1600, 1600]
                    },
                    "watermark": {
                        "logo_path": "assets/amipi_logo.png",
                        "position": "bottom_right",
                        "margin_px": 24
                    }
                }
            ))
            _seed_db.commit()
            print("[INFO] Seeded default render template: AMIPI Standard v1")
    finally:
        _seed_db.close()

except Exception as _db_err:
    print(f"[WARN] Could not connect to database on startup: {_db_err}")
    print("[WARN] Start the Postgres container: docker compose up -d db")

_env = os.getenv("APP_ENV", "development").lower()

app = FastAPI(
    title="AMIPI Rendering Standardization API",
    # Hide interactive docs in production — set APP_ENV=production in .env
    docs_url="/docs" if _env != "production" else None,
    redoc_url="/redoc" if _env != "production" else None,
)

# CORS — read from env, fall back to localhost dev server
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(jobs.router)
app.mount(
    "/outputs",
    StaticFiles(directory=str(_OUTPUT_DIR)),
    name="outputs",
)


@app.get("/health")
def health():
    return {"status": "ok", "env": _env}
