import bpy
import math
import random
import sys
from mathutils import Vector

# ============================================================
# GOJO SATORU - HOLLOW PURPLE CINEMATIC VFX
# Blender 4.2 - 5.x (best results with Eevee or Cycles)
#
# Run normally to build the effect.
# Run explain() from Blender's Python Console for documentation.
# Command-line usage:
# blender --background --python hollow_purple_cinematic.py -- --explain
# ============================================================

# ------------------------- USER SETTINGS -------------------------

SETTINGS = {
    "seed": 27,
    "animation_start": 1,
    "animation_end": 180,
    "fps": 30,
    "resolution_x": 1920,
    "resolution_y": 1080,
    "resolution_percentage": 100,
    "particle_count": 260,
    "lightning_count": 18,
    "create_camera": True,
    "create_lighting": True,
    "create_ground": False,
    "render_engine": "BLENDER_EEVEE_NEXT",
    "eevee_samples": 96,
    "glow_threshold": 0.8,
}

random.seed(SETTINGS["seed"])
scene = bpy.context.scene


# ------------------------- EXPLANATION COMMAND -------------------------

def explain():
    """Print an English guide to the Hollow Purple VFX systems."""
    print("""
========================================================================
GOJO SATORU - HOLLOW PURPLE: SCRIPT GUIDE
========================================================================

WHAT THIS SCRIPT BUILDS
  A cinematic purple energy sphere inspired by Gojo Satoru's Hollow Purple.
  The effect is made from layered procedural materials, animated plasma,
  a bright energy core, sparks, lightning tendrils, haze, and compositor glow.

MAIN SYSTEMS
  1. CORE
     A bright white-violet center. High emission makes it appear energized.

  2. PLASMA SHELLS
     Several overlapping spheres use animated 4D Noise textures and Color
     Ramps. Their different rotation speeds create layered energy motion.

  3. ENERGY HALO
     A larger transparent-looking volumetric shell adds atmospheric depth.
     Volume effects are most visible when rendered with Eevee or Cycles.

  4. PARTICLES
     Geometry Nodes instances tiny glowing fragments on points distributed
     around a spherical shell. The particle object rotates to animate them.

  5. LIGHTNING
     Procedural curve paths create irregular electrical tendrils. Their
     visible length flickers over time, while the curves rotate around the core.

  6. CINEMATIC LIGHTING AND CAMERA
     Area lights, a dark world, and a camera create a dramatic composition.

  7. COMPOSITOR
     Fog Glow adds bloom around emissive elements. Adjust the threshold
     in SETTINGS["glow_threshold"] to control which pixels glow.

HOW TO USE
  - Run the complete script in Blender's Scripting workspace.
  - To print this guide without building the effect, call explain().
  - From Blender's command line, use:
      blender --background --python hollow_purple_cinematic.py -- --explain

IMPORTANT SETTINGS
  SETTINGS["particle_count"]   Controls the number of energy fragments.
  SETTINGS["lightning_count"]  Controls the number of electrical tendrils.
  SETTINGS["animation_end"]    Sets the animation duration.
  SETTINGS["eevee_samples"]   Controls Eevee render samples.
  SETTINGS["create_ground"]   Adds an optional dark floor.

ANIMATION
  The effect uses frame-driven material drivers and object rotation.
  Move the timeline or render an animation to see the energy evolve.

TROUBLESHOOTING
  - If the effect looks too bright, lower material emission strengths or
    increase SETTINGS["glow_threshold"].
  - If the render is slow, reduce particle_count and eevee_samples.
  - If the volume looks noisy, increase render samples or reduce its density.
  - For the strongest cinematic look, render at full resolution and use
    AgX color management.

This is a procedural Blender effect, not a physically simulated fluid or
electromagnetic field. The cinematic appearance is created through layered
shading, geometry, animation, lighting, and compositing.
========================================================================
""")


# ------------------------- GENERAL HELPERS -------------------------

def link_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def get_or_create_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    return collection


def clear_previous_effect():
    """Remove the objects and data created by earlier runs of this script."""
    collection = bpy.data.collections.get("HollowPurple_Cinematic")
    if collection:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)

    # Remove leftover HP_ data so re-running does not pile up ".001" duplicates.
    # Order matters: node groups hold material references, so they go first.
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.lights,
                       bpy.data.cameras, bpy.data.node_groups, bpy.data.materials):
        for block in list(datablocks):
            if block.name.startswith("HP_") and block.users == 0:
                datablocks.remove(block)


