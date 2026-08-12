"""
Headless Blender render script — the automated half of the "documented
rendering guideline." Reads a template_config.json (camera/lighting/
background/output-size settings from the render_templates table) and
applies it identically to every product — no human operating Blender.

Run via:
    blender --background --python blender_render.py -- \
        --input path/to/model.stl \
        --config path/to/template_config.json \
        --outdir path/to/out \
        --metal gold

Supported --metal values: gold | white_gold | rose_gold | platinum | silver
Supported input types:    .stl | .obj

Requires Blender 4.x (free, https://www.blender.org) — no license cost.
Materials and lighting are production-grade starting points; refine PBR
values per the final AMIPI approved spec once signed off by stakeholders.
"""
import bpy
import json
import os
import sys
from pathlib import Path
from mathutils import Vector


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> dict:
    """Return a dict of key→value pairs from args after Blender's '--' separator."""
    argv = sys.argv[sys.argv.index("--") + 1:]
    result: dict = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            result[argv[i].lstrip("-")] = argv[i + 1]
            i += 2
        else:
            i += 1
    return result


# ---------------------------------------------------------------------------
# Scene management
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


# ---------------------------------------------------------------------------
# Mesh import & normalisation
# ---------------------------------------------------------------------------

def import_model(path: str):
    """Import .stl or .obj; join multi-object imports into one mesh."""
    ext = Path(path).suffix.lower()
    if ext == ".stl":
        bpy.ops.import_mesh.stl(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f"Unsupported 3D input: {ext}. Supported: .stl, .obj")

    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not objs:
        raise RuntimeError("No MESH object found after import.")
    if len(objs) > 1:
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def frame_and_center(obj, target_size: float = 2.0):
    """Scale the longest axis to target_size and center at the origin.
    Every product fills the frame consistently regardless of native mesh units."""
    bpy.context.view_layer.update()
    dims = obj.dimensions
    max_dim = max(dims.x, dims.y, dims.z) or 1.0
    obj.scale = Vector((target_size / max_dim,) * 3)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
# Materials — physics-based presets per metal type
# Adjust Base Color and Roughness once AMIPI's approved look is signed off.
# Colors are in linear sRGB (Blender works in linear internally).
# ---------------------------------------------------------------------------

_METAL_PRESETS: dict = {
    "gold": {
        "color":       (0.944, 0.776, 0.373, 1.0),
        "roughness":   0.12,
        "anisotropy":  0.30,
        "ior":         0.47,
    },
    "white_gold": {
        "color":       (0.832, 0.842, 0.874, 1.0),
        "roughness":   0.10,
        "anisotropy":  0.20,
        "ior":         0.50,
    },
    "rose_gold": {
        "color":       (0.944, 0.668, 0.579, 1.0),
        "roughness":   0.13,
        "anisotropy":  0.30,
        "ior":         0.47,
    },
    "platinum": {
        "color":       (0.800, 0.800, 0.830, 1.0),
        "roughness":   0.06,
        "anisotropy":  0.10,
        "ior":         2.33,
    },
    "silver": {
        "color":       (0.870, 0.870, 0.870, 1.0),
        "roughness":   0.09,
        "anisotropy":  0.20,
        "ior":         0.18,
    },
}


