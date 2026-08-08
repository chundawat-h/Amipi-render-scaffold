"""
Generates the optional "technical image" variant: the clean hero render plus
a spec overlay pulled straight from the products table. `metal_type` is
never read here on purpose — this function's input type doesn't even carry
it (see ProductPublicOut in schemas.py), so leaving it out isn't something
a future edit can accidentally undo without touching the type first.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app import models


def build_technical_image(hero_path: str, product: models.Product, out_dir: Path) -> Path:
    img = Image.open(hero_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size=max(18, img.width // 45))
    except OSError:
        font = ImageFont.load_default()

    lines = [f"SKU: {product.sku}"]
    if product.stone_count is not None:
        lines.append(f"Stone Count: {product.stone_count}")
    if product.stone_size_ct is not None:
        lines.append(f"Stone Size: {product.stone_size_ct} ct")
    if product.dimensions_mm:
        lines.append(f"Dimensions: {product.dimensions_mm}")
    if product.ring_size:
        lines.append(f"Size: {product.ring_size}")
    # metal_type intentionally omitted — not read from `product` above

    padding = 16
    line_height = font.size + 6
    box_height = padding * 2 + line_height * len(lines)
    box_width = int(img.width * 0.42)

    overlay = Image.new("RGBA", (box_width, box_height), (255, 255, 255, 235))
    odraw = ImageDraw.Draw(overlay)
    for i, line in enumerate(lines):
        odraw.text((padding, padding + i * line_height), line, fill=(20, 20, 20), font=font)

    img.paste(overlay, (16, img.height - box_height - 16), overlay)

    out_path = out_dir / "technical.png"
    img.save(out_path)
    return out_path