def find_socket(sockets, *names, socket_type=None):
    """Find a node socket by display name OR identifier.

    Some nodes (Random Value, for example) have one Min/Max/Value socket per data
    type, all sharing the same name, so a plain inputs["Min"] can return the
    wrong (vector) socket. Pass socket_type ("VALUE" = float, "VECTOR", "INT",
    ...) to pick the right one. Returns None if nothing matches.
    """
    for wanted in names:
        for socket in sockets:
            if wanted in (socket.name, socket.identifier):
                if socket_type is None or socket.type == socket_type:
                    return socket
    return None


def set_input(node, socket_names, value):
    socket = find_socket(node.inputs, *socket_names)
    if socket is None:
        return False
    try:
        socket.default_value = value
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def enable_nodes(id_block):
    """Turn on use_nodes. Blender 5.x deprecates it (nodes are always on)."""
    try:
        id_block.use_nodes = True
    except (AttributeError, TypeError):
        pass


def add_driver(data_block, data_path, index, expression):
    """Add a Python-expression driver. Falls back to no index for non-array props."""
    fcurve = None
    for args in ((data_path, index), (data_path,)):
        try:
            result = data_block.driver_add(*args)
        except Exception:
            continue
        fcurve = result[0] if isinstance(result, (list, tuple)) else result
        break

    if fcurve is None:
        print(f"[HOLLOW PURPLE] Warning: could not add a driver to '{data_path}'.")
        return None

    fcurve.driver.type = "SCRIPTED"
    fcurve.driver.expression = expression
    return fcurve


def animate_noise_w(noise, speed):
    """Animate a Noise Texture's 'W' input so the pattern evolves over time.

    The W input only exists while the node is in 4D mode, so switch to 4D first.
    """
    noise.noise_dimensions = "4D"
    w_socket = find_socket(noise.inputs, "W")
    if w_socket is None:
        print("[HOLLOW PURPLE] Warning: Noise Texture has no 'W' input; "
              "its animation was skipped.")
        return
    add_driver(w_socket, "default_value", 0, f"frame * {speed}")


def make_emission_material(name, color, strength):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength

    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


# ------------------------- RENDER AND WORLD -------------------------

