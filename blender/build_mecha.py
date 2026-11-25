"""Sci-fi hard-surface mech (科幻機甲) - original design 「鐵鷹 MK-II」 Iron Hawk.

Hard-surface vocabulary, all procedural:
  * panel(): bevelled armour plates with an inset panel line on the outward face (bmesh inset + push)
    and weighted normals, so big flat faces shade cleanly while edges catch highlights
  * piston(): hydraulic cylinder + chrome rod + end caps; joint(): ball joint with a retaining ring
  * fingered hands (2 segments per finger + thumb), vent slats, missile pod grid, thrusters
  * hazard-stripe panels and real text markings ("MK-II", "07") from Blender font objects
  * emissive visor / reactor core / thrusters / rifle optics
Rigid parts are bound to the 19-bone rig; Idle + Aim clips.

Usage: blender -b --factory-startup -P blender/build_mecha.py -- --char ironhawk --out assets/models/mecha/ironhawk.glb
"""
from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import build_character as bc  # noqa: E402
import build_chibi  # noqa: E402,F401  (registers pattern helpers; we override STYLE below)
from build_character import (build_body, cyl_between, ellipsoid, idle_keys, key_rot, link, make_mat,  # noqa: E402
                             mirror_joints, set_mat, shade, torus)
from build_chibi import stripe_mat  # noqa: E402

bc.STYLE.update(gradient=(0.96, 1.02), ao_in_albedo=0.35, normal_map=True, coat=0.12)


# ----------------------------------------------------------------------------------------
# hard-surface building blocks
# ----------------------------------------------------------------------------------------