def apply_material(obj, metal: str = "gold"):
    preset = _METAL_PRESETS.get(metal.lower(), _METAL_PRESETS["gold"])

    mat = bpy.data.materials.new(name=f"AMIPI_{metal}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out_node.location = (400, 0)
    bsdf.location = (0, 0)

    bsdf.inputs["Base Color"].default_value = preset["color"]
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = preset["roughness"]
    bsdf.inputs["IOR"].default_value = preset["ior"]

    # Anisotropy (Blender 4.x key name)
    for key in ("Anisotropic", "Anisotropy"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = preset["anisotropy"]
            break

    # Specular tint aligned to metal color
    for key in ("Specular Tint", "Specular"):
        if key in bsdf.inputs:
            try:
                bsdf.inputs[key].default_value = 1.0
            except Exception:
                pass
            break

    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Camera — one camera per view, created fresh and removed after render
# ---------------------------------------------------------------------------

_VIEW_POSITIONS = {
    # lambdas receive distance_factor d; return (x, y, z) in world space
    "hero_3quarter": lambda d: ( d * 0.90, -d * 1.00,  d * 0.70),
    "front":         lambda d: ( 0.0,      -d * 1.40,   0.15),
    "top":           lambda d: ( 0.0,       0.01,        d * 1.70),
    "side":          lambda d: ( d * 1.50,  0.0,         0.15),
}


def make_camera(name: str, location: tuple, focal_length: float, target_empty) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = focal_length
    cam_data.clip_start = 0.01
    cam_data.clip_end = 200.0
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = location

    ct = cam_obj.constraints.new(type="TRACK_TO")
    ct.target = target_empty
    ct.track_axis = "TRACK_NEGATIVE_Z"
    ct.up_axis = "UP_Y"

    bpy.context.scene.camera = cam_obj
    return cam_obj


# ---------------------------------------------------------------------------
# Lighting — 3-point area rig + optional HDRI world
# ---------------------------------------------------------------------------

def setup_lighting(config: dict):
    lc = config.get("lighting", {})

    # Try to load an HDRI from assets/ — the config stores the base name
    hdri_name = lc.get("hdri", "")
    hdri_loaded = False
    if hdri_name:
        asset_dir = Path(__file__).resolve().parent.parent / "assets"
        for ext in (".hdr", ".exr"):
            candidate = asset_dir / f"{hdri_name}{ext}"
            if candidate.exists():
                _setup_hdri_world(str(candidate))
                hdri_loaded = True
                break

    if not hdri_loaded:
        # Warm neutral ambient — provides consistent fill from all directions.
        # Key: NOT too dark. A near-black ambient made the backdrop appear to
        # emit different amounts of light from different viewing angles (GI issue).
        world = bpy.data.worlds.new("AMIPI_World_Ambient")
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.90, 0.88, 0.85, 1.0)  # warm neutral
        bg.inputs["Strength"].default_value = 0.40
        bpy.context.scene.world = world

    # Three-point area light rig — provides fill even when HDRI is present
    _add_area_light("key_light",  ( 3.5, -3.0,  4.5), 800 * lc.get("key_intensity", 1.0), size=1.5)
    _add_area_light("fill_light", (-4.0, -2.0,  2.0), 400 * lc.get("fill_intensity", 0.4), size=2.0)
    _add_area_light("rim_light",  ( 0.0,  4.5,  3.5), 600 * lc.get("rim_intensity",  0.6), size=1.0)


def _add_area_light(name: str, location: tuple, energy: float, size: float = 1.0):
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = energy
    light_data.size = size
    light_data.use_shadow = True
    obj = bpy.data.objects.new(name, light_data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)


def _setup_hdri_world(hdri_path: str):
    world = bpy.data.worlds.new("AMIPI_World_HDRI")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output  = nodes.new("ShaderNodeOutputWorld")
    bg      = nodes.new("ShaderNodeBackground")
    env     = nodes.new("ShaderNodeTexEnvironment")
    mapping = nodes.new("ShaderNodeMapping")
    texco   = nodes.new("ShaderNodeTexCoord")

    env.image = bpy.data.images.load(hdri_path)
    bg.inputs["Strength"].default_value = 1.0

    links.new(texco.outputs["Generated"],   mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"],    env.inputs["Vector"])
    links.new(env.outputs["Color"],         bg.inputs["Color"])
    links.new(bg.outputs["Background"],     output.inputs["Surface"])

    bpy.context.scene.world = world


# ---------------------------------------------------------------------------
# Background — large studio backdrop plane with gradient or flat colour
# ---------------------------------------------------------------------------

def _hex_to_linear(hex_color: str) -> tuple:
    """Convert #RRGGBB (sRGB) to a linear RGB tuple for Blender's color inputs."""
    h = hex_color.strip().lstrip("#")
    srgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(c ** 2.2 for c in srgb)  # approximate sRGB→linear


def setup_background(config: dict):
    """Create a large backdrop plane behind and below the object.
    Visible from front, 3-quarter, and top camera angles."""
    bg_cfg = config.get("background", {})
    color_top = _hex_to_linear(bg_cfg.get("color_top", "#FFFFFF"))
    color_bot = _hex_to_linear(bg_cfg.get("color_bottom", bg_cfg.get("color_top", "#FFFFFF")))
    bg_type = bg_cfg.get("type", "flat")

    # Back wall — vertical plane behind the object (positive Y side)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 5, 5))
    back_wall = bpy.context.active_object
    back_wall.name = "AMIPI_BackWall"
    back_wall.rotation_euler = (1.5708, 0, 0)   # rotate to face -Y (toward camera)

    # Floor — horizontal plane below the object (top-view background)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -1.1))
    floor = bpy.context.active_object
    floor.name = "AMIPI_Floor"
    # default rotation is already horizontal (XY plane)

    # Build the shared backdrop material
    mat = _make_backdrop_material("AMIPI_Backdrop", color_top, color_bot, bg_type)
    back_wall.data.materials.append(mat)
    floor.data.materials.append(mat)


def _make_backdrop_material(name: str, color_top: tuple, color_bot: tuple, bg_type: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")

    # IMPORTANT: use Diffuse (not Emission) for the backdrop.
    # Emission shaders actively emit light and cause GI color bleeding — the warm
    # white backdrop was tinting the metal material differently depending on how
    # much of it was visible from each camera angle (top vs 3quarter vs front).
    # Diffuse just receives and reflects light like a normal surface.
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Roughness"].default_value = 1.0

    if bg_type == "gradient" and color_top != color_bot:
        texco   = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        grad    = nodes.new("ShaderNodeTexGradient")
        ramp    = nodes.new("ShaderNodeValToRGB")

        grad.gradient_type = "LINEAR"
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, 1.5708)

        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color    = (*color_top, 1.0)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color    = (*color_bot, 1.0)

        links.new(texco.outputs["Generated"],  mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"],   grad.inputs["Vector"])
        links.new(grad.outputs["Color"],       ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"],       diffuse.inputs["Color"])
    else:
        diffuse.inputs["Color"].default_value = (*color_top, 1.0)

    links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# Render — Cycles with GPU auto-detect and denoising
# ---------------------------------------------------------------------------

def configure_render_engine():
    """Enable Cycles; try GPU (CUDA/OptiX/Metal) and fall back to CPU silently.
    Filmic view transform with no look prevents blown highlights on polished metals."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128          # bump to 512+ for final production quality
    scene.cycles.use_denoising = True

    # Filmic prevents the overexposed "blown" look on high-reflectance metals.
    # "None" look applies Filmic tone mapping without any additional colour grading.
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "None"

    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for device_type in ("OPTIX", "CUDA", "HIP", "METAL"):
            try:
                prefs.compute_device_type = device_type
                prefs.get_devices()
                active = [d for d in prefs.devices if d.use]
                if active:
                    scene.cycles.device = "GPU"
                    return
            except Exception:
                continue
    except Exception:
        pass

    scene.cycles.device = "CPU"


def render_view(out_path: str, resolution: tuple):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.filepath = out_path
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    config = json.loads(Path(args["config"]).read_text())

    clear_scene()
    configure_render_engine()

    # Target empty — all cameras track this
    target = bpy.data.objects.new("target_empty", None)
    target.empty_display_type = "PLAIN_AXES"
    bpy.context.scene.collection.objects.link(target)
    target.location = (0.0, 0.0, 0.2)   # slightly above ground for rings/pendants

    # Import and normalise mesh
    obj = import_model(args["input"])
    frame_and_center(obj)

    # Apply metal material from --metal arg (defaults to gold)
    metal = args.get("metal", "gold").lower()
    apply_material(obj, metal=metal)

    # Lighting and backdrop
    setup_lighting(config)
    setup_background(config)

    # Render settings
    out_dir = Path(args["outdir"])
    cam_cfg = config.get("camera", {})
    views = cam_cfg.get("views", ["hero_3quarter"])
    focal_length = cam_cfg.get("focal_length_mm", 85)
    distance = cam_cfg.get("distance_factor", 2.2)
    hero_size = tuple(config.get("output_sizes", {}).get("hero", [2000, 2000]))

    # Render each view at hero resolution
    # (thumbnail is generated from hero by Pillow in render_dispatch.py — no second render pass)
    for view in views:
        pos_fn = _VIEW_POSITIONS.get(view, _VIEW_POSITIONS["hero_3quarter"])
        cam = make_camera(f"cam_{view}", pos_fn(distance), focal_length, target)
        render_view(str(out_dir / f"{view}.png"), hero_size)
        bpy.data.objects.remove(cam, do_unlink=True)

    print(f"[blender_render] Done — rendered views: {views}")


if __name__ == "__main__":
    main()