def configure_render():
    # Blender 4.2-4.5 call the engine BLENDER_EEVEE_NEXT, while Blender 5.0+ renamed
    # it back to BLENDER_EEVEE. Try the configured name first, then the others.
    for engine in (SETTINGS["render_engine"], "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except (TypeError, ValueError):
            continue
    else:
        print("[HOLLOW PURPLE] Warning: could not set the render engine; "
              "keeping the current one.")

    scene.render.resolution_x = SETTINGS["resolution_x"]
    scene.render.resolution_y = SETTINGS["resolution_y"]
    scene.render.resolution_percentage = SETTINGS["resolution_percentage"]
    scene.render.fps = SETTINGS["fps"]
    scene.frame_start = SETTINGS["animation_start"]
    scene.frame_end = SETTINGS["animation_end"]

    try:
        scene.eevee.taa_render_samples = SETTINGS["eevee_samples"]
    except (AttributeError, TypeError):
        pass

    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    try:
        scene.view_settings.view_transform = "AgX"
    except (TypeError, ValueError):
        pass
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except (TypeError, ValueError):
            continue
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    if scene.world is None:
        scene.world = bpy.data.worlds.new("HollowPurple_World")

    enable_nodes(scene.world)
    world_tree = scene.world.node_tree
    if world_tree is not None:
        background = world_tree.nodes.get("Background")
        if background is None:
            background = world_tree.nodes.new("ShaderNodeBackground")
            world_output = world_tree.nodes.get("World Output")
            if world_output is None:
                world_output = world_tree.nodes.new("ShaderNodeOutputWorld")
            world_tree.links.new(background.outputs[0], world_output.inputs[0])
        background.inputs["Color"].default_value = (0.0015, 0.0005, 0.006, 1.0)
        background.inputs["Strength"].default_value = 0.12


# ------------------------- MATERIALS -------------------------

def create_procedural_plasma(name, dark_color, mid_color, bright_color,
                             noise_scale, noise_speed, emission_strength,
                             detail=8.0, opacity=None):
    # opacity=None -> solid shell. A value (0-1) -> semi-transparent shell whose
    # see-through pattern follows the noise, so the layers underneath show.
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-900, 0)

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-700, 0)

    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-480, 0)
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = detail
    noise.inputs["Roughness"].default_value = 0.72
    noise.inputs["Distortion"].default_value = 1.7
    animate_noise_w(noise, noise_speed)

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-220, 0)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = dark_color
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = bright_color
    middle = ramp.color_ramp.elements.new(0.55)
    middle.color = mid_color

    emission = nt.nodes.new("ShaderNodeEmission")
    emission.location = (40, 0)
    emission.inputs["Strength"].default_value = emission_strength

    output = nt.nodes.new("ShaderNodeOutputMaterial")
    output.location = (260, 0)

    links = nt.links
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])

    if opacity is None:
        links.new(emission.outputs["Emission"], output.inputs["Surface"])
        return mat

    # Without this, the outermost solid emission shell hides every shell inside
    # it, so only one layer would ever be visible.
    alpha_ramp = nt.nodes.new("ShaderNodeValToRGB")
    alpha_ramp.location = (-220, -320)
    alpha_ramp.color_ramp.elements[0].position = 0.35
    alpha_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    alpha_ramp.color_ramp.elements[1].position = 0.70
    alpha_ramp.color_ramp.elements[1].color = (opacity, opacity, opacity, 1.0)

    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (40, -220)

    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (260, -80)
    output.location = (480, 0)

    links.new(noise.outputs["Fac"], alpha_ramp.inputs["Fac"])
    links.new(alpha_ramp.outputs["Color"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    return mat


def create_core_material():
    mat = bpy.data.materials.new("HP_Core_WhiteViolet")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.noise_dimensions = "4D"  # the 'W' (time) input only exists in 4D mode
    tex.inputs["Scale"].default_value = 5.0
    tex.inputs["Detail"].default_value = 5.0
    tex.inputs["Roughness"].default_value = 0.8
    animate_noise_w(tex, 0.018)

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.12, 0.015, 0.35, 1)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (1.0, 0.82, 1.0, 1)
    middle = ramp.color_ramp.elements.new(0.52)
    middle.color = (0.58, 0.18, 1.0, 1)

    emission = nt.nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 22.0
    output = nt.nodes.new("ShaderNodeOutputMaterial")

    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emission.inputs["Color"])
    nt.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_volume_material():
    mat = bpy.data.materials.new("HP_Violet_Atmosphere")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    volume = nt.nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = (0.25, 0.035, 0.62, 1.0)
    volume.inputs["Density"].default_value = 0.025
    set_input(volume, ["Anisotropy"], 0.35)
    set_input(volume, ["Emission Color"], (0.35, 0.04, 0.9, 1.0))
    set_input(volume, ["Emission Strength"], 0.22)

    output = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(volume.outputs["Volume"], output.inputs["Volume"])
    return mat


# ------------------------- SPHERE AND PLASMA LAYERS -------------------------

def create_uv_sphere(name, radius, material, collection, segments=96, rings=64):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, radius=radius, location=(0, 0, 0)
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_Mesh"
    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    obj.data.materials.append(material)
    link_to_collection(obj, collection)
    return obj


def animate_rotation(obj, axis, speed):
    add_driver(obj, "rotation_euler", axis, f"frame * {speed}")


def build_energy_sphere(collection):
    core_mat = create_core_material()
    dark_mat = create_procedural_plasma(
        "HP_Dark_Edge_Plasma",
        (0.008, 0.001, 0.025, 1),
        (0.12, 0.008, 0.32, 1),
        (0.65, 0.2, 1.0, 1),
        4.5, 0.022, 5.5, opacity=0.9
    )
    plasma_mat = create_procedural_plasma(
        "HP_Main_Plasma",
        (0.025, 0.001, 0.09, 1),
        (0.34, 0.025, 0.8, 1),
        (0.95, 0.58, 1.0, 1),
        3.2, -0.031, 9.0, opacity=0.75
    )
    hot_mat = create_procedural_plasma(
        "HP_Hot_Outer_Filaments",
        (0.08, 0.005, 0.2, 1),
        (0.55, 0.12, 1.0, 1),
        (1.0, 0.88, 1.0, 1),
        7.0, 0.047, 12.0, detail=10.0, opacity=0.6
    )

    core = create_uv_sphere("HP_Core", 0.48, core_mat, collection)
    dark_shell = create_uv_sphere("HP_Dark_Energy_Boundary", 0.68, dark_mat, collection)
    main_shell = create_uv_sphere("HP_Main_Plasma_Shell", 0.92, plasma_mat, collection)
    outer_shell = create_uv_sphere("HP_Outer_Filament_Shell", 1.02, hot_mat, collection)

    animate_rotation(dark_shell, 2, 0.018)
    animate_rotation(main_shell, 1, -0.027)
    animate_rotation(main_shell, 2, 0.036)
    animate_rotation(outer_shell, 0, 0.021)
    animate_rotation(outer_shell, 2, -0.052)

    # Slight pulsing gives the core a changing energy output.
    add_driver(core, "scale", 0, "1.0 + 0.035 * sin(frame * 0.12)")
    add_driver(core, "scale", 1, "1.0 + 0.035 * sin(frame * 0.12)")
    add_driver(core, "scale", 2, "1.0 + 0.035 * sin(frame * 0.12)")

    volume_mat = create_volume_material()
    halo = create_uv_sphere("HP_Volumetric_Halo", 1.42, volume_mat, collection, 64, 48)
    halo.display_type = "WIRE"
    return core, dark_shell, main_shell, outer_shell, halo


