"""Procedural, game-ready stylized character builder for Blender 4.x (no AI, 100% free).

Pipeline (each step is a real game-art technique, see docs/research.md):
  1. Blockout body with a Skin modifier on a joint graph  -> manifold, riggable base mesh
  2. Hard-surface props (armour, weapons) from primitives + bevel/solidify modifiers
  3. Procedural "hand-painted" materials (noise variation, top-down gradient, edge highlights)
  4. Armature from the same joint graph, auto weights for the body, rigid weights for props
  5. Smart-UV + Cycles bake -> one texture set (BaseColor w/ AO, ORM, Emissive) = 1 draw call
  6. Idle + action animations, export glTF binary (.glb)

Usage:
  blender -b --factory-startup -P blender/build_character.py -- --char anvil \
      --out assets/models/blender/anvil.glb [--tex 2048]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

# ----------------------------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------------------------

def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # sRGB -> linear (Blender colour sockets are scene-linear)
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False  # distro Blender builds ship without OIDN


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def apply_modifiers(obj) -> None:
    """Bake the modifier stack into the mesh (works headless, no operator context needed)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)


def apply_transform(obj) -> None:
    bpy.context.view_layer.update()  # matrix_world is stale until the depsgraph updates
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)


def shade(obj, smooth=True, angle=40.0) -> None:
    for p in obj.data.polygons:
        p.use_smooth = smooth
    if hasattr(obj.data, "use_auto_smooth"):  # Blender <= 4.0
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = math.radians(angle)


