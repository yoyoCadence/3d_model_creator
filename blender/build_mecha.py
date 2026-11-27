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
from build_character import (build_body, cyl_between, ellipsoid, idle_keys, key_loc, key_rot, link, make_mat,  # noqa: E402
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


@bc.hit(23)  # shot fired (recoil kick)
def ironhawk_aim_keys(arm):
    """Shoulder the rifle, fire once (recoil kicks the arms up and the chest back), hold, lower."""
    P = arm.pose.bones
    #       frame, aim, recoil
    seq = [(1, 0, 0), (14, 1, 0), (22, 1, 0), (23, 1, 1), (27, 1, 0), (32, 1, 0), (44, 0, 0)]
    for f, a, r in seq:
        ua, fa, ch = -58 * a - 10 * r, -14 * a - 8 * r, -15 * a
        key_rot(P["upper_arm.R"], f, x=ua, z=ua * 0.15)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=ua * 0.6, z=-ua * 0.3)
        key_rot(P["forearm.L"], f, x=fa * 1.5)
        key_rot(P["chest"], f, z=ch, x=-5 * r)
        key_rot(P["head"], f, z=-ch * 0.6, x=-4 * r)


# ----------------------------------------------------------------------------------------
# 夜梟 RX-9 - slim stealth sniper (Iron Hawk's squad mate)
# ----------------------------------------------------------------------------------------

def oriented(direction, hint=(0, 1, 0)):
    """Euler whose local Z follows `direction` and local Y leans towards `hint` (the thin axis for blades)."""
    z = Vector(direction).normalized()
    x = Vector(hint).cross(z).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_euler()


def cloak(name, top_z, bot_z, half_w, y0, flare, strips, mat, nx=28, ny=16):
    """Hanging cape behind the back: curved around the torso, flaring out, with a tattered V-cut hem."""
    bm = bmesh.new()
    grid = [[None] * (nx + 1) for _ in range(ny + 1)]
    for j in range(ny + 1):
        v = j / ny
        for i in range(nx + 1):
            u = -1 + 2 * i / nx
            x = half_w * u * (1 + 0.45 * v)
            y = y0 + 0.07 * (1 - u * u) + flare * v ** 1.4 + 0.018 * math.sin(u * math.pi * 4.5) * v
            z = top_z - (top_z - bot_z) * v
            grid[j][i] = bm.verts.new((x, y, z))
    for j in range(ny):
        for i in range(nx):
            u, v = -1 + 2 * (i + 0.5) / nx, (j + 0.5) / ny
            frac = ((u + 1) / 2 * strips) % 1.0
            if v > 1 - 0.3 * (1 - abs(2 * frac - 1)) - 0.02:
                continue  # tattered hem
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    obj = bc.mesh_from_bmesh(name, bm)
    set_mat(obj, mat)
    bc.solidify(obj, 0.008)
    bc.apply_modifiers(obj)
    shade(obj, True, 180)
    return obj


def talon(name, base, mid, tip, r, M):
    return [cyl_between(f"{name}_a", base, mid, r, r * 0.75, M["frame"], 10),
            cyl_between(f"{name}_b", mid, tip, r * 0.75, r * 0.08, M["chrome"], 10),
            ellipsoid(f"{name}_k", mid, (r * 0.85,) * 3, M["frame"], 8, 6)]


