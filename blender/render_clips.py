# Blender headless render of BVH clips on a capsule figure.
# Usage: blender -b -P blender/render_clips.py -- <out_dir> <clip.bvh> [<clip.bvh> ...]
# Env: STEP (render every Nth source frame, default 4), MAX_SEC (default 3.0), RES (default 360),
#      CAMS (comma list of: front,side,q34,feet,top; default front,side,q34,feet)
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
CLIPS = argv[1:]
STEP = int(os.environ.get("STEP", "4"))
MAX_SEC = float(os.environ.get("MAX_SEC", "3.0"))
RES = int(os.environ.get("RES", "360"))
CAMS = os.environ.get("CAMS", "front,side,q34,feet").split(",")
HIP_HEIGHT = 0.95  # target standing hip height in meters


def log(*a):
    print("[lab]", *a, flush=True)


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.preferences.addon_enable(module="io_anim_bvh")
    except Exception as ex:  # already enabled / built in
        log("addon_enable:", ex)


def mat(name, rgb, checker=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.7
    if checker:
        ch = nt.nodes.new("ShaderNodeTexChecker")
        ch.inputs["Scale"].default_value = 40.0
        ch.inputs["Color1"].default_value = (0.42, 0.44, 0.47, 1)
        ch.inputs["Color2"].default_value = (0.30, 0.32, 0.35, 1)
        nt.links.new(ch.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    return m


def setup_world():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 2
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.12, 0.16, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
    bpy.context.object.data.energy = 3.0
    bpy.ops.mesh.primitive_plane_add(size=60)
    bpy.context.object.data.materials.append(mat("floor", (0.4, 0.4, 0.4), checker=True))


def armature_height(arm):
    # lowest and hip points at current frame
    hips = arm.pose.bones[0]
    hz = (arm.matrix_world @ hips.head).z
    lo = min((arm.matrix_world @ pb.tail).z for pb in arm.pose.bones)
    return hz, lo


def import_bvh(path):
    bpy.ops.import_anim.bvh(filepath=path, global_scale=0.056444, rotate_mode="NATIVE",
                            axis_forward="-Z", axis_up="Y", update_scene_fps=True,
                            update_scene_duration=True)
    arm = bpy.context.object
    sc = bpy.context.scene
    sc.frame_set(sc.frame_start)
    hz, lo = armature_height(arm)
    if hz - lo > 0.2:
        s = HIP_HEIGHT / (hz - lo)
        arm.scale = (s, s, s)
        bpy.context.view_layer.update()
        hz, lo = armature_height(arm)
    arm.location.z -= lo
    bpy.context.view_layer.update()
    return arm


def capsule_figure(arm):
    body = mat("body", (0.85, 0.45, 0.2))
    left = mat("left", (0.25, 0.55, 0.9))
    for pb in arm.pose.bones:
        b = pb.bone
        ln = b.length
        name = b.name.lower()
        m = left if name.startswith("left") or name.endswith("_l") else body
        if ln < 0.01:
            continue
        r = 0.045
        if any(k in name for k in ("spine", "hips", "chest")):
            r = 0.09
        elif "neck" in name:
            r = 0.04
        elif any(k in name for k in ("hand", "finger", "thumb", "toe")):
            r = 0.025
        elif "head" in name:
            r = 0.09
        # cylinder along bone Y, centered on bone
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=r / arm.scale[0], depth=ln)
        cyl = bpy.context.object
        cyl.rotation_euler = (math.radians(90), 0, 0)
        cyl.parent = arm
        cyl.parent_type = "BONE"
        cyl.parent_bone = b.name
        cyl.location = (0, -ln / 2, 0)  # bone-parented children start at the tail
        cyl.data.materials.append(m)
        # joint sphere at bone head
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=r * 1.1 / arm.scale[0])
        sp = bpy.context.object
        sp.parent = arm
        sp.parent_type = "BONE"
        sp.parent_bone = b.name
        sp.location = (0, -ln, 0)
        sp.data.materials.append(m)


def follow_rig(arm):
    # empty that follows the hips on the ground plane (XY only)
    bpy.ops.object.empty_add(location=(0, 0, 0))
    e = bpy.context.object
    c = e.constraints.new("COPY_LOCATION")
    c.target = arm
    c.subtarget = arm.pose.bones[0].name
    c.use_z = False
    return e


CAM_DEFS = {
    # name: (offset from follow point, look-at height, lens mm)
    "front": (Vector((0.0, -4.2, 1.1)), 0.9, 40),
    "side": (Vector((4.2, 0.0, 1.1)), 0.9, 40),
    "q34": (Vector((3.0, -3.0, 1.6)), 0.85, 40),
    "feet": (Vector((2.0, 0.0, 0.35)), 0.25, 35),
    "top": (Vector((0.0, -0.01, 5.0)), 0.0, 35),
}


def make_cam(name, follow):
    off, look_h, lens = CAM_DEFS[name]
    bpy.ops.object.camera_add(location=off)
    cam = bpy.context.object
    cam.name = "cam_" + name
    cam.data.lens = lens
    cam.parent = follow
    bpy.ops.object.empty_add(location=(0, 0, look_h))
    tgt = bpy.context.object
    tgt.parent = follow
    t = cam.constraints.new("TRACK_TO")
    t.target = tgt
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"
    return cam


def render_clip(path):
    clip = os.path.splitext(os.path.basename(path))[0]
    clear()
    setup_world()
    arm = import_bvh(path)
    capsule_figure(arm)
    follow = follow_rig(arm)
    sc = bpy.context.scene
    fps = sc.render.fps / sc.render.fps_base
    end = min(sc.frame_end, sc.frame_start + int(MAX_SEC * fps))
    frames = list(range(sc.frame_start, end + 1, STEP))
    log(clip, "fps", fps, "frames", len(frames), "bones", len(arm.pose.bones))
    for cname in CAMS:
        cam = make_cam(cname, follow)
        sc.camera = cam
        d = os.path.join(OUT, clip, cname)
        os.makedirs(d, exist_ok=True)
        for i, f in enumerate(frames):
            sc.frame_set(f)
            sc.render.filepath = os.path.join(d, "%04d.png" % i)
            bpy.ops.render.render(write_still=True)
        log(clip, cname, "done")
    with open(os.path.join(OUT, clip, "info.txt"), "w") as fh:
        fh.write("clip=%s\nsrc_fps=%g\nstep=%d\nout_fps=%g\nframes=%d\n"
                 % (clip, fps, STEP, fps / STEP, len(frames)))
        fh.write("bones=" + ",".join(pb.name for pb in arm.pose.bones) + "\n")


for p in CLIPS:
    render_clip(p)
log("all done")