def mesh_from_bmesh(name: str, bm: bmesh.types.BMesh):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def ellipsoid(name, center, scale, mat, seg=24, rings=16, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    obj = mesh_from_bmesh(name, bm)
    obj.scale = scale
    obj.rotation_euler = Euler(rot)
    obj.location = center
    apply_transform(obj)
    set_mat(obj, mat)
    shade(obj, True, 180)
    return obj


def cyl_between(name, p1, p2, r1, r2, mat, seg=16, cap=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=d.length)
    obj = mesh_from_bmesh(name, bm)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    obj.matrix_world = Matrix.Translation((p1 + p2) / 2) @ q.to_matrix().to_4x4()
    apply_transform(obj)
    set_mat(obj, mat)
    shade(obj, True, 50)
    return obj


def rounded_box(name, center, size, mat, bevel=0.02, segs=3, rot=(0, 0, 0), taper_bottom=1.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:  # size = half extents
        v.co.x *= size[0] * 2
        v.co.y *= size[1] * 2
        v.co.z *= size[2] * 2
        if v.co.z < 0:
            v.co.x *= taper_bottom
    obj = mesh_from_bmesh(name, bm)
    obj.rotation_euler = Euler(rot)
    obj.location = center
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = segs
    mod.limit_method = "NONE"
    apply_modifiers(obj)
    apply_transform(obj)
    set_mat(obj, mat)
    shade(obj, True, 35)
    return obj


def torus(name, center, major, minor, mat, rot=(0, 0, 0), scale=(1, 1, 1), seg=32, mseg=10):
    bpy.ops.mesh.primitive_torus_add(major_segments=seg, minor_segments=mseg,
                                     major_radius=major, minor_radius=minor)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = Euler(rot)
    obj.location = center
    apply_transform(obj)
    set_mat(obj, mat)
    shade(obj, True, 180)
    return obj


def corset(p1, p2, mat):
    obj = cyl_between("corset", p1, p2, 0.128, 0.15, mat, 24)
    for v in obj.data.vertices:
        v.co.y = v.co.y * 0.8 - 0.004
        k = (v.co.z - p1[2]) / (p2[2] - p1[2])  # pinch the waist a little
        v.co.x *= 1.0 - 0.12 * math.sin(math.pi * min(1.0, k * 1.6))
    bev = obj.modifiers.new("bevel", "BEVEL")
    bev.width = 0.01
    bev.segments = 2
    apply_modifiers(obj)
    shade(obj, True, 60)
    return obj


def set_mat(obj, mat, extra=()):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for m in extra:
        obj.data.materials.append(m)


def solidify(obj, thickness, rim_mat_offset=None):
    mod = obj.modifiers.new("solid", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 0
    if rim_mat_offset is not None:
        mod.material_offset_rim = rim_mat_offset
    return mod


def subsurf(obj, levels=1):
    mod = obj.modifiers.new("subd", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    return mod


# ----------------------------------------------------------------------------------------
# procedural "hand-painted" PBR material
# ----------------------------------------------------------------------------------------
CHANNELS = {}  # material name -> dict(color=<socket>, rough=float, metal=float, emit=(rgb, strength))
# Art-style profile; other recipe modules (e.g. build_anime.py) override it before main().
STYLE = {"gradient": (0.78, 1.08), "ao_in_albedo": 0.45, "normal_map": True, "coat": 0.0}
# vertex-group name -> eye centre z; parts tagged with tag_blink() get squashed in a "Blink" shape key
BLINK = {}


def tag_blink(obj, side, zc):
    vg = obj.vertex_groups.new(name=f"blink.{side}")
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    BLINK[f"blink.{side}"] = zc
    return obj


def add_bump(nt, bsdf, kind, strength):
    """Procedural surface detail -> baked into a tangent-space normal map later (no extra polygons)."""
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")

    def wave(direction, scale, distortion=0.0, detail=2.0):
        w = nodes.new("ShaderNodeTexWave")
        w.wave_type = "BANDS"
        w.bands_direction = direction
        w.inputs["Scale"].default_value = scale
        w.inputs["Distortion"].default_value = distortion
        w.inputs["Detail"].default_value = detail
        links.new(tc.outputs["Object"], w.inputs["Vector"])
        return w.outputs["Fac"]

    if kind == "metal":  # hammered dents
        t = nodes.new("ShaderNodeTexVoronoi")
        t.inputs["Scale"].default_value = 26.0
        links.new(tc.outputs["Object"], t.inputs["Vector"])
        h = t.outputs["Distance"]
    elif kind == "cloth":  # woven threads
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        links.new(wave("X", 140.0), mul.inputs[0])
        links.new(wave("Z", 140.0), mul.inputs[1])
        h = mul.outputs[0]
    elif kind == "leather":  # pebbled grain
        t = nodes.new("ShaderNodeTexNoise")
        t.inputs["Scale"].default_value = 90.0
        t.inputs["Detail"].default_value = 6.0
        links.new(tc.outputs["Object"], t.inputs["Vector"])
        h = t.outputs["Fac"]
    elif kind == "wood":  # long grain along the handle
        h = wave("Z", 7.0, distortion=9.0, detail=4.0)
    elif kind == "hair":  # strands
        h = wave("Z", 45.0, distortion=3.0)
    else:
        return
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.004
    links.new(h, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def make_mat(name, color, rough=0.6, metal=0.0, noise=0.10, noise_scale=6.0,
             edge=0.0, emit_strength=0.0, height=1.8, bump=None, bump_strength=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    base = Vector(hex_rgb(color))

    # 1) low-frequency colour variation (fake brush strokes)
    tc = nodes.new("ShaderNodeTexCoord")
    noise_n = nodes.new("ShaderNodeTexNoise")
    noise_n.inputs["Scale"].default_value = noise_scale
    noise_n.inputs["Detail"].default_value = 3.0
    noise_n.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], noise_n.inputs["Vector"])
    var = nodes.new("ShaderNodeMix")
    var.data_type = "RGBA"
    var.inputs[6].default_value = (*[c * (1 - noise) for c in base], 1)
    var.inputs[7].default_value = (*[min(1.0, c * (1 + noise)) for c in base], 1)
    links.new(noise_n.outputs["Fac"], var.inputs[0])
    col_out = var.outputs[2]

    # 2) top-down gradient (hand-painted games light the top of forms in the albedo)
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs[0])
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = height
    mr.inputs["To Min"].default_value = STYLE["gradient"][0]
    mr.inputs["To Max"].default_value = STYLE["gradient"][1]
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    grad = nodes.new("ShaderNodeMix")
    grad.data_type = "RGBA"
    grad.blend_type = "MULTIPLY"
    grad.inputs[0].default_value = 1.0
    links.new(col_out, grad.inputs[6])
    comb = nodes.new("ShaderNodeCombineXYZ")
    for k in "XYZ":
        links.new(mr.outputs["Result"], comb.inputs[k])
    links.new(comb.outputs[0], grad.inputs[7])
    col_out = grad.outputs[2]

    # 3) edge highlight from mesh curvature (pointiness) - classic hand-painted metal wear
    if edge > 0:
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.52
        ramp.color_ramp.elements[1].position = 0.60
        links.new(geo.outputs["Pointiness"], ramp.inputs["Fac"])
        hi = nodes.new("ShaderNodeMix")
        hi.data_type = "RGBA"
        hi.blend_type = "SCREEN"
        links.new(ramp.outputs["Color"], hi.inputs[0])
        links.new(col_out, hi.inputs[6])
        hi.inputs[7].default_value = (edge, edge, edge, 1)
        col_out = hi.outputs[2]

    links.new(col_out, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    emit = (0.0, 0.0, 0.0)
    if emit_strength > 0:
        emit = tuple(base)
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    if bump:
        add_bump(nt, bsdf, bump, bump_strength)
    CHANNELS[m.name] = dict(color=col_out, rough=rough, metal=metal, emit=emit,
                            emit_strength=emit_strength)
    return m


# ----------------------------------------------------------------------------------------
# skeleton / body
# ----------------------------------------------------------------------------------------
# bone name -> (head joint, tail joint, parent)
BONES = [
    ("hips", "hips", "spine", None),
    ("spine", "spine", "chest", "hips"),
    ("chest", "chest", "neck", "spine"),
    ("neck", "neck", "head", "chest"),
    ("head", "head", "head_top", "neck"),
]
for s in ("L", "R"):
    BONES += [
        (f"shoulder.{s}", "chest", f"shoulder.{s}", "chest"),
        (f"upper_arm.{s}", f"shoulder.{s}", f"elbow.{s}", f"shoulder.{s}"),
        (f"forearm.{s}", f"elbow.{s}", f"wrist.{s}", f"upper_arm.{s}"),
        (f"hand.{s}", f"wrist.{s}", f"hand_end.{s}", f"forearm.{s}"),
        (f"thigh.{s}", f"hip.{s}", f"knee.{s}", "hips"),
        (f"shin.{s}", f"knee.{s}", f"ankle.{s}", f"thigh.{s}"),
        (f"foot.{s}", f"ankle.{s}", f"toe.{s}", f"shin.{s}"),
    ]

# skin-modifier graph edges (body only; head and hands are separate meshes)
SKIN_EDGES = [("hips", "spine"), ("spine", "chest"), ("chest", "neck")]
for s in ("L", "R"):
    SKIN_EDGES += [("chest", f"shoulder.{s}"), (f"shoulder.{s}", f"elbow.{s}"),
                   (f"elbow.{s}", f"wrist.{s}"), ("hips", f"hip.{s}"),
                   (f"hip.{s}", f"knee.{s}"), (f"knee.{s}", f"ankle.{s}"),
                   (f"ankle.{s}", f"toe.{s}")]


def mirror_joints(j: dict) -> dict:
    out = dict(j)
    for k, v in j.items():
        if k.endswith(".L"):
            out[k[:-2] + ".R"] = (-v[0], v[1], v[2])
    return out


def build_body(J, R, mat):
    names = [n for n in J if n not in ("head", "head_top") and not n.startswith("hand_end")]
    idx = {n: i for i, n in enumerate(names)}
    me = bpy.data.meshes.new("body")
    me.from_pydata([J[n] for n in names], [(idx[a], idx[b]) for a, b in SKIN_EDGES], [])
    obj = link(bpy.data.objects.new("body", me))
    mod = obj.modifiers.new("skin", "SKIN")
    mod.branch_smoothing = 0.6
    mod.use_smooth_shade = True
    sk = obj.data.skin_vertices[0].data
    for n, i in idx.items():
        r = R.get(n, R.get(n.split(".")[0], (0.05, 0.05)))
        if isinstance(r, (int, float)):
            r = (r, r)
        sk[i].radius = r
        sk[i].use_root = n == "hips"
    subsurf(obj, 2)
    apply_modifiers(obj)
    set_mat(obj, mat)
    shade(obj, True, 180)
    return obj


def build_armature(J):
    arm_data = bpy.data.armatures.new("rig")
    arm = link(bpy.data.objects.new("rig", arm_data))
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    for name, h, t, parent in BONES:
        b = eb.new(name)
        b.head = J[h]
        b.tail = J[t]
        if (b.tail - b.head).length < 1e-3:
            b.tail = b.head + Vector((0, 0, 0.05))
        if parent:
            b.parent = eb[parent]
            b.use_connect = (Vector(J[h]) - eb[parent].tail).length < 1e-4
        b.roll = 0
        if name.split(".")[0] in ("upper_arm", "forearm", "hand"):
            # A-pose arms get a tilted roll-0 frame; pin local Z to world +Y so that
            # Z rotations always raise/lower the arm sideways and X swings it fore/aft.
            b.align_roll(Vector((0, 1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def rigid_group(obj, bone):
    vg = obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")


# ----------------------------------------------------------------------------------------
# character recipes
# ----------------------------------------------------------------------------------------

def recipe_anvil():
    H = 1.85
    J = mirror_joints({
        "hips": (0, 0, 0.92), "spine": (0, 0, 1.08), "chest": (0, 0, 1.28),
        "neck": (0, 0, 1.47), "head": (0, 0, 1.53), "head_top": (0, 0, 1.86),
        "shoulder.L": (0.19, 0, 1.40), "elbow.L": (0.41, 0.0, 1.15),
        "wrist.L": (0.55, -0.04, 0.92), "hand_end.L": (0.60, -0.06, 0.81),
        "hip.L": (0.11, 0, 0.86), "knee.L": (0.14, -0.02, 0.49),
        "ankle.L": (0.15, 0.02, 0.11), "toe.L": (0.15, -0.13, 0.05),
    })
    R = {"hips": (0.18, 0.15), "spine": (0.19, 0.15), "chest": (0.24, 0.18), "neck": 0.085,
         "shoulder": 0.10, "elbow": 0.075, "wrist": 0.06, "hip": 0.115, "knee": 0.085,
         "ankle": 0.065, "toe": 0.055}
    M = dict(
        skin=make_mat("skin", "#D9A07A", 0.6, noise=0.06, height=H),
        beard=make_mat("beard", "#5A3A22", 0.85, noise=0.18, noise_scale=30, height=H, bump="hair", bump_strength=0.5),
        steel=make_mat("steel", "#9EA7B2", 0.42, 0.9, noise=0.10, noise_scale=4, edge=0.35, height=H, bump="metal", bump_strength=0.18),
        brass=make_mat("brass", "#C9A045", 0.4, 0.9, noise=0.08, edge=0.25, height=H, bump="metal", bump_strength=0.12),
        crimson=make_mat("crimson", "#9A2B2B", 0.85, noise=0.12, noise_scale=12, height=H, bump="cloth", bump_strength=0.35),
        leather=make_mat("leather", "#5C3B24", 0.7, noise=0.14, noise_scale=14, height=H, bump="leather", bump_strength=0.3),
        wood=make_mat("wood", "#7A5233", 0.75, noise=0.18, noise_scale=20, height=H, bump="wood", bump_strength=0.45),
        cloth=make_mat("padded", "#4A3A30", 0.9, noise=0.10, noise_scale=16, height=H, bump="cloth", bump_strength=0.4),
        eye=make_mat("eye", "#1A1412", 0.15, noise=0.0, height=H),
        eye_white=make_mat("eye_white", "#F2EEE6", 0.3, noise=0.0, height=H),
        iris=make_mat("iris", "#5A3A1E", 0.2, noise=0.0, height=H),
        glint=make_mat("glint", "#FFFFFF", 0.1, noise=0.0, emit_strength=1.0, height=H),
    )
    parts = []  # (object, bone or None for auto)
    body = build_body(J, R, M["cloth"])
    parts.append((body, None))

    # --- head
    hc = Vector((0, -0.01, 1.63))
    parts += [
        (ellipsoid("head", hc, (0.14, 0.145, 0.16), M["skin"]), "head"),
        (ellipsoid("nose", hc + Vector((0, -0.145, -0.02)), (0.03, 0.03, 0.035), M["skin"], 12, 8), "head"),
        (ellipsoid("beard", hc + Vector((0, -0.07, -0.10)), (0.125, 0.10, 0.10), M["beard"]), "head"),
        (ellipsoid("moustache", hc + Vector((0, -0.135, -0.055)), (0.07, 0.025, 0.022), M["beard"], 16, 8), "head"),
    ]
    for sx in (-1, 1):
        parts += [
            (ellipsoid(f"eye{sx}", hc + Vector((0.05 * sx, -0.128, 0.02)), (0.022, 0.012, 0.019), M["eye_white"], 14, 8), "head"),
            (ellipsoid(f"iris{sx}", hc + Vector((0.048 * sx, -0.136, 0.019)), (0.011, 0.008, 0.013), M["iris"], 12, 8), "head"),
            (ellipsoid(f"glint{sx}", hc + Vector((0.044 * sx, -0.1435, 0.025)), (0.0035, 0.003, 0.0035), M["glint"], 8, 6), "head"),
            (rounded_box(f"brow{sx}", hc + Vector((0.052 * sx, -0.134, 0.058)), (0.035, 0.012, 0.010), M["beard"], 0.004, 2,
                         rot=(0, 0.25 * sx, 0)), "head"),
            (ellipsoid(f"ear{sx}", hc + Vector((0.14 * sx, 0.0, 0.0)), (0.02, 0.03, 0.04), M["skin"], 12, 8), "head"),
        ]
    # helmet: dome + brass rim + nose guard + crimson crest
    dome = ellipsoid("helmet", hc + Vector((0, 0.005, 0.035)), (0.165, 0.17, 0.165), M["steel"], 32, 16)
    bm = bmesh.new(); bm.from_mesh(dome.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < hc.z + 0.03], context="VERTS")
    bm.to_mesh(dome.data); bm.free()
    solidify(dome, 0.012); apply_modifiers(dome); shade(dome, True, 180)
    parts += [
        (dome, "head"),
        (torus("helmet_rim", hc + Vector((0, 0.005, 0.035)), 0.168, 0.016, M["brass"], scale=(1, 1.03, 1)), "head"),
        (rounded_box("nose_guard", hc + Vector((0, -0.17, 0.02)), (0.018, 0.01, 0.06), M["steel"], 0.006, 2), "head"),
        (rounded_box("crest", hc + Vector((0, 0.01, 0.20)), (0.025, 0.15, 0.06), M["crimson"], 0.02, 3), "head"),
    ]
    # --- torso armour
    parts += [
        (ellipsoid("chestplate", (0, -0.015, 1.27), (0.27, 0.215, 0.24), M["steel"], 32, 20), "chest"),
        (torus("gorget", (0, 0, 1.45), 0.11, 0.035, M["steel"], scale=(1, 0.9, 1)), "chest"),
        (torus("belt", (0, 0, 0.97), 0.195, 0.04, M["leather"], scale=(1, 0.82, 1.2)), "hips"),
        (rounded_box("buckle", (0, -0.2, 0.97), (0.05, 0.015, 0.045), M["brass"], 0.01), "hips"),
    ]
    for sy, nm in ((-1, "front"), (1, "back")):
        parts += [
            (rounded_box(f"tabard_{nm}", (0, 0.175 * sy, 0.72), (0.13, 0.012, 0.23), M["crimson"], 0.01, 2,
                         taper_bottom=1.25), "hips"),
            (rounded_box(f"tabard_trim_{nm}", (0, 0.168 * sy, 0.715), (0.142, 0.008, 0.24), M["brass"], 0.008, 2,
                         taper_bottom=1.25), "hips"),
        ]
    for s, sx in (("L", 1), ("R", -1)):
        sh = Vector(J[f"shoulder.{s}"])
        parts += [
            (ellipsoid(f"pauldron.{s}", sh + Vector((0.05 * sx, 0, 0.04)), (0.17, 0.18, 0.13), M["steel"], 28, 16,
                       rot=(0, -0.35 * sx, 0)), f"upper_arm.{s}"),
            (torus(f"pauldron_rim.{s}", sh + Vector((0.07 * sx, 0, -0.01)), 0.16, 0.018, M["brass"],
                   rot=(0, -0.35 * sx, 0), scale=(1, 1.08, 1)), f"upper_arm.{s}"),
            (ellipsoid(f"pauldron_low.{s}", sh + Vector((0.11 * sx, 0, -0.07)), (0.12, 0.14, 0.08), M["steel"], 24, 12,
                       rot=(0, -0.6 * sx, 0)), f"upper_arm.{s}"),
            *[(ellipsoid(f"rivet{k}.{s}", sh + Vector((0.07 * sx + 0.15 * sx * math.cos(a), 0.165 * math.sin(a), 0.0 - 0.05 * math.cos(a))),
                         (0.014, 0.014, 0.014), M["brass"], 8, 6), f"upper_arm.{s}")
              for k, a in enumerate((-1.2, 0.0, 1.2))],
            (cyl_between(f"gauntlet.{s}", J[f"elbow.{s}"], J[f"wrist.{s}"], 0.085, 0.072, M["steel"], 20), f"forearm.{s}"),
            (torus(f"cuff.{s}", J[f"elbow.{s}"], 0.085, 0.018, M["brass"],
                   rot=Vector((0, 0, 1)).rotation_difference(Vector(J[f"wrist.{s}"]) - Vector(J[f"elbow.{s}"])).to_euler()),
             f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (Vector(J[f"wrist.{s}"]) + Vector(J[f"hand_end.{s}"])) / 2, (0.055, 0.05, 0.07),
                       M["leather"], 16, 12), f"hand.{s}"),
            (ellipsoid(f"knee.{s}", Vector(J[f"knee.{s}"]) + Vector((0, -0.06, 0)), (0.075, 0.06, 0.07), M["steel"], 20, 12),
             f"shin.{s}"),
            (cyl_between(f"greave.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.06)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, 0.08)),
                         0.09, 0.075, M["steel"], 20), f"shin.{s}"),
            (rounded_box(f"boot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.05, -0.045)), (0.075, 0.15, 0.07), M["leather"],
                         0.04, 3), f"foot.{s}"),
        ]
    # --- shield on left forearm
    n = Vector((0.55, -0.83, 0.0)).normalized()
    q = Vector((0, 0, 1)).rotation_difference(n).to_euler()
    sc = Vector((0.60, -0.10, 1.03))
    parts += [
        (cyl_between("shield", sc - n * 0.03, sc + n * 0.03, 0.31, 0.31, M["wood"], 40), "forearm.L"),
        (torus("shield_rim", sc + n * 0.005, 0.31, 0.03, M["brass"], rot=q, seg=48), "forearm.L"),
        (cyl_between("shield_emblem", sc + n * 0.025, sc + n * 0.04, 0.19, 0.17, M["crimson"], 32), "forearm.L"),
        (ellipsoid("shield_boss", sc + n * 0.045, (0.075, 0.075, 0.045), M["steel"], 20, 10, rot=q), "forearm.L"),
    ]
    # --- war hammer in right hand, head resting on the ground
    hx, hy = -0.585, -0.055
    parts += [
        (cyl_between("hammer_handle", (hx, hy, 0.20), (hx, hy, 1.08), 0.022, 0.026, M["wood"], 12), "hand.R"),
        (ellipsoid("hammer_pommel", (hx, hy, 1.10), (0.035, 0.035, 0.035), M["brass"], 12, 8), "hand.R"),
        (rounded_box("hammer_head", (hx, hy, 0.13), (0.11, 0.19, 0.11), M["steel"], 0.025, 3), "hand.R"),
        (rounded_box("hammer_band", (hx, hy, 0.13), (0.115, 0.03, 0.115), M["brass"], 0.01, 2), "hand.R"),
    ]
    actions = {"Idle": idle_keys, "Attack": anvil_attack_keys}
    return J, R, M, parts, H, actions


def recipe_verdant():
    H = 2.05  # staff reaches above the head
    J = mirror_joints({
        "hips": (0, 0, 0.95), "spine": (0, 0, 1.10), "chest": (0, 0, 1.27),
        "neck": (0, 0, 1.43), "head": (0, 0, 1.48), "head_top": (0, 0, 1.76),
        "shoulder.L": (0.14, 0, 1.37), "elbow.L": (0.31, 0.01, 1.14),
        "wrist.L": (0.43, -0.03, 0.92), "hand_end.L": (0.47, -0.05, 0.84),
        "hip.L": (0.085, 0, 0.90), "knee.L": (0.10, -0.02, 0.50),
        "ankle.L": (0.105, 0.02, 0.09), "toe.L": (0.105, -0.11, 0.03),
    })
    R = {"hips": (0.145, 0.11), "spine": (0.115, 0.09), "chest": (0.145, 0.105), "neck": 0.05,
         "shoulder": 0.06, "elbow": 0.045, "wrist": 0.038, "hip": 0.085, "knee": 0.058,
         "ankle": 0.045, "toe": 0.04}
    M = dict(
        skin=make_mat("skin", "#EDBE9C", 0.55, noise=0.05, height=H),
        hair=make_mat("hair", "#8A3B22", 0.6, noise=0.2, noise_scale=40, height=H, bump="hair", bump_strength=0.5),
        cloak=make_mat("cloak", "#1F6F5C", 0.8, noise=0.14, noise_scale=8, height=H, bump="cloth", bump_strength=0.35),
        gold=make_mat("gold", "#D8B45A", 0.38, 0.9, noise=0.08, edge=0.3, height=H, bump="metal", bump_strength=0.1),
        leather=make_mat("leather", "#6B4A2F", 0.65, noise=0.14, noise_scale=14, height=H, bump="leather", bump_strength=0.3),
        tights=make_mat("tights", "#2E3B35", 0.85, noise=0.08, noise_scale=10, height=H, bump="cloth", bump_strength=0.3),
        wood=make_mat("wood", "#6E4A2E", 0.75, noise=0.2, noise_scale=24, height=H, bump="wood", bump_strength=0.45),
        eye_white=make_mat("eye_white", "#F2EEE6", 0.3, noise=0.0, height=H),
        iris=make_mat("iris", "#2F7A55", 0.2, noise=0.0, height=H),
        glint=make_mat("glint", "#FFFFFF", 0.1, noise=0.0, emit_strength=1.0, height=H),
        lip=make_mat("lip", "#B25A4C", 0.5, noise=0.0, height=H),
        crystal=make_mat("crystal", "#5FF2E6", 0.1, noise=0.05, emit_strength=2.0, height=H),
        eye=make_mat("eye", "#1F3A33", 0.12, noise=0.0, height=H),
    )
    parts = []
    body = build_body(J, R, M["tights"])
    parts.append((body, None))

    hc = Vector((0, -0.005, 1.585))
    parts += [
        (ellipsoid("head", hc, (0.12, 0.125, 0.14), M["skin"]), "head"),
        (ellipsoid("nose", hc + Vector((0, -0.124, -0.02)), (0.018, 0.02, 0.022), M["skin"], 12, 8), "head"),
        (ellipsoid("bangs", hc + Vector((0, -0.085, 0.085)), (0.115, 0.06, 0.05), M["hair"], 20, 10, rot=(0.35, 0, 0)), "head"),
        (ellipsoid("hair_back", hc + Vector((0, 0.045, 0.0)), (0.125, 0.11, 0.15), M["hair"]), "head"),
        (ellipsoid("braid", hc + Vector((0.11, -0.05, -0.15)), (0.03, 0.03, 0.09), M["hair"], 12, 10), "head"),
        (ellipsoid("mouth", hc + Vector((0, -0.117, -0.062)), (0.017, 0.006, 0.0055), M["lip"], 12, 6), "head"),
    ]
    for sx in (-1, 1):
        parts += [
            (ellipsoid(f"eye{sx}", hc + Vector((0.045 * sx, -0.108, 0.01)), (0.024, 0.012, 0.027), M["eye_white"], 14, 8), "head"),
            (ellipsoid(f"iris{sx}", hc + Vector((0.043 * sx, -0.117, 0.008)), (0.014, 0.008, 0.019), M["iris"], 12, 8), "head"),
            (ellipsoid(f"pupil{sx}", hc + Vector((0.043 * sx, -0.1225, 0.008)), (0.007, 0.004, 0.01), M["eye"], 10, 6), "head"),
            (ellipsoid(f"glint{sx}", hc + Vector((0.038 * sx, -0.1255, 0.016)), (0.0045, 0.003, 0.0045), M["glint"], 8, 6), "head"),
            (rounded_box(f"brow{sx}", hc + Vector((0.047 * sx, -0.116, 0.052)), (0.028, 0.008, 0.006), M["hair"], 0.003, 2,
                         rot=(0, -0.2 * sx, 0)), "head"),
        ]
    # hood: sphere shell, face opening cut, peaked tip pulled back
    hood = ellipsoid("hood", hc + Vector((0, 0.03, 0.03)), (0.16, 0.175, 0.185), M["cloak"], 32, 20)
    bm = bmesh.new(); bm.from_mesh(hood.data)
    cz = hc.z + 0.03
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co.y < hc.y - 0.02 and v.co.z < cz + 0.11) or v.co.z < cz - 0.17],
                     context="VERTS")
    for v in bm.verts:
        t = max(0.0, (v.co.z - cz) / 0.185)
        b = max(0.0, (v.co.y - hc.y) / 0.2)
        v.co.y += 0.16 * t ** 2 * (0.3 + b)
        v.co.z += 0.02 * t ** 2 - 0.05 * (t * b) ** 2
    bm.to_mesh(hood.data); bm.free()
    hood.data.materials.append(M["gold"])
    solidify(hood, 0.014, rim_mat_offset=1); subsurf(hood, 1); apply_modifiers(hood); shade(hood, True, 180)
    parts.append((hood, "head"))

    # cloak: back-half cone shell with gold rim
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=0.40, radius2=0.17, depth=1.05)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0.02, 0.88))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.03], context="FACES")
    for v in bm.verts:  # gentle cloth folds
        a = math.atan2(v.co.y, v.co.x)
        v.co.y += 0.012 * math.sin(a * 9) * (1.4 - v.co.z)
    cloak = mesh_from_bmesh("cloak", bm)
    set_mat(cloak, M["cloak"], [M["gold"]])
    solidify(cloak, 0.014, rim_mat_offset=1); subsurf(cloak, 1); apply_modifiers(cloak); shade(cloak, True, 180)
    parts.append((cloak, "chest"))
    # capelet: short shoulder cape over the cloak -> reads as "hooded cloak" in silhouette (v2)
    cap = ellipsoid("capelet", (0, 0.01, 1.20), (0.30, 0.22, 0.25), M["cloak"], 40, 24)
    bm = bmesh.new(); bm.from_mesh(cap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 1.16 or v.co.z > 1.445], context="VERTS")
    for v in bm.verts:  # soft folds + slightly longer at the back
        a = math.atan2(v.co.y, v.co.x)
        k = max(0.0, (1.30 - v.co.z) / 0.14)
        v.co.x += 0.012 * math.cos(a) * math.sin(a * 10) * k
        v.co.y += 0.012 * math.sin(a) * math.sin(a * 10) * k
        if v.co.y > 0:
            v.co.z -= 0.05 * k * (v.co.y / 0.22)
    bm.to_mesh(cap.data); bm.free()
    cap.data.materials.append(M["gold"])
    solidify(cap, 0.012, rim_mat_offset=1); subsurf(cap, 1); apply_modifiers(cap); shade(cap, True, 180)
    parts.append((cap, "chest"))
    parts.append((ellipsoid("clasp", (0, -0.2, 1.33), (0.03, 0.02, 0.03), M["gold"], 16, 10), "chest"))

    # bodice, belt, skirt
    parts += [
        (corset((0, 0, 0.98), (0, 0, 1.33), M["leather"]), "chest"),
        (torus("belt", (0, 0, 0.99), 0.145, 0.025, M["leather"], scale=(1, 0.8, 1.2)), "hips"),
        (rounded_box("buckle", (0, -0.12, 0.99), (0.03, 0.01, 0.028), M["gold"], 0.006), "hips"),
        (rounded_box("pouch", (0.13, -0.06, 0.95), (0.04, 0.03, 0.045), M["leather"], 0.015, 3, rot=(0, 0, 0.5)), "hips"),
    ]
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.25, radius2=0.155, depth=0.36)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.80))
    for v in bm.verts:
        v.co.y *= 0.82
    skirt = mesh_from_bmesh("skirt", bm)
    set_mat(skirt, M["cloak"], [M["gold"]])
    solidify(skirt, 0.012, rim_mat_offset=1); subsurf(skirt, 1); apply_modifiers(skirt); shade(skirt, True, 180)
    parts.append((skirt, "hips"))

    for s, sx in (("L", 1), ("R", -1)):
        parts += [
            (cyl_between(f"bracer.{s}", Vector(J[f"elbow.{s}"]).lerp(Vector(J[f"wrist.{s}"]), 0.25), J[f"wrist.{s}"],
                         0.05, 0.044, M["leather"], 16), f"forearm.{s}"),
            (torus(f"bracer_ring.{s}", J[f"wrist.{s}"], 0.044, 0.008, M["gold"],
                   rot=Vector((0, 0, 1)).rotation_difference(Vector(J[f"wrist.{s}"]) - Vector(J[f"elbow.{s}"])).to_euler()),
             f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (Vector(J[f"wrist.{s}"]) + Vector(J[f"hand_end.{s}"])) / 2, (0.038, 0.034, 0.055),
                       M["skin"], 16, 12), f"hand.{s}"),
            (cyl_between(f"boot.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.03)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, -0.02)),
                         0.066, 0.052, M["leather"], 18), f"shin.{s}"),
            (torus(f"boot_cuff.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.03)), 0.066, 0.012, M["leather"]), f"shin.{s}"),
            (rounded_box(f"boot_foot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.04, -0.045)), (0.05, 0.11, 0.045),
                         M["leather"], 0.03, 3), f"foot.{s}"),
        ]
    # staff with crystal
    sx_, sy_ = -0.455, -0.045
    parts += [
        (cyl_between("staff", (sx_, sy_, 0.0), (sx_, sy_, 1.78), 0.02, 0.026, M["wood"], 12), "hand.R"),
        (torus("staff_ring_a", (sx_, sy_, 1.70), 0.03, 0.008, M["gold"]), "hand.R"),
        (torus("staff_ring_b", (sx_, sy_, 1.05), 0.026, 0.007, M["gold"]), "hand.R"),
        (torus("staff_crescent", (sx_, sy_, 1.91), 0.10, 0.014, M["gold"], rot=(math.pi / 2, 0, 0), seg=36), "hand.R"),
        (ellipsoid("crystal", (sx_, sy_, 1.91), (0.045, 0.045, 0.085), M["crystal"], 6, 4), "hand.R"),
    ]
    actions = {"Idle": idle_keys, "Cast": verdant_cast_keys}
    return J, R, M, parts, H, actions


# ----------------------------------------------------------------------------------------
# animation
# ----------------------------------------------------------------------------------------

ARM_BONES = ("upper_arm", "forearm", "hand")
# rest frame of an arm hanging straight down: local X = world X, local Y (bone) = world -Z, local Z = world +Y
_ARM_CANON = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
_last_quat = {}


def key_rot(pb, frame, x=0.0, y=0.0, z=0.0):
    e = Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ")
    if pb.name.split(".")[0] not in ARM_BONES:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = e
        pb.keyframe_insert("rotation_euler", frame=frame)
        return
    # Arm clips are authored for arms hanging at the sides. Re-express the rotation about world axes
    # (conjugate by the rest frame) so A-pose rigs (chibi, AI meshes) swing/raise the same way.
    B = pb.bone.matrix_local.to_3x3()
    K = _ARM_CANON.inverted() @ B
    q = (K.inverted() @ e.to_matrix() @ K).to_quaternion()
    act = pb.id_data.animation_data.action if pb.id_data.animation_data else None
    key = (act.name if act else "", pb.name)
    prev = _last_quat.get(key)
    if prev is not None and prev.dot(q) < 0:
        q.negate()
    _last_quat[key] = q.copy()
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = q
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)