def recipe_nightowl():
    H = 2.3
    J = mirror_joints({
        "hips": (0, 0, 1.12), "spine": (0, 0, 1.3), "chest": (0, 0, 1.52),
        "neck": (0, 0, 1.8), "head": (0, 0, 1.86), "head_top": (0, 0, 2.16),
        "shoulder.L": (0.26, 0, 1.7), "elbow.L": (0.42, 0.03, 1.42),
        "wrist.L": (0.53, -0.0, 1.15), "hand_end.L": (0.57, -0.02, 1.04),
        "hip.L": (0.13, 0, 1.05), "knee.L": (0.16, -0.05, 0.6),
        "ankle.L": (0.17, 0.04, 0.17), "toe.L": (0.17, -0.18, 0.05),
    })
    R = {"hips": (0.13, 0.1), "spine": (0.1, 0.08), "chest": (0.15, 0.11), "neck": 0.055,
         "shoulder": 0.07, "elbow": 0.05, "wrist": 0.045, "hip": 0.075, "knee": 0.06,
         "ankle": 0.05, "toe": 0.045}
    M = dict(
        frame=make_mat("frame", "#24262E", 0.42, 0.85, noise=0.06, noise_scale=10, edge=0.07, height=H, bump="metal", bump_strength=0.08),
        navy=make_mat("navy", "#1B2238", 0.4, 0.0, noise=0.05, noise_scale=6, edge=0.04, height=H),
        purple=make_mat("purple", "#4B3880", 0.36, 0.0, noise=0.05, noise_scale=6, edge=0.05, height=H),
        lilac=make_mat("lilac", "#9C8BD0", 0.36, 0.0, noise=0.03, noise_scale=6, edge=0.05, height=H),
        chrome=make_mat("chrome", "#B9C0CC", 0.2, 1.0, noise=0.02, height=H),
        rubber=make_mat("rubber", "#15161A", 0.8, 0.0, noise=0.05, height=H),
        glow=make_mat("glow", "#58FF9C", 0.2, 0.0, noise=0.0, emit_strength=3.2, height=H),
        glass=make_mat("glass", "#0E3B2A", 0.08, 0.0, noise=0.0, emit_strength=0.6, height=H),
        cloth=make_mat("cloth", "#262B3F", 0.85, 0.0, noise=0.08, noise_scale=40, edge=0.0, height=H, bump="cloth", bump_strength=0.12),
        cloth_in=make_mat("cloth_in", "#3B2F5C", 0.85, 0.0, noise=0.06, noise_scale=40, height=H),
        decal=make_mat("decal", "#C9C3E8", 0.5, 0.0, noise=0.0, height=H),
        hazard=stripe_mat("hazard", "#58FF9C", "#1C2336", 14.0, "DIAGONAL", 0.45, H),
    )
    M["paint_w"] = M["purple"]  # hand()/finger() colour slot
    parts = [(build_body(J, R, M["frame"]), None)]
    P = lambda objs, bone: [(o, bone) for o in (objs if isinstance(objs, list) else [objs])]  # noqa: E731

    # --- owl helmet: faceted dome, dark face plate, twin round optics, beak vane, ear tufts, side antenna
    hc = Vector((0, -0.005, 1.95))
    parts += P(ellipsoid("helmet", hc + Vector((0, 0.015, 0.02)), (0.118, 0.125, 0.108), M["purple"], 32, 20), "head")
    parts += P(panel("helmet_crest", hc + Vector((0, 0.0, 0.118)), (0.03, 0.12, 0.018), M["navy"], bevel=0.006, face=(0, 0, 1),
                     inset_mat=M["glow"], inset=0.008, depth=0.002, rot=(-0.15, 0, 0), taper=(0.6, 0.9)), "head")
    parts += P(panel("helmet_cheek_L", hc + Vector((0.095, -0.05, -0.04)), (0.03, 0.06, 0.05), M["navy"], bevel=0.006, face=None,
                     rot=(0, 0.25, -0.35), chamfer=0.012), "head")
    parts += P(panel("helmet_cheek_R", hc + Vector((-0.095, -0.05, -0.04)), (0.03, 0.06, 0.05), M["navy"], bevel=0.006, face=None,
                     rot=(0, -0.25, 0.35), chamfer=0.012), "head")
    parts += P(panel("faceplate", hc + Vector((0, -0.1, -0.015)), (0.105, 0.04, 0.07), M["navy"], bevel=0.008, face=None,
                     taper=(0.75, 1.0), chamfer=0.025), "head")
    for sx in (-1, 1):
        oc = hc + Vector((0.048 * sx, -0.142, 0.0))
        parts += P([cyl_between(f"optic_housing{sx}", oc + Vector((0, 0.03, 0)), oc, 0.04, 0.04, M["frame"], 28),
                    cyl_between(f"optic_glass{sx}", oc, oc + Vector((0, -0.006, 0)), 0.031, 0.031, M["glass"], 28),
                    cyl_between(f"optic_pupil{sx}", oc + Vector((0, -0.006, 0)), oc + Vector((0, -0.009, 0)), 0.014, 0.014, M["glow"], 20),
                    torus(f"optic_ring{sx}", oc + Vector((0, -0.002, 0)), 0.037, 0.006, M["chrome"], rot=(math.pi / 2, 0, 0), seg=32),
                    torus(f"facial_disc{sx}", oc + Vector((0.004 * sx, 0.006, 0.002)), 0.05, 0.011, M["lilac"], rot=(math.pi / 2, 0, 0), seg=32)],
                   "head")
        brow_d = Vector((0.6 * sx, 0.25, 0.75))
        parts += P(panel(f"ear_tuft{sx}", hc + Vector((0.08 * sx, 0.02, 0.13)), (0.03, 0.007, 0.09), M["purple"], bevel=0.004,
                         face=None, rot=oriented(brow_d), taper=(0.2, 1.0)), "head")
        parts += P(panel(f"brow{sx}", hc + Vector((0.055 * sx, -0.14, 0.05)), (0.05, 0.012, 0.012), M["lilac"], bevel=0.004, face=None,
                         rot=(0.3, 0, -0.35 * sx)), "head")
    parts += P(panel("beak", hc + Vector((0, -0.155, -0.05)), (0.018, 0.018, 0.035), M["frame"], bevel=0.004, face=None,
                     rot=(math.pi + 0.3, 0, 0), taper=(0.1, 0.4)), "head")
    parts += P(cyl_between("antenna", hc + Vector((-0.11, 0.04, 0.04)), hc + Vector((-0.15, 0.16, 0.24)), 0.006, 0.0025, M["chrome"], 6), "head")
    parts += P(ellipsoid("antenna_tip", hc + Vector((-0.15, 0.16, 0.24)), (0.008,) * 3, M["glow"], 8, 6), "head")
    parts += P(cyl_between("neck_cyl", (0, 0, 1.76), (0, 0, 1.86), 0.06, 0.055, M["frame"], 20), "neck")
    parts += P(torus("cowl", (0, 0.005, 1.785), 0.085, 0.042, M["cloth"], scale=(1.05, 1.0, 0.75), seg=40, mseg=14), "chest")
    parts += P(torus("cowl_fold", (0, 0.01, 1.74), 0.12, 0.03, M["cloth_in"], scale=(1.05, 1.0, 0.7), seg=40, mseg=12), "chest")
    for k in range(3):
        parts += P(torus(f"neck_ring{k}", (0, 0, 1.78 + k * 0.028), 0.06, 0.007, M["chrome"]), "neck")

    # --- slim torso: chest with green V light, collar, abs, waist, small skirt plates
    parts += P(panel("chest", (0, -0.02, 1.58), (0.15, 0.12, 0.14), M["navy"], bevel=0.01, face=(0, -1, 0),
                     inset_mat=M["purple"], inset=0.03, taper=(1.5, 1.05), chamfer=0.05), "chest")
    for sx in (-1, 1):
        parts += P(panel(f"pec{sx}", (0.085 * sx, -0.14, 1.635), (0.075, 0.018, 0.06), M["navy"], bevel=0.006, face=None,
                         rot=(0.12, 0, 0.28 * sx), taper=(1.15, 1.0), chamfer=0.018), "chest")
    for sx in (-1, 1):
        parts += P(cyl_between(f"chest_light{sx}", (0.14 * sx, -0.162, 1.69), (0.02 * sx, -0.158, 1.555), 0.006, 0.006, M["glow"], 8), "chest")
        parts += P(panel(f"collar{sx}", (0.11 * sx, -0.01, 1.74), (0.08, 0.09, 0.025), M["purple"], bevel=0.008, face=None,
                         rot=(0, 0.35 * sx, 0), chamfer=0.015), "chest")
        parts += P(vents(f"side_vent{sx}_", (0.2 * sx, 0.0, 1.55), (0.01, 0.07, 0.06), 4, M["frame"]), "chest")
    parts += P(text_decal("decal_rx9", "RX-9", Vector((-0.1, -0.142, 1.47)), 0.035, M["decal"]), "chest")
    for k in range(3):
        parts += P(panel(f"abs{k}", (0, -0.02, 1.4 - k * 0.06), (0.1 - k * 0.008, 0.085, 0.024), M["frame"], bevel=0.008,
                         face=(0, -1, 0), inset=0.006, depth=0.003), "spine")
    parts += P(panel("waist", (0, 0, 1.17), (0.15, 0.11, 0.045), M["purple"], bevel=0.008, face=(0, -1, 0), inset_mat=M["frame"], chamfer=0.02), "hips")
    for sx in (-1, 1):
        parts += P(panel(f"skirt_f{sx}", (0.075 * sx, -0.12, 1.04), (0.06, 0.014, 0.09), M["navy"], bevel=0.008, face=(0, -1, 0),
                         inset_mat=M["purple"], inset=0.012, rot=(0.15, 0, 0.1 * sx), taper=(0.7, 1.0), chamfer=0.02), "hips")
        parts += P(panel(f"skirt_s{sx}", (0.17 * sx, 0.0, 1.05), (0.014, 0.09, 0.085), M["purple"], bevel=0.008, face=None,
                         rot=(0, -0.22 * sx, 0), chamfer=0.02), "hips")

    # --- back: slim pack, tattered cloak, fanned wing blades with glowing edges
    parts += P(panel("backpack", (0, 0.14, 1.58), (0.11, 0.05, 0.13), M["frame"], bevel=0.012, face=(0, 1, 0), inset_mat=M["purple"]), "chest")
    bc.COLLIDER.update(scale=1.6, torso=1.4)  # armour is much bulkier than the skin body
    cl_names = []
    for k, u in enumerate((-0.8, -0.4, 0.0, 0.4, 0.8)):  # chains follow cloak()'s own surface formula
        pts = [(0.2 * u * (1 + 0.45 * v), 0.16 + 0.07 * (1 - u * u) + 0.16 * v ** 1.4, 1.76 - (1.76 - 0.62) * v)
               for v in (0.12, 0.35, 0.6, 0.85, 1.0)]
        bc.spring(f"clothCloak{k}", pts, "chest")
        cl_names.append(f"clothCloak{k}")
    parts += P(cloak("cloak", 1.76, 0.62, 0.2, 0.16, 0.16, 7, M["cloth"]), "spring:" + ",".join(cl_names))
    parts += P(torus("cloak_clasp_bar", (0, 0.05, 1.75), 0.15, 0.012, M["chrome"], scale=(1, 0.75, 1)), "chest")
    for sx in (-1, 1):
        b = Vector((0.07 * sx, 0.25, 1.67))
        parts += P(ellipsoid(f"wing_mount{sx}", b, (0.035, 0.03, 0.035), M["frame"], 14, 10), "chest")
        for i in range(5):  # folded owl wing: overlapping primaries sweeping down-back, lower ones longer
            d = Vector((sx * (0.6 - 0.09 * i), 0.42 + 0.03 * i, 0.3 - 0.3 * i)).normalized()
            L = 0.26 + 0.05 * i
            c = b + d * (L + 0.02)
            rot = oriented(d, (0, 1, 0.2))
            parts += P(panel(f"wing{sx}_{i}", c + Vector((0, 0.012 * i, 0)), (0.05, 0.007, L), M["purple"] if i % 2 == 0 else M["navy"],
                             bevel=0.004, face=None,
                             rot=rot, taper=(0.25, 1.0)), "chest")
            xax = rot.to_matrix().col[0]
            parts += P(cyl_between(f"wing_edge{sx}_{i}", c - d * L + xax * 0.046, c + d * L + xax * 0.012, 0.005, 0.003, M["glow"], 6),
                       "chest")

    # --- arms: slim pauldrons with light strip, armour, wrist blade (L), hands
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        pc = sh + Vector((0.04 * sx, 0, 0.03))
        parts += P(joint(f"shoulder_joint.{s}", sh, 0.075, M), f"upper_arm.{s}")
        parts += P(panel(f"pauldron.{s}", pc, (0.11, 0.13, 0.08), M["purple"], bevel=0.008, face=(sx, 0, 0),
                         inset_mat=M["navy"], inset=0.025, rot=(0, -0.35 * sx, 0), taper=(0.6, 0.8), chamfer=0.04), f"upper_arm.{s}")
        parts += P(cyl_between(f"pauldron_light.{s}", pc + Vector((0.07 * sx, -0.12, -0.04)), pc + Vector((0.1 * sx, 0.1, -0.06)),
                               0.005, 0.005, M["glow"], 6), f"upper_arm.{s}")
        up_rot = Vector((0, 0, 1)).rotation_difference(sh - el).to_euler()
        lo_rot = Vector((0, 0, 1)).rotation_difference(el - wr).to_euler()
        parts += P(panel(f"upper_arm_armor.{s}", sh.lerp(el, 0.58), (0.065, 0.07, 0.11), M["navy"], bevel=0.008, face=(sx, 0, 0),
                         inset_mat=M["purple"], rot=up_rot, chamfer=0.02), f"upper_arm.{s}")
        parts += P(joint(f"elbow.{s}", el, 0.055, M), f"forearm.{s}")
        parts += P(panel(f"forearm_armor.{s}", el.lerp(wr, 0.5), (0.07, 0.075, 0.13), M["purple"], bevel=0.008, face=(sx, 0, 0),
                         inset_mat=M["navy"], rot=lo_rot, taper=(0.8, 0.85), chamfer=0.025), f"forearm.{s}")
        parts += P(torus(f"wrist_ring.{s}", wr, 0.045, 0.01, M["chrome"],
                         rot=Vector((0, 0, 1)).rotation_difference(wr - el).to_euler()), f"forearm.{s}")
        parts += P(hand(f"hand.{s}", wr, J[f"hand_end.{s}"], sx, M), f"hand.{s}")
    el, wr = Vector(J["elbow.L"]), Vector(J["wrist.L"])
    bd = (wr - el).normalized()
    parts += P([panel("wrist_blade", el.lerp(wr, 0.75) + Vector((0.075, 0.0, 0.0)), (0.008, 0.03, 0.2), M["chrome"], bevel=0.003,
                      face=None, rot=oriented(bd, (1, 0, 0)), taper=(1.0, 0.1)),
                cyl_between("wrist_blade_edge", el.lerp(wr, 0.3) + Vector((0.075, -0.028, 0)), el.lerp(wr, 1.3) + Vector((0.075, -0.004, 0)),
                            0.003, 0.002, M["glow"], 6)], "forearm.L")

    # --- digitigrade-looking legs: slim thighs, long chamfered shins, owl talon feet
    for s, sx in (("L", 1), ("R", -1)):
        hp, kn, an = (Vector(J[f"{k}.{s}"]) for k in ("hip", "knee", "ankle"))
        parts += P(joint(f"hip_joint.{s}", hp, 0.075, M), f"thigh.{s}")
        parts += P(panel(f"thigh_armor.{s}", hp.lerp(kn, 0.5), (0.09, 0.1, 0.19), M["navy"], bevel=0.008, face=(0, -1, 0),
                         inset_mat=M["purple"], rot=Vector((0, 0, 1)).rotation_difference(hp - kn).to_euler(), taper=(1.1, 1.1), chamfer=0.03),
                   f"thigh.{s}")
        parts += P(joint(f"knee_joint.{s}", kn, 0.065, M), f"shin.{s}")
        parts += P(panel(f"knee_pad.{s}", kn + Vector((0, -0.075, 0.03)), (0.06, 0.03, 0.08), M["purple"], bevel=0.012, face=None,
                         rot=(0.3, 0, 0), taper=(0.4, 1.0), chamfer=0.015), f"shin.{s}")
        sc = kn.lerp(an, 0.5)
        srot = Vector((0, 0, 1)).rotation_difference(kn - an).to_euler()
        parts += P(panel(f"shin_armor.{s}", sc + Vector((0, -0.015, 0)), (0.1, 0.11, 0.24), M["purple"], bevel=0.008, face=(0, -1, 0),
                         inset_mat=M["navy"], rot=srot, taper=(0.75, 0.8), chamfer=0.045), f"shin.{s}")
        parts += P(cyl_between(f"shin_light.{s}", kn + Vector((0, -0.125, -0.06)), an + Vector((0, -0.1, 0.12)), 0.005, 0.005, M["glow"], 6),
                   f"shin.{s}")
        parts += P(panel(f"calf_spur.{s}", sc + Vector((0, 0.12, 0.05)), (0.03, 0.06, 0.16), M["navy"], bevel=0.006, face=None,
                         rot=(-0.35, 0, 0), taper=(0.3, 0.4), chamfer=0.01), f"shin.{s}")
        parts += P(piston(f"calf_piston.{s}", kn + Vector((0, 0.07, -0.05)), an + Vector((0, 0.08, 0.08)), 0.016, M), f"shin.{s}")
        parts += P(joint(f"ankle_joint.{s}", an, 0.055, M), f"foot.{s}")
        parts += P(panel(f"foot.{s}", Vector((an.x, -0.02, 0.07)), (0.07, 0.12, 0.05), M["navy"], bevel=0.01, face=(0, 0, 1),
                         inset_mat=M["purple"], taper=(0.8, 0.7), chamfer=0.02), f"foot.{s}")
        for k, ox in enumerate((-0.045, 0.0, 0.045)):
            base = Vector((an.x + ox, -0.11, 0.06))
            parts += P(talon(f"talon.{s}{k}", base, base + Vector((ox * 0.6, -0.1, 0.0)), base + Vector((ox * 0.9, -0.17, -0.06)), 0.02, M),
                       f"foot.{s}")
        hb = Vector((an.x, 0.09, 0.07))
        parts += P(talon(f"talon_back.{s}", hb, hb + Vector((0, 0.07, -0.01)), hb + Vector((0, 0.11, -0.07)), 0.018, M), f"foot.{s}")

    # --- long sniper rifle in the right hand, muzzle down-forward (low ready)
    g = Vector(J["hand_end.R"]) + Vector((0, -0.02, 0.03))
    d = Vector((-0.12, -0.6, -0.79)).normalized()
    rr = oriented(d, (1, 0, 0))
    up = rr.to_matrix().col[1]  # rifle "top" (scope side)
    parts += P([panel("rifle_receiver", g + d * 0.1, (0.03, 0.05, 0.2), M["frame"], bevel=0.006, face=(1, 0, 0), inset_mat=M["purple"],
                      rot=rr, chamfer=0.012),
                panel("rifle_stock", g - d * 0.28 + up * 0.01, (0.022, 0.06, 0.16), M["purple"], bevel=0.008, face=(1, 0, 0),
                      inset_mat=M["navy"], rot=rr, taper=(1.0, 1.3), chamfer=0.015),
                panel("rifle_butt", g - d * 0.45 + up * 0.01, (0.026, 0.075, 0.015), M["rubber"], bevel=0.006, face=None, rot=rr),
                panel("rifle_cheek", g - d * 0.2 + up * 0.065, (0.02, 0.012, 0.07), M["navy"], bevel=0.005, face=None, rot=rr),
                cyl_between("rifle_shroud", g + d * 0.3, g + d * 0.62, 0.028, 0.026, M["navy"], 16),
                cyl_between("rifle_barrel", g + d * 0.62, g + d * 0.98, 0.014, 0.013, M["chrome"], 12),
                panel("rifle_brake", g + d * 1.02, (0.022, 0.022, 0.045), M["frame"], bevel=0.004, face=None, rot=rr),
                cyl_between("rifle_brake_glow", g + d * 1.066, g + d * 1.07, 0.012, 0.012, M["glow"], 12),
                cyl_between("scope", g + d * 0.02 + up * 0.075, g + d * 0.34 + up * 0.075, 0.026, 0.026, M["frame"], 16),
                cyl_between("scope_bell", g + d * 0.34 + up * 0.075, g + d * 0.4 + up * 0.075, 0.026, 0.034, M["frame"], 16),
                cyl_between("scope_lens", g + d * 0.4 + up * 0.075, g + d * 0.405 + up * 0.075, 0.03, 0.03, M["glow"], 16),
                cyl_between("scope_eye", g - d * 0.005 + up * 0.075, g + d * 0.02 + up * 0.075, 0.02, 0.02, M["rubber"], 12),
                panel("scope_mount", g + d * 0.17 + up * 0.045, (0.012, 0.025, 0.06), M["frame"], bevel=0.003, face=None, rot=rr),
                panel("rifle_mag", g + d * 0.12 - up * 0.07, (0.02, 0.04, 0.05), M["purple"], bevel=0.005, face=None, rot=rr),
                text_decal("rifle_text", "NIGHT OWL", g + d * 0.45 + Vector((0.03, 0, 0)), 0.022, M["decal"],
                           rot=(Matrix.Rotation(-math.pi / 2, 3, "Y") @ Matrix.Rotation(math.atan2(d.y, -d.z), 3, "X")).to_euler())]
               + [cyl_between(f"bipod{k}", g + d * 0.58 - up * 0.03, g + d * 0.85 - up * 0.03 + Vector((0.015 * k, 0, 0)), 0.006, 0.005,
                              M["frame"], 8) for k in (-1, 1)], "hand.R")
    return J, R, M, parts, H, {"Idle": idle_keys, "Snipe": nightowl_snipe_keys}


