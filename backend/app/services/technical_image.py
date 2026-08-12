"""
Generates the "technical image" variant: the clean hero render with a spec
overlay pulled from the products table, per AMIPI presentation spec:

  - SKU / product code:  Large, immediately readable (primary identifier)
  - Stone specs:         Medium weight, secondary
  - Dimensions / size:  Smaller, supporting detail
  - Logo slot:          Small and understated, right-aligned

Layout: full-width bar at the bottom of the image, warm-white semi-transparent
background. Saves as PNG at 300 DPI to match the hero master.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app import models

# Fallback font stack — tries system fonts before PIL's built-in bitmap default
_FONT_STACK = [
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
    "arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONT_STACK:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_technical_image(hero_path: str, product: models.Product, out_dir: Path) -> Path:
    img = Image.open(hero_path).convert("RGB")
    w, h = img.size

    # --- Typography scale (relative to image width) ---
    sz_sku   = max(36, w // 44)   # Large — primary identifier
    sz_specs = max(24, w // 64)   # Medium — stone specs
    sz_small = max(18, w // 82)   # Small  — dimensions / ring size
    sz_label = max(14, w // 100)  # Tiny   — field labels

    font_sku   = _load_font(sz_sku)
    font_specs = _load_font(sz_specs)
    font_small = _load_font(sz_small)
    font_label = _load_font(sz_label)

    # --- Collect spec lines ---
    stone_parts = []
    if product.stone_count is not None:
        stone_parts.append(f"{product.stone_count}×")
    if product.stone_size_ct is not None:
        stone_parts.append(f"{product.stone_size_ct} ct")
    stone_line = "  ".join(stone_parts) if stone_parts else None

    dim_parts = []
    if product.dimensions_mm:
        dim_parts.append(product.dimensions_mm)
    if product.ring_size:
        dim_parts.append(f"Size {product.ring_size}")
    dim_line = "  ·  ".join(dim_parts) if dim_parts else None

    # --- Measure bar height ---
    pad = max(20, w // 60)
    row_gap = max(6, w // 220)
    bar_height = pad * 2 + sz_sku + row_gap
    if stone_line:
        bar_height += sz_specs + row_gap
    if dim_line:
        bar_height += sz_small + row_gap

    # --- Draw overlay bar ---
    overlay = Image.new("RGBA", (w, bar_height), (252, 250, 247, 230))  # warm white, 90% opacity
    odraw = ImageDraw.Draw(overlay)

    # Thin top divider line
    odraw.line([(0, 0), (w, 0)], fill=(180, 170, 160, 200), width=1)

    ink = (22, 18, 14)          # near-black text
    muted = (110, 100, 90)      # muted label colour
    y = pad

    # SKU — large primary identifier
    odraw.text((pad, y), product.sku, fill=ink, font=font_sku)
    # Metal type label — small, right of SKU, vertically centered on the SKU row
    if product.metal_type:
        mt_label = product.metal_type.replace("_", " ").upper()
        odraw.text((pad, y + sz_sku - sz_label - 2), mt_label, fill=muted, font=font_label)
    y += sz_sku + row_gap * 2

    # Stone specs — medium
    if stone_line:
        odraw.text((pad, y), stone_line, fill=ink, font=font_specs)
        y += sz_specs + row_gap

    # Dimensions / ring size — small
    if dim_line:
        odraw.text((pad, y), dim_line, fill=muted, font=font_small)

    # Logo slot — small placeholder text right-aligned, vertically centered in bar
    logo_text = "AMIPI"
    logo_bbox = odraw.textbbox((0, 0), logo_text, font=font_small)
    logo_w = logo_bbox[2] - logo_bbox[0]
    odraw.text((w - pad - logo_w, pad), logo_text, fill=(160, 148, 130), font=font_small)

    # --- Composite onto image ---
    bar_y = h - bar_height
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, bar_y), overlay)
    result = img_rgba.convert("RGB")

    out_path = out_dir / "technical.png"
    result.save(str(out_path), dpi=(300, 300))
    return out_path
