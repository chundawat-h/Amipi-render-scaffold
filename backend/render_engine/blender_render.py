"""
Headless Blender render script — the automated half of the "documented
rendering guideline." It reads a template_config.json (camera/lighting/
background/output-size settings, sourced from the render_templates table)
and applies it identically to every product, so consistency isn't a matter
of who's operating Blender that day — there's no one operating it.

Run via:
    blender --background --python blender_render.py -- \
        --input path/to/model.stl --config path/to/config.json --outdir path/to/out

Requires Blender (free, https://www.blender.org) — no license cost.
Materials/lighting/camera setup below are a starting skeleton: swap in real
metal PBR node graphs and an actual studio HDRI file once the guideline is
validated with AMIPI (the config schema already has the hooks for it).
"""
import bpy
import json
import sys
import os
from pathlib import Path
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    args = {}
    for i in range(0, len(argv), 2):
        args[argv[i].lstrip("-")] = argv[i + 1]
    return args


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_model(path: str):
    ext = Path(path).suffix.lower()
    if ext == ".stl":
        bpy.ops.import_mesh.stl(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f"Unsupported 3D input type: {ext}")
    return bpy.context.selected_objects[0]


def frame_and_scale(obj, target_size=2.0):
    """Normalize scale so every product fills the frame consistently,
    regardless of how large the source mesh's native units are."""
    dims = obj.dimensions
    max_dim = max(dims.x, dims.y, dims.z) or 1.0
    scale_factor = target_size / max_dim
    obj.scale = Vector((scale_factor,) * 3)
    bpy.context.view_layer.update()
    obj.location = (0, 0, 0)


def apply_default_material(obj, metal="gold"):
    """Placeholder PBR preset — replace with AMIPI-approved shader node
    groups per metal type once defined (this is exactly the kind of thing
    that belongs in the documented guideline)."""
    presets = {
        "gold": (0.83, 0.69, 0.22),
        "white_gold": (0.85, 0.85, 0.88),
        "rose_gold": (0.9, 0.66, 0.6),
        "platinum": (0.88, 0.88, 0.9),
    }
    color = presets.get(metal, presets["gold"])
    mat = bpy.data.materials.new(name=f"AMIPI_{metal}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.15
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def setup_camera(view: str, distance_factor: float, focal_length: float):
    cam_data = bpy.data.cameras.new(f"cam_{view}")
    cam_data.lens = focal_length
    cam_obj = bpy.data.objects.new(f"cam_{view}", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

    positions = {
        "hero_3quarter": (distance_factor, -distance_factor, distance_factor * 0.7),
        "front": (0, -distance_factor * 1.4, 0.2),
        "top": (0, 0.01, distance_factor * 1.6),
    }
    cam_obj.location = positions.get(view, positions["hero_3quarter"])
    constraint = cam_obj.constraints.new(type="TRACK_TO")
    constraint.target = bpy.data.objects.get("target_empty")
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    bpy.context.scene.camera = cam_obj
    return cam_obj


def setup_lighting(config: dict):
    # Three-point studio rig. Swap the "SUN" placeholders for an HDRI world
    # texture (config["lighting"]["hdri"]) once a real HDRI asset is chosen.
    key = bpy.data.lights.new("key", type="AREA")
    key.energy = 800 * config["lighting"].get("key_intensity", 1.0)
    key_obj = bpy.data.objects.new("key", key)
    key_obj.location = (3, -3, 4)
    bpy.context.scene.collection.objects.link(key_obj)

    fill = bpy.data.lights.new("fill", type="AREA")
    fill.energy = 400 * config["lighting"].get("fill_intensity", 0.4)
    fill_obj = bpy.data.objects.new("fill", fill)
    fill_obj.location = (-4, -2, 2)
    bpy.context.scene.collection.objects.link(fill_obj)

    rim = bpy.data.lights.new("rim", type="AREA")
    rim.energy = 500 * config["lighting"].get("rim_intensity", 0.6)
    rim_obj = bpy.data.objects.new("rim", rim)
    rim_obj.location = (0, 4, 3)
    bpy.context.scene.collection.objects.link(rim_obj)


def setup_background(config: dict):
    world = bpy.data.worlds.new("AMIPI_World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    # Flat top color as a simple starting point; a real gradient needs a
    # ColorRamp driven by a Gradient Texture node — left as a follow-up once
    # the brand gradient direction is confirmed.
    hex_color = config["background"].get("color_top", "#FFFFFF").lstrip("#")
    rgb = tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bpy.context.scene.world = world


def render(view: str, out_path: str, resolution: tuple[int, int]):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.filepath = out_path
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128  # bump for final quality once render times are measured
    bpy.ops.render.render(write_still=True)


def main():
    args = parse_args()
    config = json.loads(Path(args["config"]).read_text())

    clear_scene()
    empty = bpy.data.objects.new("target_empty", None)
    bpy.context.scene.collection.objects.link(empty)

    obj = import_model(args["input"])
    frame_and_scale(obj)
    apply_default_material(obj, metal="gold")  # TODO: read from job/product metadata
    setup_lighting(config)
    setup_background(config)

    out_dir = Path(args["outdir"])
    hero_size = tuple(config["output_sizes"]["hero"])
    thumb_size = tuple(config["output_sizes"]["thumbnail"])

    setup_camera("hero_3quarter", config["camera"]["distance_factor"], config["camera"]["focal_length_mm"])
    render("hero_3quarter", str(out_dir / "hero.png"), hero_size)
    render("hero_3quarter", str(out_dir / "thumbnail.png"), thumb_size)


if __name__ == "__main__":
    main()