def key_loc(pb, frame, v):
    pb.location = v
    pb.keyframe_insert("location", frame=frame)


def idle_keys(arm):
    P = arm.pose.bones
    for f, k in ((1, 0.0), (31, 1.0), (61, 0.0)):
        key_loc(P["hips"], f, (0, 0, -0.012 * k))  # bone-local Y is up the chain; tiny bob
        key_rot(P["chest"], f, x=-2.5 * k)
        key_rot(P["head"], f, x=2.0 * k, z=1.5 * k)
        for s, sx in (("L", 1), ("R", -1)):
            key_rot(P[f"upper_arm.{s}"], f, x=3 * k, z=2 * k * sx)
            key_rot(P[f"forearm.{s}"], f, x=-3 * k)


# ---- shared base animation library (all characters use the same 19-bone naming) ----------
# Axis conventions measured on the rig (front = -Y): thigh/shin/upper_arm/forearm +X swing backward
# (so forward = -X, knee flexion = +X, elbow flexion = -X); spine/chest/head +X lean forward;
# upper_arm.L -Z / upper_arm.R +Z raise the arm sideways; hips location +Y = up (root motion).

def _leg_len(arm):
    b = arm.data.bones
    return b["thigh.L"].length + b["shin.L"].length


def _cycle(n, step=2):
    return [(1 + i, 2 * math.pi * i / n) for i in range(0, n + 1, step)]