def panel(name, c, half, mat, rot=(0, 0, 0), bevel=0.012, face=(0, -1, 0), inset_mat=None, inset=0.014,
          depth=0.004, taper=(1.0, 1.0), chamfer=0.0):
    """Bevelled plate; the face pointing along `face` (local) gets an inset panel line."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    for v in bm.verts:
        v.co.x *= half[0] * (taper[0] if v.co.z > 0 else 1.0)
        v.co.y *= half[1] * (taper[1] if v.co.z > 0 else 1.0)
        v.co.z *= half[2]
    if face is not None and inset > 0:
        f0 = max(bm.faces, key=lambda f: f.normal.dot(Vector(face)))
        bmesh.ops.inset_individual(bm, faces=[f0], thickness=inset, depth=-depth)
    obj = bc.mesh_from_bmesh(name, bm)
    set_mat(obj, mat, [inset_mat] if inset_mat is not None else [])
    if inset_mat is not None and face is not None:
        # set after the slots exist (to_mesh clamps indices otherwise); inner face = the one facing `face` most squarely
        inner = max(obj.data.polygons, key=lambda p: p.normal.dot(Vector(face)) - 1e-3 * p.area)
        inner.material_index = 1
    obj.rotation_euler = Euler(rot)
    obj.location = c
    if chamfer > 0:  # big 45-degree cut on the long edges -> angular sci-fi armour
        ch = obj.modifiers.new("chamfer", "BEVEL")
        ch.width = chamfer
        ch.segments = 1
        ch.limit_method = "ANGLE"
        ch.angle_limit = math.radians(60)
        bc.apply_modifiers(obj)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = 2
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(40)
    bc.apply_modifiers(obj)
    bc.apply_transform(obj)
    shade(obj, True, 35)
    wn = obj.modifiers.new("wn", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    bc.apply_modifiers(obj)
    return obj


def piston(name, p1, p2, r, M):
    p1, p2 = Vector(p1), Vector(p2)
    mid = p1.lerp(p2, 0.55)
    return [
        cyl_between(f"{name}_cyl", p1, mid, r, r, M["frame"], 16),
        cyl_between(f"{name}_rod", mid, p2, r * 0.55, r * 0.55, M["chrome"], 12),
        ellipsoid(f"{name}_capA", p1, (r * 1.25, r * 1.25, r * 1.25), M["frame"], 12, 8),
        ellipsoid(f"{name}_capB", p2, (r * 1.0, r * 1.0, r * 1.0), M["chrome"], 12, 8),
        torus(f"{name}_seal", mid, r * 0.95, r * 0.18, M["rubber"],
              rot=Vector((0, 0, 1)).rotation_difference(p2 - p1).to_euler(), seg=16, mseg=6),
    ]


def joint(name, c, r, M):
    return [ellipsoid(f"{name}_ball", c, (r, r, r), M["frame"], 20, 14),
            torus(f"{name}_ring", c, r * 0.92, r * 0.16, M["chrome"], rot=(math.pi / 2, 0, 0), seg=24, mseg=6)]


def text_decal(name, text, c, size, mat, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = size
    cu.extrude = 0.0015
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = link(bpy.data.objects.new(name + "_t", cu))
    tmp.rotation_euler = Euler(rot)
    tmp.location = c
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    me.transform(tmp.matrix_world)
    bpy.data.objects.remove(tmp)
    obj = link(bpy.data.objects.new(name, me))
    set_mat(obj, mat)
    return obj


def vents(name, c, half, n, mat, axis="z"):
    out = []
    for i in range(n):
        t = -1 + 2 * (i + 0.5) / n
        off = Vector((0, 0, t * half[2])) if axis == "z" else Vector((t * half[0], 0, 0))
        out.append(panel(f"{name}{i}", Vector(c) + off, (half[0], half[1], half[2] / n * 0.35) if axis == "z" else
                         (half[0] / n * 0.35, half[1], half[2]), mat, bevel=0.002, face=None))
    return out


def finger(name, base, direction, lengths, r, M):
    d = Vector(direction).normalized()
    out, p = [], Vector(base)
    for i, L in enumerate(lengths):
        q = p + d * L
        out.append(cyl_between(f"{name}_{i}", p, q, r, r * 0.92, M["frame"] if i % 2 else M["paint_w"], 10))
        out.append(ellipsoid(f"{name}_k{i}", p, (r * 1.1, r * 1.1, r * 1.1), M["frame"], 8, 6))
        d = (d + Vector((0, -0.25, -0.35))).normalized()  # curl
        p = q
    return out


def hand(prefix, wrist, hand_end, sx, M):
    w, e = Vector(wrist), Vector(hand_end)
    fwd = (e - w).normalized()
    palm_c = w.lerp(e, 0.45)
    out = [panel(f"{prefix}_palm", palm_c, (0.058, 0.036, 0.062), M["frame"], bevel=0.008, face=None,
                 rot=Vector((0, 0, 1)).rotation_difference(fwd).to_euler())]
    for k in range(4):
        off = Vector((0.0, (k - 1.5) * 0.029, 0))
        base = e + off * 1.0 + Vector((0, 0, 0.01))
        out += finger(f"{prefix}_f{k}", base, fwd + Vector((0.15 * sx, 0, 0)), (0.05, 0.042), 0.0135, M)
    out += finger(f"{prefix}_thumb", palm_c + Vector((-0.035 * sx, -0.05, 0.0)), Vector((-0.4 * sx, -0.6, -0.6)), (0.042, 0.036), 0.014, M)
    return out


# ----------------------------------------------------------------------------------------
# 鐵鷹 MK-II
# ----------------------------------------------------------------------------------------

def recipe_ironhawk():
    H = 2.42
    J = mirror_joints({
        "hips": (0, 0, 1.15), "spine": (0, 0, 1.35), "chest": (0, 0, 1.6),
        "neck": (0, 0, 1.9), "head": (0, 0, 1.96), "head_top": (0, 0, 2.3),
        "shoulder.L": (0.33, 0, 1.79), "elbow.L": (0.55, 0.02, 1.47),
        "wrist.L": (0.71, -0.02, 1.17), "hand_end.L": (0.76, -0.04, 1.05),
        "hip.L": (0.17, 0, 1.08), "knee.L": (0.21, -0.04, 0.62),
        "ankle.L": (0.22, 0.02, 0.17), "toe.L": (0.22, -0.22, 0.05),
    })
    R = {"hips": (0.17, 0.13), "spine": (0.14, 0.11), "chest": (0.2, 0.15), "neck": 0.07,
         "shoulder": 0.085, "elbow": 0.065, "wrist": 0.055, "hip": 0.095, "knee": 0.08,
         "ankle": 0.065, "toe": 0.055}
    M = dict(
        frame=make_mat("frame", "#3B4049", 0.45, 0.8, noise=0.06, noise_scale=10, edge=0.25, height=H, bump="metal", bump_strength=0.08),
        paint_w=make_mat("paint_w", "#E4E7EB", 0.36, 0.0, noise=0.04, noise_scale=6, edge=0.18, height=H),
        paint_o=make_mat("paint_o", "#EE5F0E", 0.38, 0.0, noise=0.05, noise_scale=6, edge=0.12, height=H),
        navy=make_mat("navy", "#2B3A55", 0.4, 0.0, noise=0.04, noise_scale=6, edge=0.15, height=H),
        chrome=make_mat("chrome", "#CDD3DA", 0.18, 1.0, noise=0.02, height=H),
        rubber=make_mat("rubber", "#1B1D21", 0.8, 0.0, noise=0.05, height=H),
        glow=make_mat("glow", "#39E0FF", 0.2, 0.0, noise=0.0, emit_strength=3.0, height=H),
        glow_o=make_mat("glow_o", "#FF9A3C", 0.2, 0.0, noise=0.0, emit_strength=3.0, height=H),
        decal=make_mat("decal", "#23272E", 0.5, 0.0, noise=0.0, height=H),
        hazard=stripe_mat("hazard", "#F2C230", "#23272E", 14.0, "DIAGONAL", 0.45, H),
        missile=make_mat("missile", "#C6352E", 0.4, 0.0, noise=0.03, height=H),
    )
    parts = [(build_body(J, R, M["frame"]), None)]
    P = lambda objs, bone: [(o, bone) for o in (objs if isinstance(objs, list) else [objs])]  # noqa: E731

    # --- head: helmet, visor, face mask, crest fin, sensors, chin
    hc = Vector((0, -0.01, 2.05))
    parts += P(panel("helmet", hc + Vector((0, 0.01, 0.04)), (0.15, 0.17, 0.12), M["paint_w"], bevel=0.012, face=(0, 0, 1),
                     inset_mat=M["navy"], inset=0.035, taper=(0.78, 0.85), chamfer=0.05), "head")
    parts += P(panel("mask", hc + Vector((0, -0.08, -0.06)), (0.11, 0.1, 0.075), M["frame"], bevel=0.01, face=(0, -1, 0),
                     taper=(1.2, 1.0), chamfer=0.03), "head")
    parts += P(panel("visor", hc + Vector((0, -0.178, 0.005)), (0.12, 0.012, 0.024), M["glow"], bevel=0.006, face=None,
                     chamfer=0.01), "head")
    parts += P(panel("brow", hc + Vector((0, -0.17, 0.05)), (0.14, 0.03, 0.02), M["paint_o"], bevel=0.006, face=None,
                     rot=(0.35, 0, 0), chamfer=0.012), "head")
    parts += P(panel("crest", hc + Vector((0, 0.02, 0.2)), (0.012, 0.15, 0.05), M["paint_o"], bevel=0.006, face=None,
                     rot=(-0.45, 0, 0), taper=(1.0, 0.45)), "head")
    for sx in (-1, 1):
        ear = hc + Vector((0.16 * sx, 0.0, 0.0))
        parts += P([cyl_between(f"ear{sx}", ear, ear + Vector((0.04 * sx, 0, 0)), 0.05, 0.045, M["frame"], 20),
                    cyl_between(f"ear_lens{sx}", ear + Vector((0.04 * sx, 0, 0)), ear + Vector((0.048 * sx, 0, 0)), 0.03, 0.03, M["glow"], 16),
                    cyl_between(f"antenna{sx}", ear + Vector((0.03 * sx, 0.02, 0.03)), ear + Vector((0.05 * sx, 0.12, 0.17)), 0.006, 0.003,
                                M["chrome"], 6)], "head")
    parts += P(panel("chin", hc + Vector((0, -0.11, -0.13)), (0.07, 0.05, 0.035), M["paint_w"], bevel=0.008, face=None,
                     chamfer=0.02), "head")
    parts += P(cyl_between("neck_cyl", (0, 0, 1.84), (0, 0, 1.95), 0.08, 0.075, M["frame"], 20), "neck")
    for k in range(3):
        parts += P(torus(f"neck_ring{k}", (0, 0, 1.86 + k * 0.03), 0.079, 0.008, M["chrome"]), "neck")

    # --- torso: chest plates, reactor core, collar, abdomen stack, skirt armour, backpack + thrusters
    parts += P(panel("chest", (0, -0.03, 1.66), (0.3, 0.17, 0.17), M["paint_w"], bevel=0.012, face=(0, -1, 0),
                     inset_mat=M["navy"], inset=0.05, taper=(1.12, 1.05), chamfer=0.07), "chest")
    for sx in (-1, 1):
        parts += P(panel(f"chest_side{sx}", (0.29 * sx, -0.02, 1.6), (0.05, 0.13, 0.12), M["paint_o"], bevel=0.008, face=(sx, 0, 0),
                         inset_mat=M["frame"], chamfer=0.03), "chest")
        parts += P(panel(f"collar{sx}", (0.15 * sx, -0.02, 1.82), (0.11, 0.12, 0.035), M["paint_o"], bevel=0.012, face=None,
                         rot=(0, 0.3 * sx, 0)), "chest")
        parts += P(vents(f"chest_vent{sx}_", (0.19 * sx, -0.205, 1.56), (0.05, 0.012, 0.055), 4, M["frame"]), "chest")
    core = Vector((0, -0.215, 1.66))
    parts += P([cyl_between("core_housing", core + Vector((0, 0.04, 0)), core, 0.085, 0.085, M["frame"], 32),
                cyl_between("core", core, core + Vector((0, -0.012, 0)), 0.06, 0.06, M["glow"], 32),
                torus("core_ring", core + Vector((0, -0.008, 0)), 0.072, 0.01, M["chrome"], rot=(math.pi / 2, 0, 0), seg=40),
                torus("core_ring_o", core + Vector((0, 0.005, 0)), 0.092, 0.012, M["paint_o"], rot=(math.pi / 2, 0, 0), seg=40)], "chest")
    parts += P(text_decal("decal_mk2", "MK-II", Vector((0.17, -0.205, 1.76)), 0.05, M["decal"]), "chest")
    for k in range(3):
        parts += P(panel(f"abs{k}", (0, -0.03, 1.47 - k * 0.075), (0.15 - k * 0.012, 0.12, 0.032), M["frame"], bevel=0.01,
                         face=(0, -1, 0), inset=0.008, depth=0.003), "spine")
    parts += P(panel("waist", (0, 0, 1.2), (0.21, 0.16, 0.055), M["navy"], bevel=0.01, face=(0, -1, 0), inset_mat=M["frame"], chamfer=0.025), "hips")
    for sx in (-1, 1):
        parts += P(panel(f"skirt_f{sx}", (0.1 * sx, -0.17, 1.06), (0.085, 0.02, 0.11), M["paint_w"], bevel=0.012, face=(0, -1, 0),
                         inset_mat=M["hazard"], rot=(0.18, 0, 0.08 * sx), taper=(1.0, 1.0)), "hips")
        parts += P(panel(f"skirt_s{sx}", (0.24 * sx, 0.0, 1.07), (0.02, 0.12, 0.1), M["paint_o"], bevel=0.01, face=(sx, 0, 0),
                         inset_mat=M["paint_w"], rot=(0, -0.2 * sx, 0)), "hips")
    parts += P(panel("skirt_b", (0, 0.17, 1.07), (0.15, 0.02, 0.1), M["paint_w"], bevel=0.012, face=(0, 1, 0), rot=(-0.18, 0, 0)), "hips")
    parts += P(panel("backpack", (0, 0.2, 1.62), (0.17, 0.08, 0.17), M["frame"], bevel=0.02, face=(0, 1, 0), inset_mat=M["paint_w"]), "chest")
    for sx in (-1, 1):
        t0 = Vector((0.12 * sx, 0.27, 1.6))
        parts += P([cyl_between(f"thruster{sx}", t0 + Vector((0, 0, 0.12)), t0 + Vector((0, 0.03, -0.12)), 0.055, 0.075, M["paint_o"], 24),
                    cyl_between(f"nozzle{sx}", t0 + Vector((0, 0.03, -0.12)), t0 + Vector((0, 0.035, -0.17)), 0.07, 0.085, M["frame"], 24),
                    cyl_between(f"flame{sx}", t0 + Vector((0, 0.035, -0.16)), t0 + Vector((0, 0.036, -0.165)), 0.06, 0.06, M["glow"], 24)], "chest")

    # --- shoulders: big pauldrons, missile pod (L), markings (R)
    for s, sx in (("L", 1), ("R", -1)):
        sh = Vector(J[f"shoulder.{s}"])
        pc = sh + Vector((0.06 * sx, 0, 0.03))
        parts += P(joint(f"shoulder_joint.{s}", sh, 0.1, M), f"upper_arm.{s}")
        parts += P(panel(f"pauldron.{s}", pc, (0.17, 0.2, 0.14), M["paint_w"], bevel=0.012, face=(sx, 0, 0),
                         inset_mat=M["paint_o"], inset=0.04, rot=(0, -0.25 * sx, 0), taper=(0.8, 0.88), chamfer=0.06), f"upper_arm.{s}")
        parts += P(panel(f"pauldron_trim.{s}", pc + Vector((0.02 * sx, -0.2, -0.06)), (0.13, 0.02, 0.035), M["hazard"], bevel=0.006,
                         face=None, rot=(0, -0.25 * sx, 0)), f"upper_arm.{s}")
        if s == "L":
            pod = pc + Vector((0.02, 0.0, 0.2))
            parts += P(panel("pod", pod, (0.09, 0.15, 0.07), M["frame"], bevel=0.015, face=(0, -1, 0), inset_mat=M["paint_w"]), "upper_arm.L")
            for i in range(3):
                for j in range(2):
                    mc = pod + Vector((-0.05 + i * 0.05, -0.15, -0.025 + j * 0.05))
                    parts += P([cyl_between(f"tube{i}{j}", mc + Vector((0, 0.03, 0)), mc, 0.018, 0.018, M["rubber"], 12),
                                ellipsoid(f"missile{i}{j}", mc + Vector((0, 0.008, 0)), (0.013, 0.013, 0.013), M["missile"], 10, 6)],
                               "upper_arm.L")
        else:
            parts += P(text_decal("decal_07", "07", pc + Vector((-0.06, -0.19, 0.03)), 0.09, M["decal"], rot=(math.pi / 2, 0, 0.25)),
                       "upper_arm.R")

    # --- arms: upper armour, elbow, forearm armour + hazard plate, wrist, fingered hands
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        up_rot = Vector((0, 0, 1)).rotation_difference(sh - el).to_euler()
        lo_rot = Vector((0, 0, 1)).rotation_difference(el - wr).to_euler()
        parts += P(panel(f"upper_arm_armor.{s}", sh.lerp(el, 0.58), (0.09, 0.095, 0.14), M["paint_w"], bevel=0.01, face=(sx, 0, 0),
                         inset_mat=M["navy"], rot=up_rot, chamfer=0.03), f"upper_arm.{s}")
        parts += P(joint(f"elbow.{s}", el, 0.075, M), f"forearm.{s}")
        parts += P(panel(f"forearm_armor.{s}", el.lerp(wr, 0.5), (0.105, 0.11, 0.17), M["paint_o"], bevel=0.01, face=(sx, 0, 0),
                         inset_mat=M["paint_w"], rot=lo_rot, taper=(0.82, 0.88), chamfer=0.035), f"forearm.{s}")
        parts += P(piston(f"arm_piston.{s}", el + Vector((0, 0.07, 0.04)), wr + Vector((0, 0.06, 0.05)), 0.016, M), f"forearm.{s}")
        parts += P(torus(f"wrist_ring.{s}", wr, 0.06, 0.014, M["chrome"],
                         rot=Vector((0, 0, 1)).rotation_difference(wr - el).to_euler()), f"forearm.{s}")
        parts += P(hand(f"hand.{s}", wr, J[f"hand_end.{s}"], sx, M), f"hand.{s}")

    # --- legs: thigh, knee, shin with vents and calf pistons, ankle, feet
    for s, sx in (("L", 1), ("R", -1)):
        hp, kn, an, to = (Vector(J[f"{k}.{s}"]) for k in ("hip", "knee", "ankle", "toe"))
        parts += P(joint(f"hip_joint.{s}", hp, 0.095, M), f"thigh.{s}")
        parts += P(panel(f"thigh_armor.{s}", hp.lerp(kn, 0.5), (0.13, 0.14, 0.2), M["paint_w"], bevel=0.01, face=(0, -1, 0),
                         inset_mat=M["navy"], rot=Vector((0, 0, 1)).rotation_difference(hp - kn).to_euler(), taper=(1.1, 1.1), chamfer=0.04),
                   f"thigh.{s}")
        parts += P(joint(f"knee_joint.{s}", kn, 0.085, M), f"shin.{s}")
        parts += P(panel(f"knee_pad.{s}", kn + Vector((0, -0.1, 0.02)), (0.085, 0.04, 0.09), M["paint_o"], bevel=0.02, face=(0, -1, 0),
                         inset_mat=M["frame"], rot=(0.25, 0, 0), taper=(0.8, 1.0)), f"shin.{s}")
        sc = kn.lerp(an, 0.5)
        parts += P(panel(f"shin_armor.{s}", sc + Vector((0, -0.02, 0)), (0.145, 0.155, 0.25), M["paint_w"], bevel=0.01, face=(0, -1, 0),
                         inset_mat=M["paint_o"], rot=Vector((0, 0, 1)).rotation_difference(kn - an).to_euler(), taper=(0.82, 0.82),
                         chamfer=0.05),
                   f"shin.{s}")
        parts += P(vents(f"shin_vent.{s}_", sc + Vector((0.145 * sx, -0.02, 0.02)), (0.01, 0.07, 0.1), 5, M["frame"]), f"shin.{s}")
        parts += P(panel(f"shin_hazard.{s}", sc + Vector((0, -0.18, -0.15)), (0.09, 0.008, 0.03), M["hazard"], bevel=0.004, face=None),
                   f"shin.{s}")
        parts += P(piston(f"calf_piston.{s}", kn + Vector((0, 0.1, -0.06)), an + Vector((0, 0.11, 0.08)), 0.022, M), f"shin.{s}")
        parts += P(joint(f"ankle_joint.{s}", an, 0.07, M), f"foot.{s}")
        parts += P(panel(f"foot.{s}", Vector((an.x, -0.08, 0.07)), (0.11, 0.2, 0.065), M["paint_w"], bevel=0.01, face=(0, 0, 1),
                         inset_mat=M["navy"], taper=(0.85, 0.7), chamfer=0.03), f"foot.{s}")
        parts += P(panel(f"toe.{s}", Vector((an.x, -0.27, 0.05)), (0.09, 0.05, 0.045), M["paint_o"], bevel=0.02, face=None,
                         rot=(0.25, 0, 0)), f"foot.{s}")
        parts += P(panel(f"heel.{s}", Vector((an.x, 0.12, 0.06)), (0.07, 0.04, 0.05), M["frame"], bevel=0.015, face=None), f"foot.{s}")
        parts += P(panel(f"sole.{s}", Vector((an.x, -0.08, 0.012)), (0.105, 0.23, 0.012), M["rubber"], bevel=0.006, face=None), f"foot.{s}")

    # --- beam rifle (right hand) and shield (left forearm)
    hr_ = Vector(J["hand_end.R"]) + Vector((0, -0.03, 0.0))
    d = Vector((0, -0.35, -1)).normalized()
    rr = Vector((0, 0, 1)).rotation_difference(d).to_euler()
    k = 1.45
    parts += P([panel("rifle_body", hr_ + d * 0.12 * k, (0.05, 0.085, 0.24 * k), M["frame"], bevel=0.008, face=(1, 0, 0),
                      inset_mat=M["paint_w"], rot=rr, chamfer=0.02),
                cyl_between("rifle_barrel", hr_ + d * 0.3 * k, hr_ + d * 0.66 * k, 0.026, 0.024, M["chrome"], 16),
                cyl_between("rifle_shroud", hr_ + d * 0.3 * k, hr_ + d * 0.5 * k, 0.042, 0.042, M["paint_o"], 16),
                cyl_between("rifle_muzzle", hr_ + d * 0.66 * k, hr_ + d * 0.675 * k, 0.031, 0.031, M["glow"], 16),
                cyl_between("rifle_scope", hr_ + d * 0.02 * k + Vector((0, -0.09, 0.02)), hr_ + d * 0.22 * k + Vector((0, -0.09, 0.02)),
                            0.025, 0.025, M["frame"], 12),
                cyl_between("rifle_lens", hr_ + d * 0.22 * k + Vector((0, -0.09, 0.02)), hr_ + d * 0.226 * k + Vector((0, -0.09, 0.02)),
                            0.021, 0.021, M["glow_o"], 12),
                panel("rifle_mag", hr_ + d * 0.16 * k + Vector((0, 0.08, 0.03)), (0.035, 0.06, 0.1), M["paint_w"], bevel=0.006, face=None,
                      rot=rr, chamfer=0.012)], "hand.R")
    el, wr = Vector(J["elbow.L"]), Vector(J["wrist.L"])
    shc = el.lerp(wr, 0.5) + Vector((0.13, -0.03, 0))
    parts += P([panel("shield", shc, (0.03, 0.22, 0.32), M["paint_w"], bevel=0.01, face=(1, 0, 0), inset_mat=M["navy"], inset=0.045,
                      rot=(0, -0.25, 0), taper=(1.0, 0.5), chamfer=0.06),
                panel("shield_chevron", shc + Vector((0.035, -0.02, 0.05)), (0.006, 0.09, 0.03), M["frame"], bevel=0.004, face=None,
                      rot=(0.6, -0.25, 0)),
                panel("shield_chevron2", shc + Vector((0.035, -0.02, -0.02)), (0.006, 0.07, 0.025), M["frame"], bevel=0.004, face=None,
                      rot=(0.6, -0.25, 0))], "forearm.L")
    return J, R, M, parts, H, {"Idle": idle_keys, "Aim": ironhawk_aim_keys}


def ironhawk_aim_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (14, -70, -25, -15), (30, -70, -25, -15), (44, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua, z=ua * 0.15)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=ua * 0.6, z=-ua * 0.3)
        key_rot(P["forearm.L"], f, x=fa * 1.5)
        key_rot(P["chest"], f, z=ch)
        key_rot(P["head"], f, z=-ch * 0.6)


bc.RECIPES.update(ironhawk=recipe_ironhawk)

if __name__ == "__main__":
    bc.main()