# ------------------------- GEOMETRY NODES PARTICLES -------------------------

def build_particles(collection):
    particle_count = max(1, int(SETTINGS["particle_count"]))
    vertices = []

    for _ in range(particle_count):
        direction = Vector((
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            random.uniform(-1, 1)
        ))
        if direction.length == 0:
            direction = Vector((0, 0, 1))
        direction.normalize()
        radius = random.uniform(0.92, 1.48)
        vertices.append(tuple(direction * radius))

    mesh = bpy.data.meshes.new("HP_Particle_Point_Mesh")
    mesh.from_pydata(vertices, [], [])
    mesh.update()

    points_obj = bpy.data.objects.new("HP_Energy_Particles", mesh)
    collection.objects.link(points_obj)

    particle_mat = make_emission_material(
        "HP_Particle_Emission", (0.72, 0.28, 1.0, 1), 18.0
    )

    # Geometry Nodes: input points -> instance tiny ico spheres -> output.
    group = bpy.data.node_groups.new("HP_Particle_Instancing", "GeometryNodeTree")
    group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )

    nodes = group.nodes
    links = group.links

    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-600, 100)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (500, 100)

    ico = nodes.new("GeometryNodeMeshIcoSphere")
    ico.location = (-600, -180)
    ico.inputs["Radius"].default_value = 0.025
    set_input(ico, ["Subdivisions"], 1)

    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.location = (-350, -180)
    set_material.inputs["Material"].default_value = particle_mat
    links.new(ico.outputs["Mesh"], set_material.inputs["Geometry"])

    random_scale = nodes.new("FunctionNodeRandomValue")
    random_scale.data_type = "FLOAT"
    random_scale.location = (-350, -420)
    # Random Value has separate Min/Max/Value sockets for every data type, all with
    # the same names. Pick the float ones explicitly (inputs["Min"] is the vector).
    find_socket(random_scale.inputs, "Min", socket_type="VALUE").default_value = 0.35
    find_socket(random_scale.inputs, "Max", socket_type="VALUE").default_value = 1.8
    random_value_out = find_socket(random_scale.outputs, "Value", socket_type="VALUE")

    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (0, 100)
    links.new(group_in.outputs["Geometry"], instance.inputs["Points"])
    links.new(set_material.outputs["Geometry"], instance.inputs["Instance"])
    links.new(random_value_out, instance.inputs["Scale"])
    links.new(instance.outputs["Instances"], group_out.inputs["Geometry"])

    modifier = points_obj.modifiers.new("HP_Particle_GeometryNodes", "NODES")
    modifier.node_group = group

    animate_rotation(points_obj, 2, 0.032)
    add_driver(points_obj, "rotation_euler", 0, "frame * 0.012")
    return points_obj


# ------------------------- LIGHTNING TENDRILS -------------------------

def create_lightning_material():
    return make_emission_material(
        "HP_Lightning_WhiteViolet", (0.78, 0.48, 1.0, 1), 28.0
    )