def walk_keys(arm):
    P, L = arm.pose.bones, _leg_len(arm)
    for f, ph in _cycle(24):
        s, c = math.sin(ph), math.cos(ph)
        key_rot(P["thigh.L"], f, x=-26 * s)
        key_rot(P["thigh.R"], f, x=26 * s)
        key_rot(P["shin.L"], f, x=6 + 42 * max(0.0, c))
        key_rot(P["shin.R"], f, x=6 + 42 * max(0.0, -c))
        key_rot(P["foot.L"], f, x=-8 * s)
        key_rot(P["foot.R"], f, x=8 * s)
        key_rot(P["upper_arm.L"], f, x=22 * s, z=14)
        key_rot(P["upper_arm.R"], f, x=-22 * s, z=-14)
        key_rot(P["forearm.L"], f, x=-12 - 14 * max(0.0, -s))
        key_rot(P["forearm.R"], f, x=-12 - 14 * max(0.0, s))
        key_rot(P["spine"], f, x=3, y=-5 * s)
        key_rot(P["chest"], f, y=9 * s)
        key_rot(P["head"], f, y=-5 * s)
        key_loc(P["hips"], f, (0, 0.025 * L * math.cos(2 * ph) - 0.015 * L, 0))


def run_keys(arm):
    P, L = arm.pose.bones, _leg_len(arm)
    for f, ph in _cycle(16):
        s, c = math.sin(ph), math.cos(ph)
        key_rot(P["thigh.L"], f, x=-15 - 40 * s)
        key_rot(P["thigh.R"], f, x=-15 + 40 * s)
        key_rot(P["shin.L"], f, x=25 + 70 * max(0.0, c))
        key_rot(P["shin.R"], f, x=25 + 70 * max(0.0, -c))
        key_rot(P["upper_arm.L"], f, x=38 * s, z=22)
        key_rot(P["upper_arm.R"], f, x=-38 * s, z=-22)
        key_rot(P["forearm.L"], f, x=-75)
        key_rot(P["forearm.R"], f, x=-75)
        key_rot(P["spine"], f, x=12, y=-7 * s)
        key_rot(P["chest"], f, x=6, y=12 * s)
        key_rot(P["head"], f, x=-12)
        key_loc(P["hips"], f, (0, 0.06 * L * abs(math.cos(ph)) - 0.05 * L, 0.0))


