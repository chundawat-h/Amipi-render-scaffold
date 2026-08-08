import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=schemas.ProductOut)
def create_product(payload: schemas.ProductIn, db: Session = Depends(get_db)):
    existing = db.query(models.Product).filter_by(sku=payload.sku).first()
    if existing:
        raise HTTPException(409, f"SKU {payload.sku} already exists")
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{sku}", response_model=schemas.ProductOut)
def get_product(sku: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter_by(sku=sku).first()
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@router.get("/{sku}/public", response_model=schemas.ProductPublicOut)
def get_product_public(sku: str, db: Session = Depends(get_db)):
    """What the technical-image generator / any external-facing view is
    allowed to see. metal_type never leaves this endpoint."""
    product = db.query(models.Product).filter_by(sku=sku).first()
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@router.post("/import")
async def import_from_erp_sheet(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk-import product metadata from the ERP Excel export (style number,
    stone count, etc.). Expected columns (case-insensitive, order doesn't
    matter): sku, stone_count, stone_size_ct, dimensions_mm, ring_size,
    metal_type, category. Unknown columns are ignored; missing optional
    columns are left null. Adjust `column_map` below once you confirm the
    exact ERP export header names.
    """
    contents = await file.read()
    ext = file.filename.lower().rsplit(".", 1)[-1]
    df = pd.read_excel(io.BytesIO(contents)) if ext in ("xlsx", "xls") else pd.read_csv(io.BytesIO(contents))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    column_map = {
        "style_no": "sku", "style_number": "sku", "sku": "sku",
        "stone_count": "stone_count", "no_of_stones": "stone_count",
        "stone_size_ct": "stone_size_ct", "carat": "stone_size_ct",
        "dimensions_mm": "dimensions_mm", "dimensions": "dimensions_mm",
        "ring_size": "ring_size", "size": "ring_size",
        "metal_type": "metal_type", "metal": "metal_type",
        "category": "category",
    }
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    if "sku" not in df.columns:
        raise HTTPException(400, "Import file must contain a SKU / Style No. column")

    created, updated = 0, 0
    for _, row in df.iterrows():
        sku = str(row["sku"]).strip()
        if not sku or sku.lower() == "nan":
            continue
        existing = db.query(models.Product).filter_by(sku=sku).first()
        fields = {
            col: (None if pd.isna(row.get(col)) else row.get(col))
            for col in ("stone_count", "stone_size_ct", "dimensions_mm", "ring_size", "metal_type", "category")
            if col in df.columns
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(models.Product(sku=sku, **fields))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "rows_processed": len(df)}