def create_lightning_arc(index, collection, material):
    # Arcs wrap around the energy sphere in varied 3D directions.
    angle = random.uniform(0, math.tau)
    height = random.uniform(-0.9, 0.9)
    radial = math.sqrt(max(0.05, 1.0 - height * height))

    start = Vector((
        math.cos(angle) * radial,
        math.sin(angle) * radial,
        height
    )) * random.uniform(0.78, 1.0)

    end_angle = angle + random.uniform(-1.1, 1.1)
    end_height = max(-1.0, min(1.0, height + random.uniform(-0.75, 0.75)))
    end_radial = math.sqrt(max(0.05, 1.0 - end_height * end_height))
    end = Vector((
        math.cos(end_angle) * end_radial,
        math.sin(end_angle) * end_radial,
        end_height
    )) * random.uniform(0.82, 1.28)

    midpoint = (start + end) * 0.5
    midpoint += Vector((
        random.uniform(-0.55, 0.55),
        random.uniform(-0.55, 0.55),
        random.uniform(-0.55, 0.55)
    ))

    points = []
    segment_count = random.randint(14, 24)
    for step in range(segment_count + 1):
        t = step / segment_count
        base = (1 - t) ** 2 * start + 2 * (1 - t) * t * midpoint + t ** 2 * end
        envelope = math.sin(math.pi * t)
        jitter = random.uniform(-0.14, 0.14) * envelope
        base += Vector((
            random.uniform(-1, 1) * jitter,
            random.uniform(-1, 1) * jitter,
            random.uniform(-1, 1) * jitter
        ))
        points.append(base)

    curve = bpy.data.curves.new(f"HP_Lightning_Curve_{index:02d}", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = random.uniform(0.006, 0.014)
    curve.bevel_resolution = 3

    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for i, point in enumerate(points):
        spline.points[i].co = (*point, 1.0)
        spline.points[i].radius = 0.2 + math.sin(math.pi * i / (len(points) - 1)) * 1.1

    # Flicker the visible length to mimic unstable electrical discharge.
    curve.bevel_factor_start = 0.0
    curve.bevel_factor_end = 1.0
    add_driver(
        curve, "bevel_factor_end", 0,
        f"0.48 + 0.52 * abs(sin(frame * {random.uniform(0.18, 0.34):.4f} + {index * 1.7:.3f}))"
    )

    arc_obj = bpy.data.objects.new(f"HP_Lightning_Arc_{index:02d}", curve)
    collection.objects.link(arc_obj)
    curve.materials.append(material)

    direction = random.choice([-1, 1])
    add_driver(arc_obj, "rotation_euler", 2, f"frame * {direction * random.uniform(0.012, 0.035):.4f}")
    return arc_obj


def build_lightning(collection):
    material = create_lightning_material()
    for index in range(max(1, int(SETTINGS["lightning_count"]))):
        create_lightning_arc(index, collection, material)


# ------------------------- CAMERA AND LIGHTS -------------------------

def point_object_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_camera(collection):
    camera_data = bpy.data.cameras.new("HP_Cinematic_Camera")
    camera = bpy.data.objects.new("HP_Cinematic_Camera", camera_data)
    collection.objects.link(camera)
    camera.location = (0.0, -6.8, 1.0)
    point_object_at(camera, (0.0, 0.0, 0.0))
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 6.8
    camera.data.dof.aperture_fstop = 5.6
    scene.camera = camera
    return camera


def create_area_light(name, collection, location, color, power, size):
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = power
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size

    light_obj = bpy.data.objects.new(name, light_data)
    collection.objects.link(light_obj)
    light_obj.location = location
    point_object_at(light_obj, (0, 0, 0))
    return light_obj


def build_lighting(collection):
    create_area_light(
        "HP_Key_Light", collection, (3.5, -3.0, 3.0),
        (0.45, 0.12, 1.0), 900, 4.0
    )
    create_area_light(
        "HP_Rim_Light", collection, (-3.0, 1.5, 1.8),
        (0.18, 0.25, 1.0), 1300, 3.0
    )
    create_area_light(
        "HP_Magenta_Fill", collection, (0.0, 3.0, -1.0),
        (0.8, 0.08, 1.0), 700, 3.5
    )


def build_ground(collection):
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -2.2))
    ground = bpy.context.object
    ground.name = "HP_Dark_Ground"
    ground.data.name = "HP_Dark_Ground_Mesh"
    material = bpy.data.materials.new("HP_Ground_Matte")
    material.diffuse_color = (0.008, 0.006, 0.018, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.008, 0.006, 0.018, 1)
        bsdf.inputs["Roughness"].default_value = 0.82
    ground.data.materials.append(material)
    link_to_collection(ground, collection)