def jump_keys(arm):
    P, L = arm.pose.bones, _leg_len(arm)
    #       frame, hip_up, thigh, shin, foot, spine, arm_x, arm_raise, elbow
    seq = [(1, 0.0, 0, 0, 0, 0, 0, 0, 0),
           (9, -0.22, -55, 95, -35, 22, 45, 0, -20),      # crouch, arms back
           (13, 0.1, -5, 5, 20, -5, -120, 25, -10),       # take-off, arms up
           (19, 0.55, -55, 95, 0, 8, -140, 35, -30),      # apex, legs tucked
           (26, 0.05, -15, 20, 10, 0, -40, 20, -20),      # falling
           (30, -0.18, -50, 85, -30, 18, 20, 15, -25),    # landing absorb
           (40, 0.0, 0, 0, 0, 0, 0, 0, 0)]
    for f, up, th, sh, ft, sp, ax, ar, el in seq:
        for s, sx in (("L", 1), ("R", -1)):
            key_rot(P[f"thigh.{s}"], f, x=th)
            key_rot(P[f"shin.{s}"], f, x=sh)
            key_rot(P[f"foot.{s}"], f, x=ft)
            key_rot(P[f"upper_arm.{s}"], f, x=ax, z=-ar * sx)
            key_rot(P[f"forearm.{s}"], f, x=el)
        key_rot(P["spine"], f, x=sp)
        key_rot(P["head"], f, x=-sp * 0.6)
        key_loc(P["hips"], f, (0, up * L, 0))