@bc.hit(28)  # shot fired (recoil kick)
def nightowl_snipe_keys(arm):
    """Drop to a crouch, shoulder the rifle, fire (recoil kick), recover."""
    P, L = arm.pose.bones, bc._leg_len(arm)
    #       frame, crouch, aim, recoil
    seq = [(1, 0, 0, 0), (12, 1, 1, 0), (26, 1, 1, 0), (28, 1, 1, 1), (34, 1, 1, 0), (48, 1, 1, 0), (60, 0, 0, 0)]
    for f, c, a, r in seq:
        key_loc(P["hips"], f, (0, -0.16 * L * c, 0))
        for s in ("L", "R"):
            key_rot(P[f"thigh.{s}"], f, x=-38 * c)
            key_rot(P[f"shin.{s}"], f, x=62 * c)
            key_rot(P[f"foot.{s}"], f, x=-24 * c)
        key_rot(P["spine"], f, x=10 * c - 4 * r)
        key_rot(P["chest"], f, z=-12 * a, x=-6 * r)
        key_rot(P["upper_arm.R"], f, x=-40 * a - 8 * r, z=15 * a)
        key_rot(P["forearm.R"], f, x=-20 * a - 12 * r)
        key_rot(P["hand.R"], f, x=-6 * a)
        key_rot(P["upper_arm.L"], f, x=-62 * a, z=-28 * a)
        key_rot(P["forearm.L"], f, x=-70 * a)
        key_rot(P["head"], f, z=10 * a, x=4 * a - 6 * r)


bc.RECIPES.update(ironhawk=recipe_ironhawk, nightowl=recipe_nightowl)

if __name__ == "__main__":
    bc.main()