# ------------------------- COMPOSITOR GLOW -------------------------

def configure_glare(node, threshold, size):
    """Configure a Fog Glow node. Blender 4.2 - 5.x expose its settings differently."""
    # Glare type: a node property on older builds, a menu input on newer ones.
    try:
        node.glare_type = "FOG_GLOW"
    except (AttributeError, TypeError, ValueError):
        pass
    type_socket = find_socket(node.inputs, "Type", "Glare Type")
    if type_socket is not None:
        for value in ("Fog Glow", "FOG_GLOW"):
            try:
                type_socket.default_value = value
                break
            except (TypeError, ValueError):
                continue

    try:
        node.quality = "HIGH"
    except (AttributeError, TypeError, ValueError):
        pass

    # Threshold: an input socket on 4.4+, a node property before that.
    threshold_socket = find_socket(node.inputs, "Threshold")
    if threshold_socket is not None:
        threshold_socket.default_value = threshold
    elif hasattr(node, "threshold"):
        node.threshold = threshold

    # Size: older builds take an integer 6-9 (9 = widest); newer builds take a
    # 0-1 value relative to the image where each step down halves the spread.
    size_socket = find_socket(node.inputs, "Size")
    if size_socket is not None:
        size_socket.default_value = 2.0 ** (size - 9)
    elif hasattr(node, "size"):
        node.size = size


def setup_compositor():
    """Add a two-stage Fog Glow bloom (works on Blender 4.2-4.5 and 5.x)."""
    tree = None
    if hasattr(scene, "node_tree"):
        # Blender 4.x: the compositor tree belongs to the scene.
        try:
            scene.use_nodes = True
        except AttributeError:
            pass
        tree = scene.node_tree

    if tree is not None:
        tree.nodes.clear()
        output = tree.nodes.new("CompositorNodeComposite")
    else:
        # Blender 5.0+: the compositor is a standalone node group, and the
        # Composite node was replaced by a Group Output node.
        old_group = bpy.data.node_groups.get("HP_Compositor")
        if old_group is not None:
            bpy.data.node_groups.remove(old_group)
        tree = bpy.data.node_groups.new("HP_Compositor", "CompositorNodeTree")
        tree.interface.new_socket(
            name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
        )
        scene.compositing_node_group = tree
        output = tree.nodes.new("NodeGroupOutput")
    output.location = (420, 0)

    render_layers = tree.nodes.new("CompositorNodeRLayers")
    render_layers.location = (-400, 0)

    glare = tree.nodes.new("CompositorNodeGlare")
    glare.location = (-100, 0)
    configure_glare(glare, SETTINGS["glow_threshold"], 9)

    glare_mix = tree.nodes.new("CompositorNodeGlare")
    glare_mix.location = (150, 0)
    configure_glare(glare_mix, 1.8, 7)

    tree.links.new(render_layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], glare_mix.inputs["Image"])
    tree.links.new(glare_mix.outputs["Image"], output.inputs[0])


# ------------------------- BUILD THE EFFECT -------------------------

def build_hollow_purple():
    print("[HOLLOW PURPLE] Starting cinematic VFX setup...")

    # The mesh operators used below only work in Object Mode.
    try:
        active = bpy.context.object
        if active is not None and active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError:
        pass

    clear_previous_effect()
    collection = get_or_create_collection("HollowPurple_Cinematic")

    configure_render()
    build_energy_sphere(collection)
    build_particles(collection)
    build_lightning(collection)

    if SETTINGS["create_lighting"]:
        build_lighting(collection)

    if SETTINGS["create_camera"]:
        create_camera(collection)

    if SETTINGS["create_ground"]:
        build_ground(collection)

    try:
        setup_compositor()
    except Exception as error:
        print(f"[HOLLOW PURPLE] Warning: compositor glow was skipped ({error}). "
              "Add a Glare (Fog Glow) node in the Compositing workspace instead.")

    scene.frame_set(1)
    print("[HOLLOW PURPLE] Build completed successfully.")
    print("[HOLLOW PURPLE] Collection: HollowPurple_Cinematic")
    print("[HOLLOW PURPLE] Run explain() for the English documentation.")
    print("[HOLLOW PURPLE] Press Numpad 0 to view the camera.")
    return collection


# ------------------------- SCRIPT ENTRY POINT -------------------------

if "--explain" in sys.argv:
    explain()
else:
    build_hollow_purple()