def wave_keys(arm, side="R"):
    P = arm.pose.bones
    sz = 1 if side == "R" else -1  # raising is +Z on the right arm, -Z on the left
    d = P[f"upper_arm.{side}"].bone.vector.normalized()
    # chibi arms are shorter than the head is tall: an overhead wave would hide the hand inside the head,
    # so wave lower and further out as the arm/head ratio drops (anvil ~1.7, chibi ~0.5)
    ratio = (P[f"upper_arm.{side}"].length + P[f"forearm.{side}"].length) / P["head"].length
    t = min(1.0, max(0.0, (ratio - 0.5) / 1.0))
    elev, bend, sway = 5 + 30 * t, 18 + 32 * t, 22 + 6 * t
    up = 90 + elev - math.degrees(math.atan2(abs(d.x), -d.z))  # upper arm ends `elev` deg above horizontal
    other = "L" if side == "R" else "R"
    for f, k, w in ((1, 0, 0), (8, 1, 0), (14, 1, 1), (20, 1, -1), (26, 1, 1), (32, 1, -1), (40, 0, 0)):
        key_rot(P[f"upper_arm.{side}"], f, z=sz * up * k, x=-8 * k)
        key_rot(P[f"forearm.{side}"], f, z=sz * (bend + sway * w) * k)  # forearm raised, swaying side to side
        key_rot(P[f"hand.{side}"], f, z=sz * 15 * w * k)
        key_rot(P[f"upper_arm.{other}"], f, z=sz * 10 * k)
        key_rot(P["chest"], f, z=-5 * sz * k, y=-6 * sz * k)
        key_rot(P["head"], f, z=8 * sz * k, y=-8 * sz * k)


