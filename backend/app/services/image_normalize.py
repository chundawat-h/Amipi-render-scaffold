"""
Path B: for products where no 3D mesh exists — only a flattened photo or
vendor render (JPEG/PNG). Standardizes background, framing, and exposure.

AMIPI output spec implemented here:
  - Canvas:    2000×2000 px, 1:1 square
  - Product:   65% of canvas (55–70% per spec), centered, slightly above middle
  - Margin:    140 px safe zone from edges
  - Shadow:    Very soft contact shadow ellipse under the product
  - Master:    PNG at 300 DPI (sRGB)
  - Delivery:  JPG at 92 quality, 72 DPI (screen-optimised)

Note: a JPEG-in pipeline is a ceiling on quality — it can clean up framing,
it cannot recover missing detail. Any product only available as a photo should
be flagged for a proper CAD/STL re-render when possible.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def normalize_existing_image(input_path: str, template_config: dict, out_dir: Path) -> dict:
    # Lazy-import rembg so that onnxruntime doesn't block server startup
    from rembg import remove, new_session

    src = Image.open(input_path).convert("RGBA")

    # 1. Remove existing (often dark / inconsistent) background
    # Use the lightweight 'u2netp' model (~4MB) instead of default 'u2net' (~170MB)
    # This prevents Out-Of-Memory (OOM) crashes on Render's 512MB RAM free tier.
    session = new_session("u2netp")
    cutout = remove(src, session=session)

    # 2. Canvas + background colour
    bg_cfg = template_config.get("background", {})
    bg_hex = bg_cfg.get("color_top", "#FAFAF8").lstrip("#")
    bg_rgb = tuple(int(bg_hex[i:i + 2], 16) for i in (0, 2, 4))
    hero_size = tuple(template_config["output_sizes"]["hero"])   # (2000, 2000)

    canvas = Image.new("RGBA", hero_size, (*bg_rgb, 255))

    # 3. Scale product to 65% of canvas (AMIPI spec: 55–70%)
    framing = template_config.get("framing", {})
    product_pct = framing.get("product_size_pct", 0.65)
    safe_margin = framing.get("safe_margin_px", 140)
    v_offset_pct = framing.get("vertical_offset_pct", -0.03)  # negative = above center

    max_dim = int(min(hero_size) * product_pct)
    cutout = cutout.copy()
    cutout.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    # 4. Position: centered horizontally, slightly above center vertically
    paste_x = (hero_size[0] - cutout.width) // 2
    paste_y = int(hero_size[1] * (0.5 + v_offset_pct)) - cutout.height // 2
    # Enforce safe margins
    paste_x = max(safe_margin, min(paste_x, hero_size[0] - cutout.width - safe_margin))
    paste_y = max(safe_margin, min(paste_y, hero_size[1] - cutout.height - safe_margin))

    # 5. Very soft contact shadow — ellipse at the base of the product, heavily blurred
    shadow = Image.new("RGBA", hero_size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sw = int(cutout.width * 0.72)                     # narrower than the product
    sh = max(12, int(hero_size[1] * 0.018))           # thin ellipse
    sx0 = paste_x + (cutout.width - sw) // 2
    sy0 = paste_y + cutout.height - sh // 2
    sdraw.ellipse([sx0, sy0, sx0 + sw, sy0 + sh], fill=(15, 12, 8, 75))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=28))
    canvas.paste(shadow, (0, 0), shadow)

    # 6. Composite product onto canvas
    canvas.paste(cutout, (paste_x, paste_y), cutout)

    # 7. Subtle exposure / contrast normalisation
    flat = canvas.convert("RGB")
    flat = ImageEnhance.Brightness(flat).enhance(1.04)
    flat = ImageEnhance.Contrast(flat).enhance(1.06)
    flat = ImageEnhance.Sharpness(flat).enhance(1.18)

    # 8. PNG master at 300 DPI (sRGB — Pillow default colour space)
    hero_path = out_dir / "hero.png"
    flat.save(str(hero_path), dpi=(300, 300))

    # 9. JPG delivery copy (screen-optimised, 72 DPI)
    jpg_path = out_dir / "hero_delivery.jpg"
    flat.convert("RGB").save(str(jpg_path), "JPEG", quality=92, dpi=(72, 72))

    # 10. Thumbnail (800×800 by default)
    thumb_size = tuple(template_config["output_sizes"]["thumbnail"])
    thumb = flat.copy()
    thumb.thumbnail(thumb_size, Image.Resampling.LANCZOS)
    thumb_path = out_dir / "thumbnail.png"
    thumb.save(str(thumb_path), dpi=(72, 72))

    return {"hero": hero_path, "thumbnail": thumb_path, "delivery": jpg_path}
