# Blender headless render of exported joint positions (data/*.json: bones, parents, clips -> frames of xyz).
# Usage: blender -b -P blender/render_joints.py -- <clips.json> <out_dir>
# Env: CLIPS (comma list, default all), LOOPS (gait repeats, default 3), MAX_FRAMES (default 150), RES, CAMS
import json
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
RES = int(os.environ.get("RES", "360"))
CAMS = os.environ.get("CAMS", "front,side,q34,feet").split(",")
LOOPS = int(os.environ.get("LOOPS", "3"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "150"))
D = json.load(open(SRC))
WANT = [c for c in os.environ.get("CLIPS", "").split(",") if c] or list(D["clips"])
BONES, PARENTS = D["bones"], D["parents"]


def log(*a):
    print("[lab]", *a, flush=True)


def to_b(p):  # unity (x, y up, z fwd, left-handed) -> blender (x, y fwd, z up)
    return Vector((p[0], p[2], p[1]))


def mat(name, rgb, checker=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.7
    if checker:
        ch = nt.nodes.new("ShaderNodeTexChecker")
        ch.inputs["Scale"].default_value = 120.0  # 0.5 m squares on the 60 m plane
        ch.inputs["Color1"].default_value = (0.42, 0.44, 0.47, 1)
        ch.inputs["Color2"].default_value = (0.30, 0.32, 0.35, 1)
        nt.links.new(ch.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    return m


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 2
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.10, 0.12, 0.16, 1)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
    bpy.context.object.data.energy = 3.0
    bpy.ops.mesh.primitive_plane_add(size=60)
    bpy.context.object.data.materials.append(mat("floor", None, checker=True))


def radius(name):
    if name.startswith("spine") or name == "hips":
        return 0.085
    if name in ("neck",):
        return 0.045
    if name.startswith(("hand", "finger", "toe")):
        return 0.03
    if name.startswith(("thigh",)):
        return 0.065
    if name.startswith(("calf", "upperarm")):
        return 0.05
    return 0.042


def build_figure():
    body = mat("body", (0.85, 0.45, 0.2))
    left = mat("left", (0.25, 0.55, 0.9))
    segs = []
    for i, p in enumerate(PARENTS):
        if p < 0 or BONES[p] == "root":
            continue
        n = BONES[i]
        m = left if n.endswith("_l") else body
        r = radius(n if not n.startswith(("thigh", "clavicle")) else n)
        if n.startswith(("calf", "foot", "toe")):
            r = radius(BONES[p])
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=1.0, depth=1.0)
        cyl = bpy.context.object
        cyl.data.materials.append(m)
        cyl["r"] = r
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=r * 1.1)
        sp = bpy.context.object
        sp.data.materials.append(m)
        segs.append((p, i, cyl, sp))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.11)
    head = bpy.context.object
    head.data.materials.append(body)
    head.scale = (0.85, 0.95, 1.1)
    return segs, head


def pose(frame_pts, segs, head, offset):
    P = [to_b(p) + offset for p in frame_pts]
    for p, i, cyl, sp in segs:
        a, b = P[p], P[i]
        d = b - a
        L = max(d.length, 1e-4)
        r = cyl["r"]
        cyl.location = (a + b) / 2
        cyl.rotation_mode = "QUATERNION"
        cyl.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
        cyl.scale = (r, r, L)
        sp.location = b
    hi, ni = BONES.index("head"), BONES.index("neck")
    up = (P[hi] - P[ni]).normalized()
    head.location = P[hi] + up * 0.09
    head.rotation_mode = "QUATERNION"
    head.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(up)


CAM_DEFS = {
    "front": (Vector((0.0, 3.2, 1.0)), 0.85, 40),
    "side": (Vector((3.2, 0.0, 1.0)), 0.85, 40),
    "q34": (Vector((2.3, 2.3, 1.5)), 0.8, 40),
    "feet": (Vector((1.5, 0.3, 0.3)), 0.15, 35),
    "back": (Vector((0.0, -3.2, 1.2)), 0.85, 40),
}


def make_cams():
    bpy.ops.object.empty_add()
    follow = bpy.context.object
    cams = {}
    for name in CAMS:
        off, look_h, lens = CAM_DEFS[name]
        bpy.ops.object.camera_add(location=off)
        cam = bpy.context.object
        cam.data.lens = lens
        cam.parent = follow
        bpy.ops.object.empty_add(location=(0, 0, look_h))
        tgt = bpy.context.object
        tgt.parent = follow
        t = cam.constraints.new("TRACK_TO")
        t.target = tgt
        t.track_axis = "TRACK_NEGATIVE_Z"
        t.up_axis = "UP_Y"
        cams[name] = cam
    return follow, cams


def render_clip(name):
    clip = D["clips"][name]
    frames = clip["frames"]
    speed = clip.get("speed", 0.0)
    th = math.radians(clip.get("dir", 0.0))  # travel direction: 0 ahead (+y in Blender), 90 right (+x... mirrored)
    # unity x is blender x: right is +x
    fps = D["fps"]
    seq = frames * (LOOPS if speed > 0 else 1)
    seq = seq[:MAX_FRAMES]
    setup()
    segs, head = build_figure()
    follow, cams = make_cams()
    hips = BONES.index("hips")
    # ground: the lowest joint over the clip sits 4 cm up (ankle/toe joints are inside the foot)
    lo = min(min(p[1] for p in f) for f in frames)
    for cname, cam in cams.items():
        bpy.context.scene.camera = cam
        d = os.path.join(OUT, name, cname)
        os.makedirs(d, exist_ok=True)
        for k, f in enumerate(seq):
            dist = speed * k / fps
            off = Vector((dist * math.sin(th), dist * math.cos(th), 0.04 - lo))  # travel at the clip's speed
            pose(f, segs, head, off)
            hp = to_b(f[hips]) + off
            follow.location = (hp.x, hp.y, 0)
            if speed > 0:
                follow.location = (off.x, off.y, 0)  # steady camera: sliding feet show against the floor
            bpy.context.view_layer.update()
            bpy.context.scene.render.filepath = os.path.join(d, "%04d.png" % k)
            bpy.ops.render.render(write_still=True)
        log(name, cname, len(seq))
    with open(os.path.join(OUT, name, "info.txt"), "w") as fh:
        fh.write(json.dumps({k: v for k, v in clip.items() if k != "frames"}) + "\n")


for c in WANT:
    render_clip(c)
log("all done")