def hit_keys(arm):
    P, L = arm.pose.bones, _leg_len(arm)
    for f, k in ((1, 0.0), (4, 1.0), (9, 0.7), (20, 0.0)):
        key_rot(P["spine"], f, x=-18 * k)
        key_rot(P["chest"], f, x=-12 * k, y=8 * k)
        key_rot(P["head"], f, x=-20 * k, z=6 * k)
        for s, sx in (("L", 1), ("R", -1)):
            key_rot(P[f"upper_arm.{s}"], f, x=-30 * k, z=-25 * k * sx)
            key_rot(P[f"forearm.{s}"], f, x=-40 * k)
            key_rot(P[f"thigh.{s}"], f, x=-10 * k)
            key_rot(P[f"shin.{s}"], f, x=20 * k)
        key_loc(P["hips"], f, (0, -0.05 * L * k, -0.06 * L * k))


BASE_CLIPS = {"Walk": walk_keys, "Run": run_keys, "Jump": jump_keys, "Wave": wave_keys, "Hit": hit_keys}


def with_base_clips(actions):
    """Idle first, then the shared clips, then the character's own action."""
    out = {"Idle": actions.get("Idle", idle_keys)}
    out.update(BASE_CLIPS)
    out.update({k: v for k, v in actions.items() if k != "Idle"})
    return out


def anvil_attack_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (12, -35, 70, -25), (18, -40, 85, -30), (26, 20, -40, 20), (40, 0, 0, 0)]
    for f, chest, ua, fa in seq:
        key_rot(P["chest"], f, z=chest * 0.4, x=-abs(chest) * 0.15)
        key_rot(P["upper_arm.R"], f, x=-ua)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=-abs(ua) * 0.2)


def verdant_cast_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (14, -60, 30, -8), (24, -70, 40, -10), (40, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua * 0.7, z=-ua * 0.3)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=ua * 0.5, z=ua * 0.4)
        key_rot(P["chest"], f, x=ch)
        key_rot(P["head"], f, x=ch * 0.8)


# ----------------------------------------------------------------------------------------
# texture bake (Cycles): albedo, roughness, metallic, emission via EMIT trick + AO
# ----------------------------------------------------------------------------------------

def bake_textures(obj, size, out_dir, char_id):
    sc = bpy.context.scene
    sc.cycles.samples = 1
    sc.render.bake.margin = 8
    sc.render.bake.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    def new_img(name, non_color):
        img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        return img

    def wire(img, channel):
        for m in obj.data.materials:
            nt = m.node_tree
            ch = CHANNELS[m.name]
            out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
            em = nt.nodes.get("__bake_emit") or nt.nodes.new("ShaderNodeEmission")
            em.name = "__bake_emit"
            em.inputs["Strength"].default_value = 1.0
            for l in list(em.inputs["Color"].links):
                nt.links.remove(l)
            if channel == "albedo":
                nt.links.new(ch["color"], em.inputs["Color"])
            elif channel == "rough":
                em.inputs["Color"].default_value = (ch["rough"],) * 3 + (1,)
            elif channel == "metal":
                em.inputs["Color"].default_value = (ch["metal"],) * 3 + (1,)
            elif channel == "emit":
                s = min(1.0, ch["emit_strength"])
                em.inputs["Color"].default_value = tuple(c * s for c in ch["emit"]) + (1,)
            if channel in ("ao", "normal"):
                bsdf = nt.nodes["Principled BSDF"]
                nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
            else:
                nt.links.new(em.outputs[0], out.inputs["Surface"])
            tn = nt.nodes.get("__bake_target") or nt.nodes.new("ShaderNodeTexImage")
            tn.name = "__bake_target"
            tn.image = img
            nt.nodes.active = tn

    def pixels(img):
        a = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(size, size, 4)

    res = {}
    for ch, nc in (("albedo", False), ("rough", True), ("metal", True), ("emit", False)):
        img = new_img(f"{char_id}_{ch}", nc)
        wire(img, ch)
        t = time.time()
        bpy.ops.object.bake(type="EMIT")
        print(f"  baked {ch} in {time.time() - t:.1f}s")
        res[ch] = pixels(img)
        print(f"    {ch}: mean={res[ch][..., :3].mean():.3f} max={res[ch][..., :3].max():.3f}")
    # ambient occlusion: local cavities only (short ray distance) -> hand-painted shadow look
    sc.cycles.samples = 48
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.light_settings.distance = 0.25
    img = new_img(f"{char_id}_ao", True)
    wire(img, "ao")
    t = time.time()
    bpy.ops.object.bake(type="AO")
    print(f"  baked ao in {time.time() - t:.1f}s")
    res["ao"] = pixels(img)
    # tangent-space normal map from the procedural bump (cloth weave, hammered metal, leather, wood grain)
    if STYLE["normal_map"]:
        sc.cycles.samples = 4
        img = new_img(f"{char_id}_normal", True)
        wire(img, "normal")
        t = time.time()
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
        print(f"  baked normal in {time.time() - t:.1f}s")
        res["normal"] = pixels(img)

    ao = np.clip(res["ao"][..., 0], 0, 1)
    ao = 0.25 + 0.75 * ao  # keep the AO soft
    albedo = res["albedo"].copy()
    k = STYLE["ao_in_albedo"]
    albedo[..., :3] *= (1.0 - k + k * ao)[..., None]  # bake part of the AO into albedo (stylized)
    orm = np.stack([ao, res["rough"][..., 0], res["metal"][..., 0], np.ones_like(ao)], -1)
    emit = res["emit"]

    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    outputs = [("basecolor", albedo, False), ("orm", orm, True), ("emissive", emit, False)]
    if "normal" in res:
        outputs.append(("normal", res["normal"], True))
    for name, arr, nc in outputs:
        img = bpy.data.images.new(f"T_{char_id}_{name}", size, size, alpha=False)
        img.colorspace_settings.name = "Non-Color" if nc else "sRGB"
        if not nc:  # float linear -> sRGB bytes
            a = arr.copy()
            rgb = np.clip(a[..., :3], 0, 1)
            a[..., :3] = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
            arr = a
        arr[..., 3] = 1.0
        img.pixels.foreach_set(np.clip(arr, 0, 1).astype(np.float32).ravel())
        p = os.path.join(out_dir, f"{char_id}_{name}.png")
        img.filepath_raw = p
        img.file_format = "PNG"
        img.save()
        paths[name] = p
    return paths


