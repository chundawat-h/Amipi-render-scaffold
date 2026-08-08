from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, ForeignKey, Text, DateTime, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    sku = Column(String(64), unique=True, nullable=False, index=True)
    stone_count = Column(Integer)
    stone_size_ct = Column(Numeric(6, 3))
    dimensions_mm = Column(String(64))
    ring_size = Column(String(16))
    metal_type = Column(String(32))  # internal_only — exclude from technical-image queries
    category = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    jobs = relationship("RenderJob", back_populates="product")


class RenderTemplate(Base):
    __tablename__ = "render_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    config = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RenderJob(Base):
    __tablename__ = "render_jobs"
    __table_args__ = (
        CheckConstraint("input_type in ('cad','stl','obj','jpeg')", name="ck_input_type"),
        CheckConstraint("pipeline in ('render_3d','normalize_2d')", name="ck_pipeline"),
        CheckConstraint("status in ('queued','processing','done','failed')", name="ck_status"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))
    input_type = Column(String(16), nullable=False)
    input_path = Column(Text, nullable=False)
    pipeline = Column(String(16), nullable=False)
    template_id = Column(Integer, ForeignKey("render_templates.id"))
    status = Column(String(16), nullable=False, default="queued")
    error_message = Column(Text)
    output_paths = Column(JSONB)
    requested_by = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="jobs")
    template = relationship("RenderTemplate")
