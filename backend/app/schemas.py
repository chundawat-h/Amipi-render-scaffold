from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class ProductIn(BaseModel):
    sku: str
    stone_count: Optional[int] = None
    stone_size_ct: Optional[Decimal] = None
    dimensions_mm: Optional[str] = None
    ring_size: Optional[str] = None
    metal_type: Optional[str] = None  # stored, but never returned by the technical-image endpoint
    category: Optional[str] = None


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ProductPublicOut(BaseModel):
    """What the technical-image / customer-facing spec sheet is allowed to see.
    Deliberately excludes metal_type."""
    model_config = ConfigDict(from_attributes=True)
    sku: str
    stone_count: Optional[int] = None
    stone_size_ct: Optional[Decimal] = None
    dimensions_mm: Optional[str] = None
    ring_size: Optional[str] = None


class RenderJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: Optional[int]
    input_type: str
    pipeline: str
    status: str
    error_message: Optional[str] = None
    output_paths: Optional[dict[str, Any]] = None
    requested_by: Optional[str] = None
    created_at: datetime


class RenderTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    version: int
    is_active: bool
    config: dict[str, Any]