def final_material(char_id, paths, emissive_strength):
    m = bpy.data.materials.new(f"M_{char_id}")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    def tex(path, nc):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path)
        n.image.colorspace_settings.name = "Non-Color" if nc else "sRGB"
        return n

    bc = tex(paths["basecolor"], False)
    nt.links.new(bc.outputs["Color"], bsdf.inputs["Base Color"])
    orm = tex(paths["orm"], True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    # glTF occlusion via the exporter's custom node group
    grp = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if not grp.interface.items_tree:
        grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = grp
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    if "normal" in paths:
        nm = tex(paths["normal"], True)
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.space = "TANGENT"
        nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    em = tex(paths["emissive"], False)
    nt.links.new(em.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = emissive_strength
    if STYLE.get("coat"):  # glossy vinyl / lacquer finish -> KHR_materials_clearcoat
        bsdf.inputs["Coat Weight"].default_value = STYLE["coat"]
        bsdf.inputs["Coat Roughness"].default_value = 0.12
    return m


# ----------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------

def add_blink_shape_key(obj):
    """'Blink' morph target: vertices tagged blink.L/R collapse onto their eye's centre line."""
    groups = {obj.vertex_groups[g].index: zc for g, zc in BLINK.items() if g in obj.vertex_groups}
    if not groups:
        return
    obj.shape_key_add(name="Basis")
    sk = obj.shape_key_add(name="Blink")
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group in groups and g.weight > 0.5:
                zc = groups[g.group]
                sk.data[v.index].co.z = zc + (v.co.z - zc) * 0.08
                break
    print(f"  blink shape key on {sum(1 for _ in groups)} eye groups")


RECIPES = {"anvil": recipe_anvil, "verdant": recipe_verdant}  # extended by build_anime.py etc.


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True, choices=sorted(RECIPES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--tex", type=int, default=2048)
    args = ap.parse_args(argv)

    t0 = time.time()
    reset_scene()
    J, R, M, parts, H, actions = RECIPES[args.char]()
    actions = with_base_clips(actions)
    print(f"[{args.char}] built {len(parts)} parts in {time.time() - t0:.1f}s")

    # 1) rig: armature + auto weights for the body, rigid weights for props
    arm = build_armature(J)
    body = parts[0][0]
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    body.parent = None
    body.modifiers.clear()
    for obj, bone in parts[1:]:
        rigid_group(obj, bone)

    # 2) join into a single mesh
    bpy.ops.object.select_all(action="DESELECT")
    for obj, _ in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    mesh_obj = bpy.context.object
    mesh_obj.name = f"{args.char}_mesh"
    add_blink_shape_key(mesh_obj)

    # 3) UVs
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.quads_convert_to_tris()  # game mesh = triangles; also required for exported tangents
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # 4) bake -> one texture set
    out_glb = os.path.abspath(args.out)
    tex_dir = os.path.join(os.path.dirname(out_glb), "textures")
    t = time.time()
    paths = bake_textures(mesh_obj, args.tex, tex_dir, args.char)
    print(f"[{args.char}] bake done in {time.time() - t:.1f}s")
    emit_strength = max(CHANNELS[m.name]["emit_strength"] for m in mesh_obj.data.materials)
    mat = final_material(args.char, paths, max(1.0, emit_strength))
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    for p in mesh_obj.data.polygons:
        p.material_index = 0

    # 5) skin to armature
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mesh_obj.parent = arm

    # 6) animations as separate actions (stashed in NLA so the exporter sees them all)
    arm.animation_data_create()
    for name, fn in actions.items():
        act = bpy.data.actions.new(name)
        arm.animation_data.action = act
        fn(arm)
        act.use_fake_user = True
        track = arm.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, int(act.frame_range[0]), act)
        track.mute = True
        arm.animation_data.action = None
    reset_pose(arm)

    # 7) stats + export
    dg = bpy.context.evaluated_depsgraph_get()
    tris = sum(len(p.vertices) - 2 for p in mesh_obj.data.polygons)
    stats = {
        "character": args.char,
        "vertices": len(mesh_obj.data.vertices),
        "triangles": tris,
        "bones": len(arm.data.bones),
        "materials": 1,
        "texture_size": args.tex,
        "animations": list(actions.keys()),
        "height_m": round(max((mesh_obj.matrix_world @ v.co).z for v in mesh_obj.data.vertices), 3),
        "build_seconds": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.dirname(out_glb), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    mesh_obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True,
                              export_animations=True, export_animation_mode="ACTIONS",
                              export_skins=True, export_yup=True, export_image_format="JPEG", export_jpeg_quality=90, export_tangents=True)
    stats["glb_bytes"] = os.path.getsize(out_glb)
    with open(out_glb.replace(".glb", ".stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    bpy.ops.wm.save_as_mainfile(filepath=out_glb.replace(".glb", ".blend"))
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
