"""
Path B: for products where no 3D mesh exists — only a flattened photo or
vendor render (JPEG/PNG). We can't relight or re-angle baked-in geometry,
so this pipeline standardizes what CAN be controlled: background, framing,
and exposure/color, using `rembg` (free, open-source, no API cost).

This directly targets the "dark background / blurry / inconsistent" issues
called out — note that a JPEG-in pipeline is a ceiling on quality: it can
clean up framing, it cannot recover missing detail. Any product only
available as a photo like this should be flagged for a proper CAD/STL
re-render when possible (see `pipeline` field on the job — "normalize_2d"
outputs are visually tagged as such downstream).
"""
from pathlib import Path
from PIL import Image, ImageEnhance
from rembg import remove


def normalize_existing_image(input_path: str, template_config: dict, out_dir: Path) -> dict:
    src = Image.open(input_path).convert("RGBA")

    # 1. Remove existing (often dark/inconsistent) background
    cutout = remove(src)

    # 2. Composite onto the standard brand background from the active template
    bg_hex = template_config["background"].get("color_top", "#FFFFFF").lstrip("#")
    bg_rgb = tuple(int(bg_hex[i:i + 2], 16) for i in (0, 2, 4))
    hero_size = tuple(template_config["output_sizes"]["hero"])

    canvas = Image.new("RGBA", hero_size, (*bg_rgb, 255))
    cutout.thumbnail((int(hero_size[0] * 0.8), int(hero_size[1] * 0.8)))
    paste_pos = (
        (hero_size[0] - cutout.width) // 2,
        (hero_size[1] - cutout.height) // 2,
    )
    canvas.paste(cutout, paste_pos, cutout)

    # 3. Basic exposure/contrast normalization — fixes the "some are blurry
    #    or too dark" complaint without pretending to add detail that isn't there
    flat = canvas.convert("RGB")
    flat = ImageEnhance.Brightness(flat).enhance(1.08)
    flat = ImageEnhance.Contrast(flat).enhance(1.05)
    flat = ImageEnhance.Sharpness(flat).enhance(1.15)

    hero_path = out_dir / "hero.png"
    flat.save(hero_path)

    thumb_size = tuple(template_config["output_sizes"]["thumbnail"])
    thumb = flat.copy()
    thumb.thumbnail(thumb_size)
    thumb_path = out_dir / "thumbnail.png"
    thumb.save(thumb_path)

    return {"hero": hero_path, "thumbnail": thumb_path}
