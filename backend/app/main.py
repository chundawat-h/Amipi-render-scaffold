from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import products, jobs

Base.metadata.create_all(bind=engine)  # fine for MVP; move to Alembic migrations once schema stabilizes

app = FastAPI(title="AMIPI Rendering Standardization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the frontend's real origin before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(jobs.router)
app.mount("/outputs", StaticFiles(directory="storage/outputs"), name="outputs")


@app.get("/health")
def health():
    return {"status": "ok"}
