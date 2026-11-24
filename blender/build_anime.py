"""Anime / cel-shaded game characters (original designs), built procedurally in Blender.

Same rig/bake/export pipeline as build_character.py, plus anime-specific building blocks:
  * strand(): tapered hair clumps from NURBS curves with per-point radius (the classic anime hair shape)
  * ribbon(): flat cloth strips (scarf, hair ribbon tails, sash)
  * anime_head(): narrowed jaw and small chin
  * anime_eye(): large decal eyes - sclera, iris, pupil, two highlights, eyeliner, brow
The style profile turns off baked normal maps and keeps almost no AO in the albedo: cel shading
(toon ramp + outlines) is applied by the real-time shader (site/js/viewer.js toon mode / an engine
toon shader), so the textures stay flat colour.

Usage: blender -b --factory-startup -P blender/build_anime.py -- --char sora --out assets/models/anime-blender/sora.glb
"""
from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import build_character as bc  # noqa: E402
from build_character import (build_body, cyl_between, ellipsoid, idle_keys, key_rot, link,  # noqa: E402
                             make_mat, mirror_joints, rounded_box, set_mat, shade, solidify, subsurf, torus)

bc.STYLE.update(gradient=(0.93, 1.04), ao_in_albedo=0.12, normal_map=False)


# ----------------------------------------------------------------------------------------
# anime building blocks
# ----------------------------------------------------------------------------------------

def strand(name, pts, mat, res=2):
    """Tapered clump along [(x, y, z, radius), ...] -> mesh (NURBS curve, per-point radius)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 1.0
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    cu.resolution_u = 6
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for p, (x, y, z, r) in zip(sp.points, pts):
        p.co = (x, y, z, 1.0)
        p.radius = max(r, 0.0015)
    sp.use_endpoint_u = True
    sp.order_u = min(4, len(pts))
    tmp = link(bpy.data.objects.new(name + "_cu", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    obj = link(bpy.data.objects.new(name, me))
    set_mat(obj, mat)
    shade(obj, True, 180)
    return obj


def ribbon(name, pts, widths, ref, mat, thickness=0.006, rim=None):
    """Flat strip through points; `ref` is the direction the strip's face points to."""
    pts = [Vector(p) for p in pts]
    bm = bmesh.new()
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(Vector(ref)).normalized()
        w = widths[i] / 2
        rows.append((bm.verts.new(p - side * w), bm.verts.new(p + side * w)))
    for (a0, b0), (a1, b1) in zip(rows, rows[1:]):
        bm.faces.new((a0, b0, b1, a1))
    obj = bc.mesh_from_bmesh(name, bm)
    set_mat(obj, mat, [rim] if rim else [])
    solidify(obj, thickness, rim_mat_offset=1 if rim else None)
    subsurf(obj, 1)
    bc.apply_modifiers(obj)
    shade(obj, True, 180)
    return obj


def anime_head(hc, r, mat):
    obj = ellipsoid("head", hc, r, mat, 32, 24)
    for v in obj.data.vertices:
        dz = (hc.z - v.co.z) / r[2]
        if dz > 0:  # narrow jaw, small pointed chin
            k = dz ** 1.6
            v.co.x = hc.x + (v.co.x - hc.x) * (1 - 0.42 * k)
            v.co.y = hc.y + (v.co.y - hc.y) * (1 - 0.15 * k)
    return obj


def face_y(hc, r, dx, dz):
    """Front surface y of the head ellipsoid at offset (dx, dz) from its centre."""
    q = 1 - (dx / r[0]) ** 2 - (dz / r[2]) ** 2
    return hc.y - r[1] * math.sqrt(max(q, 0.05))


def anime_eye(hc, r, sx, M, size=1.0, dz=-0.012, dx=0.042, iris_col="iris"):
    """Big decal eye on the face surface; returns [(obj, bone)]."""
    x = dx * sx
    y = face_y(hc, r, x, dz)
    s = size
    rot = (0, 0, 0.32 * sx)
    c = hc + Vector((x, 0, dz))
    c.y = y + 0.001
    parts = [
        ellipsoid(f"sclera{sx}", c, (0.024 * s, 0.004, 0.028 * s), M["eye_white"], 16, 8, rot=rot),
        ellipsoid(f"iris{sx}", c + Vector((-0.003 * sx, -0.0035, -0.002 * s)), (0.0175 * s, 0.0035, 0.0235 * s), M[iris_col], 16, 8, rot=rot),
        ellipsoid(f"pupil{sx}", c + Vector((-0.003 * sx, -0.0055, -0.002 * s)), (0.0075 * s, 0.002, 0.012 * s), M["pupil"], 12, 6, rot=rot),
        ellipsoid(f"glintA{sx}", c + Vector((0.004 * sx, -0.0072, 0.009 * s)), (0.0055 * s, 0.0015, 0.0055 * s), M["glint"], 10, 6, rot=rot),
        ellipsoid(f"glintB{sx}", c + Vector((-0.008 * sx, -0.0072, -0.01 * s)), (0.0025 * s, 0.0012, 0.0025 * s), M["glint"], 8, 6, rot=rot),
    ]
    # eyeliner: arc over the top of the eye, flicked up at the outer corner
    pts = []
    for i in range(6):
        u = -1 + 2 * i / 5
        px = x + u * 0.027 * s * sx
        pz = dz + 0.027 * s * (1 - 0.55 * u * u) + (0.006 * s if u > 0.7 else 0)
        pts.append((hc.x + px, face_y(hc, r, px, pz) - 0.003, hc.z + pz, 0.0042 * s if abs(u) < 0.8 else 0.0022))
    parts.append(strand(f"liner{sx}", pts, M["liner"]))
    # brow
    bpts = []
    for i in range(4):
        u = -1 + 2 * i / 3
        px = x + u * 0.024 * s * sx
        pz = dz + 0.052 * s - 0.004 * u * u + 0.004 * u
        bpts.append((hc.x + px, face_y(hc, r, px, pz) - 0.002, hc.z + pz, 0.0028 if abs(u) < 0.9 else 0.0015))
    parts.append(strand(f"brow{sx}", bpts, M["liner"]))
    return [(p, "head") for p in parts]


def face_details(hc, r, M, blush=False, mouth_w=0.016):
    out = []
    ny = face_y(hc, r, 0, -0.045)
    out.append(ellipsoid("nose", hc + Vector((0, ny - hc.y - 0.002, -0.045)), (0.005, 0.005, 0.007), M["skin"], 8, 6))
    pts = []
    for i in range(5):
        u = -1 + 2 * i / 4
        px, pz = u * mouth_w, -0.075 + 0.004 * u * u
        pts.append((hc.x + px, face_y(hc, r, px, pz) - 0.0015, hc.z + pz, 0.0022 if abs(u) < 0.9 else 0.0012))
    out.append(strand("mouth", pts, M["mouth"]))
    if blush:
        for sx in (-1, 1):
            px, pz = 0.058 * sx, -0.045
            out.append(ellipsoid(f"blush{sx}", hc + Vector((px, face_y(hc, r, px, pz) - hc.y + 0.0015, pz)),
                                 (0.014, 0.002, 0.007), M["blush"], 12, 6, rot=(0, 0, 0.45 * sx)))
    return [(p, "head") for p in out]


def hair_cap(hc, r, mat, face_open=0.045):
    cap = ellipsoid("hair_cap", hc + Vector((0, 0.012, 0.016)), (r[0] * 1.09, r[1] * 1.09, r[2] * 1.06), mat, 32, 20)
    bm = bmesh.new()
    bm.from_mesh(cap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts
                               if (v.co.y < hc.y - 0.02 and v.co.z < hc.z + face_open) or v.co.z < hc.z - 0.085],
                     context="VERTS")
    bm.to_mesh(cap.data)
    bm.free()
    solidify(cap, 0.008)
    bc.apply_modifiers(cap)
    shade(cap, True, 180)
    return cap


def anime_mats(H, hair, hair2, iris, extra):
    M = dict(
        skin=make_mat("skin", "#F6D5C3", 0.65, noise=0.02, height=H),
        hair=make_mat("hair", hair, 0.55, noise=0.04, noise_scale=3, height=H),
        hair2=make_mat("hair2", hair2, 0.55, noise=0.04, noise_scale=3, height=H),
        eye_white=make_mat("eye_white", "#FFFFFF", 0.4, noise=0.0, height=H),
        iris=make_mat("iris", iris, 0.3, noise=0.0, emit_strength=0.25, height=H),
        pupil=make_mat("pupil", "#1B1824", 0.3, noise=0.0, height=H),
        glint=make_mat("glint", "#FFFFFF", 0.2, noise=0.0, emit_strength=1.0, height=H),
        liner=make_mat("liner", "#2A1E24", 0.5, noise=0.0, height=H),
        mouth=make_mat("mouth", "#A9555A", 0.5, noise=0.0, height=H),
        blush=make_mat("blush", "#F4A3A3", 0.7, noise=0.0, height=H),
    )
    for k, (col, rough, metal, emit) in extra.items():
        M[k] = make_mat(k, col, rough, metal, noise=0.03, noise_scale=4, emit_strength=emit, height=H,
                        edge=0.25 if metal > 0.5 else 0.0)
    return M


# ----------------------------------------------------------------------------------------
# 蒼嵐・ソラ (Sora) - wind archer
# ----------------------------------------------------------------------------------------

def recipe_sora():
    H = 1.62
    J = mirror_joints({
        "hips": (0, 0, 0.86), "spine": (0, 0, 0.98), "chest": (0, 0, 1.12),
        "neck": (0, 0, 1.28), "head": (0, 0, 1.32), "head_top": (0, 0, 1.60),
        "shoulder.L": (0.115, 0, 1.235), "elbow.L": (0.265, 0.01, 1.03),
        "wrist.L": (0.365, -0.02, 0.84), "hand_end.L": (0.395, -0.03, 0.77),
        "hip.L": (0.072, 0, 0.82), "knee.L": (0.084, -0.015, 0.46),
        "ankle.L": (0.09, 0.015, 0.075), "toe.L": (0.09, -0.10, 0.02),
    })
    R = {"hips": (0.115, 0.085), "spine": (0.088, 0.07), "chest": (0.108, 0.08), "neck": 0.036,
         "shoulder": 0.043, "elbow": 0.032, "wrist": 0.026, "hip": 0.068, "knee": 0.046,
         "ankle": 0.032, "toe": 0.028}
    M = anime_mats(H, "#3E4F86", "#9FD3F0", "#3FB6C9", {
        "leggings": ("#283456", 0.75, 0.0, 0.0), "white": ("#F5F3EE", 0.7, 0.0, 0.0),
        "sky": ("#5DB8E6", 0.6, 0.0, 0.0), "gold": ("#E2BC58", 0.38, 0.85, 0.0),
        "wind": ("#6FF0E0", 0.2, 0.0, 2.0), "boot": ("#EDEBE6", 0.55, 0.0, 0.0),
    })
    parts = [(build_body(J, R, M["leggings"]), None)]
    hc, hr = Vector((0, -0.004, 1.43)), (0.102, 0.108, 0.118)
    parts.append((anime_head(hc, hr, M["skin"]), "head"))
    for sx in (-1, 1):
        parts += anime_eye(hc, hr, sx, M, size=1.05)
        parts.append((ellipsoid(f"ear{sx}", hc + Vector((0.098 * sx, 0.005, -0.012)), (0.012, 0.018, 0.026), M["skin"], 10, 8), "head"))
    parts += face_details(hc, hr, M, blush=True)

    # --- hair: cap, bangs, side locks, bob, ahoge, ribbon
    parts.append((hair_cap(hc, hr, M["hair"]), "head"))
    top = hc.z + hr[2]
    for i in range(7):
        x0 = -0.078 + i * 0.026
        sway = 0.008 * (1 if i % 2 else -1)
        parts.append((strand(f"bang{i}", [
            (x0 * 0.5, hc.y - 0.03, top - 0.005, 0.02),
            (x0 * 1.05, hc.y - hr[1] * 1.08, hc.z + 0.075, 0.019),
            (x0 * 1.12 + sway, hc.y - hr[1] * 1.06, hc.z + 0.035, 0.011),
            (x0 * 1.15 + sway * 1.5, hc.y - hr[1] * 1.0, hc.z + 0.005 - 0.01 * (i % 3 == 1), 0.0)],
            M["hair"]), "head"))
    for sx in (-1, 1):
        parts.append((strand(f"sidelock{sx}", [
            (0.08 * sx, hc.y - 0.04, hc.z + 0.07, 0.022), (0.106 * sx, hc.y - 0.055, hc.z - 0.04, 0.02),
            (0.104 * sx, hc.y - 0.05, hc.z - 0.15, 0.014), (0.098 * sx, hc.y - 0.04, hc.z - 0.23, 0.0)],
            M["hair"]), "head"))
        parts.append((strand(f"sidelock_tip{sx}", [  # two-tone tips
            (0.103 * sx, hc.y - 0.049, hc.z - 0.17, 0.0125), (0.098 * sx, hc.y - 0.04, hc.z - 0.232, 0.0)],
            M["hair2"]), "head"))
    for k in range(9):
        a = math.radians(15 + k * 18.75)
        ca, sa = math.cos(a), math.sin(a)
        parts.append((strand(f"bob{k}", [
            (0.55 * hr[0] * ca, hc.y + 0.55 * hr[1] * sa, top - 0.01, 0.03),
            (1.1 * hr[0] * ca, hc.y + 1.12 * hr[1] * sa, hc.z + 0.01, 0.032),
            (1.2 * hr[0] * ca, hc.y + 1.18 * hr[1] * sa, hc.z - 0.09, 0.022),
            (1.28 * hr[0] * ca, hc.y + 1.15 * hr[1] * sa, hc.z - 0.13 - 0.02 * (k % 2), 0.0)],
            M["hair" if k % 3 else "hair2"]), "head"))
    parts.append((strand("ahoge", [(0, hc.y - 0.01, top, 0.012), (0.0, hc.y - 0.035, top + 0.05, 0.01),
                                   (0.02, hc.y + 0.01, top + 0.075, 0.005), (0.035, hc.y + 0.03, top + 0.06, 0.0)],
                         M["hair"]), "head"))
    bow_c = hc + Vector((0, hr[1] * 1.05, 0.015))
    for sx in (-1, 1):
        parts.append((ellipsoid(f"ribbon_loop{sx}", bow_c + Vector((0.055 * sx, 0.01, 0.012)), (0.055, 0.016, 0.034),
                                M["sky"], 16, 10, rot=(0, 0.35 * sx, 0)), "head"))
        parts.append((ribbon(f"ribbon_tail{sx}", [bow_c + Vector((0.01 * sx, 0.012, -0.01)),
                                                   bow_c + Vector((0.04 * sx, 0.03, -0.12)),
                                                   bow_c + Vector((0.06 * sx, 0.045, -0.24))],
                             [0.035, 0.03, 0.026], (0, 1, 0), M["sky"], rim=M["gold"]), "head"))
    parts.append((ellipsoid("ribbon_knot", bow_c + Vector((0, 0.018, 0.0)), (0.018, 0.014, 0.018), M["gold"], 12, 8), "head"))

    # --- outfit
    parts += [
        (ellipsoid("blouse", (0, -0.004, 1.13), (0.122, 0.09, 0.15), M["white"], 28, 18), "chest"),
        (torus("collar", (0, 0, 1.255), 0.052, 0.014, M["sky"], scale=(1, 0.9, 1)), "chest"),
        (ellipsoid("wind_gem", (0, -0.062, 1.235), (0.014, 0.01, 0.017), M["wind"], 8, 6), "chest"),
        (torus("belt", (0, 0, 0.935), 0.11, 0.016, M["gold"], scale=(1, 0.8, 1.0)), "hips"),
    ]
    bodice = cyl_between("bodice", (0, 0, 0.93), (0, 0, 1.1), 0.106, 0.112, M["sky"], 24)
    for v in bodice.data.vertices:
        v.co.y = v.co.y * 0.8 - 0.004
    parts.append((bodice, "spine"))
    for nm, z0, z1, r0, r1, mat, open_front in (("skirt_in", 0.70, 0.94, 0.20, 0.112, M["white"], False),
                                                ("skirt_out", 0.76, 0.95, 0.215, 0.118, M["sky"], True)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=36, radius1=r0, radius2=r1, depth=z1 - z0)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, (z0 + z1) / 2))
        if open_front:
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.12], context="FACES")
        for v in bm.verts:  # pleats
            a = math.atan2(v.co.y, v.co.x)
            k = (z1 - v.co.z) / (z1 - z0)
            v.co.x += 0.008 * math.cos(a) * math.sin(a * 14) * k
            v.co.y = v.co.y * 0.85 + 0.008 * math.sin(a) * math.sin(a * 14) * k
        sk = bc.mesh_from_bmesh(nm, bm)
        set_mat(sk, mat, [M["gold"]])
        solidify(sk, 0.008, rim_mat_offset=1)
        subsurf(sk, 1)
        bc.apply_modifiers(sk)
        shade(sk, True, 180)
        parts.append((sk, "hips"))
    for s, sx in (("L", 1), ("R", -1)):
        el, wr = Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        sl = cyl_between(f"sleeve.{s}", el.lerp(wr, 0.1), wr + (wr - el).normalized() * 0.04, 0.036, 0.062, M["white"], 20, cap=False)
        sl.data.materials.append(M["sky"])
        solidify(sl, 0.006, rim_mat_offset=1)
        bc.apply_modifiers(sl)
        parts += [
            (sl, f"forearm.{s}"),
            (ellipsoid(f"puff.{s}", Vector(J[f"shoulder.{s}"]) + Vector((0.03 * sx, 0, -0.005)), (0.05, 0.05, 0.042), M["white"], 18, 12), f"upper_arm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.026, 0.022, 0.04), M["skin"], 14, 10), f"hand.{s}"),
            (cyl_between(f"boot.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.07)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, -0.02)),
                         0.05, 0.038, M["boot"], 18), f"shin.{s}"),
            (torus(f"boot_cuff.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.07)), 0.05, 0.009, M["gold"]), f"shin.{s}"),
            (rounded_box(f"boot_foot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.035, -0.04)), (0.036, 0.085, 0.034),
                         M["boot"], 0.025, 3), f"foot.{s}"),
        ]
    # scarf: around the neck and streaming behind the left shoulder
    parts.append((torus("scarf_wrap", (0, 0.004, 1.275), 0.055, 0.02, M["sky"], scale=(1, 0.95, 0.8)), "chest"))
    parts.append((ribbon("scarf_tail", [(0.03, 0.05, 1.27), (0.11, 0.12, 1.22), (0.2, 0.2, 1.1), (0.27, 0.27, 0.95),
                                        (0.3, 0.32, 0.8)], [0.07, 0.075, 0.07, 0.062, 0.05], (0.6, -0.8, 0.2),
                         M["sky"], rim=M["white"]), "chest"))
    # bow in the left hand
    gx, gy = 0.385, -0.025
    parts.append((strand("bow", [(gx, gy + 0.11, 1.24, 0.008), (gx, gy - 0.02, 1.06, 0.012), (gx, gy - 0.005, 0.81, 0.016),
                                 (gx, gy - 0.02, 0.56, 0.012), (gx, gy + 0.11, 0.38, 0.008)], M["white"]), "hand.L"))
    parts.append((cyl_between("bowstring", (gx, gy + 0.115, 1.235), (gx, gy + 0.115, 0.385), 0.0015, 0.0015, M["gold"], 6), "hand.L"))
    parts.append((ellipsoid("bow_gem", (gx, gy - 0.025, 0.81), (0.012, 0.01, 0.02), M["wind"], 8, 6), "hand.L"))
    for k, z in enumerate((1.2, 0.42)):
        parts.append((ellipsoid(f"bow_tip{k}", (gx, gy + 0.11, z), (0.012, 0.012, 0.03), M["gold"], 8, 6), "hand.L"))
    return J, R, M, parts, H, {"Idle": idle_keys, "Shoot": sora_shoot_keys}


def sora_shoot_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (12, -75, -10, 30), (22, -80, -12, 34), (34, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.L"], f, x=ua * 0.2, z=ua * -0.9)
        key_rot(P["forearm.L"], f, x=fa)
        key_rot(P["upper_arm.R"], f, x=ua * 0.5, z=ua * 0.5)
        key_rot(P["chest"], f, z=ch * 0.5)
        key_rot(P["head"], f, z=-ch * 0.4)


# ----------------------------------------------------------------------------------------
# 緋槍・カイ (Kai) - flame spearman
# ----------------------------------------------------------------------------------------

def recipe_kai():
    H = 2.12  # spear tip
    J = mirror_joints({
        "hips": (0, 0, 0.95), "spine": (0, 0, 1.09), "chest": (0, 0, 1.27),
        "neck": (0, 0, 1.44), "head": (0, 0, 1.48), "head_top": (0, 0, 1.76),
        "shoulder.L": (0.16, 0, 1.395), "elbow.L": (0.335, 0.01, 1.16),
        "wrist.L": (0.46, -0.03, 0.935), "hand_end.L": (0.5, -0.045, 0.855),
        "hip.L": (0.088, 0, 0.9), "knee.L": (0.103, -0.015, 0.5),
        "ankle.L": (0.108, 0.015, 0.085), "toe.L": (0.108, -0.12, 0.025),
    })
    R = {"hips": (0.125, 0.095), "spine": (0.108, 0.08), "chest": (0.142, 0.095), "neck": 0.044,
         "shoulder": 0.052, "elbow": 0.04, "wrist": 0.032, "hip": 0.078, "knee": 0.054,
         "ankle": 0.038, "toe": 0.033}
    M = anime_mats(H, "#23202B", "#C8323A", "#E0612F", {
        "pants": ("#3B3846", 0.8, 0.0, 0.0), "coat": ("#2E2C3A", 0.7, 0.0, 0.0),
        "crimson": ("#B92F38", 0.65, 0.0, 0.0), "gold": ("#DDAE4E", 0.36, 0.85, 0.0),
        "steel": ("#C9D0D8", 0.3, 0.85, 0.0), "flame": ("#FF7A33", 0.3, 0.0, 2.5),
        "glove": ("#1A1820", 0.6, 0.0, 0.0),
    })
    parts = [(build_body(J, R, M["pants"]), None)]
    hc, hr = Vector((0, -0.004, 1.59)), (0.104, 0.11, 0.122)
    parts.append((anime_head(hc, hr, M["skin"]), "head"))
    for sx in (-1, 1):
        parts += anime_eye(hc, hr, sx, M, size=0.92, dz=-0.008, dx=0.044)
        parts.append((ellipsoid(f"ear{sx}", hc + Vector((0.1 * sx, 0.005, -0.01)), (0.012, 0.019, 0.028), M["skin"], 10, 8), "head"))
    parts += face_details(hc, hr, M, blush=False, mouth_w=0.014)

    # --- hair: spiky crown, bangs, long ponytail with crimson tips
    parts.append((hair_cap(hc, hr, M["hair"], face_open=0.05), "head"))
    top = hc.z + hr[2]
    for k in range(12):
        a = math.radians(-10 + k * 200 / 11)  # around the sides and back
        ca, sa = math.cos(a), math.sin(a)
        up = 0.05 * math.cos(k * 1.7)
        parts.append((strand(f"spike{k}", [
            (0.4 * hr[0] * ca, hc.y + 0.4 * hr[1] * sa, top - 0.01, 0.034),
            (1.05 * hr[0] * ca, hc.y + 1.05 * hr[1] * sa, hc.z + 0.07 + up * 0.4, 0.03),
            (1.45 * hr[0] * ca, hc.y + 1.4 * hr[1] * sa, hc.z + 0.02 + up, 0.0)],
            M["hair2" if k in (2, 7, 10) else "hair"]), "head"))
    for i in range(5):
        x0 = -0.07 + i * 0.035
        parts.append((strand(f"bang{i}", [
            (x0 * 0.4, hc.y - 0.03, top, 0.024),
            (x0 * 1.0, hc.y - hr[1] * 1.1, hc.z + 0.08, 0.02),
            (x0 * 1.3 + 0.02, hc.y - hr[1] * 1.05, hc.z + 0.02 - 0.012 * (i % 2), 0.0)],
            M["hair"]), "head"))
    pt0 = hc + Vector((0, hr[1] * 0.95, 0.03))
    parts.append((torus("hair_tie", pt0 + Vector((0, 0.03, -0.01)), 0.026, 0.01, M["gold"], rot=(math.pi / 2 - 0.4, 0, 0)), "head"))
    parts.append((strand("ponytail", [(pt0.x, pt0.y + 0.03, pt0.z - 0.01, 0.034), (0.0, pt0.y + 0.09, pt0.z - 0.12, 0.038),
                                      (0.02, pt0.y + 0.1, pt0.z - 0.3, 0.03), (0.03, pt0.y + 0.08, pt0.z - 0.46, 0.018),
                                      (0.035, pt0.y + 0.06, pt0.z - 0.58, 0.0)], M["hair"]), "head"))
    parts.append((strand("ponytail_tip", [(0.032, pt0.y + 0.075, pt0.z - 0.48, 0.016), (0.035, pt0.y + 0.06, pt0.z - 0.585, 0.0)],
                         M["hair2"]), "head"))

    # --- outfit: long coat with open front, high collar, sash, one pauldron
    parts += [
        (ellipsoid("shirt", (0, -0.004, 1.25), (0.15, 0.1, 0.19), M["coat"], 28, 18), "chest"),
        (torus("belt", (0, 0, 0.99), 0.13, 0.02, M["crimson"], scale=(1, 0.8, 1.1)), "hips"),
        (rounded_box("buckle", (0, -0.106, 0.99), (0.025, 0.01, 0.022), M["gold"], 0.006), "hips"),
        (ellipsoid("flame_gem", (0, -0.118, 0.99), (0.011, 0.008, 0.014), M["flame"], 8, 6), "hips"),
    ]
    collar = cyl_between("collar", (0, 0, 1.41), (0, 0.008, 1.495), 0.076, 0.094, M["coat"], 24, cap=False)
    bm = bmesh.new(); bm.from_mesh(collar.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.07], context="FACES")
    bm.to_mesh(collar.data); bm.free()
    collar.data.materials.append(M["gold"])
    solidify(collar, 0.008, rim_mat_offset=1); bc.apply_modifiers(collar); shade(collar, True, 180)
    parts.append((collar, "neck"))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=0.3, radius2=0.15, depth=0.6)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0.01, 0.72))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.06], context="FACES")
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        k = (1.02 - v.co.z) / 0.6
        v.co.y *= 0.82
        v.co.x += 0.01 * math.cos(a) * math.sin(a * 8) * k
    coat = bc.mesh_from_bmesh("coat_tails", bm)
    set_mat(coat, M["coat"], [M["gold"]])
    solidify(coat, 0.012, rim_mat_offset=1); subsurf(coat, 1); bc.apply_modifiers(coat); shade(coat, True, 180)
    parts.append((coat, "hips"))
    parts.append((ribbon("sash", [(0.11, -0.07, 0.97), (0.14, -0.06, 0.85), (0.15, -0.05, 0.7), (0.155, -0.04, 0.58)],
                         [0.05, 0.05, 0.045, 0.04], (0.3, -1, 0), M["crimson"], rim=M["gold"]), "hips"))
    parts.append((ellipsoid("pauldron.L", Vector(J["shoulder.L"]) + Vector((0.035, 0, 0.02)), (0.085, 0.09, 0.06), M["coat"], 20, 12,
                            rot=(0, -0.45, 0)), "upper_arm.L"))
    parts.append((torus("pauldron_rim.L", Vector(J["shoulder.L"]) + Vector((0.05, 0, -0.005)), 0.08, 0.01, M["gold"],
                        rot=(0, -0.45, 0), scale=(1, 1.1, 1)), "upper_arm.L"))
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        parts += [
            (cyl_between(f"sleeve_up.{s}", sh, el, 0.058, 0.05, M["coat"], 18), f"upper_arm.{s}"),
            (cyl_between(f"sleeve_lo.{s}", el, wr, 0.05, 0.046, M["coat"], 18), f"forearm.{s}"),
            (torus(f"cuff.{s}", wr, 0.046, 0.012, M["crimson"],
                   rot=Vector((0, 0, 1)).rotation_difference(wr - el).to_euler()), f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.031, 0.027, 0.046), M["glove"], 14, 10), f"hand.{s}"),
            (cyl_between(f"boot.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.04)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, -0.02)),
                         0.06, 0.046, M["coat"], 18), f"shin.{s}"),
            (torus(f"boot_cuff.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.04)), 0.06, 0.01, M["gold"]), f"shin.{s}"),
            (rounded_box(f"boot_foot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.04, -0.045)), (0.043, 0.1, 0.038),
                         M["coat"], 0.028, 3), f"foot.{s}"),
        ]
    # spear in the right hand
    px, py = -0.48, -0.04
    parts += [
        (cyl_between("spear_shaft", (px, py, 0.02), (px, py, 1.86), 0.015, 0.017, M["crimson"], 12), "hand.R"),
        (torus("spear_band_a", (px, py, 0.89), 0.019, 0.006, M["gold"]), "hand.R"),
        (torus("spear_band_b", (px, py, 1.84), 0.022, 0.008, M["gold"]), "hand.R"),
        (ellipsoid("spear_guard", (px, py, 1.875), (0.05, 0.022, 0.018), M["gold"], 16, 8), "hand.R"),
        (ellipsoid("spear_blade", (px, py, 2.0), (0.034, 0.009, 0.13), M["steel"], 16, 10), "hand.R"),
        (ellipsoid("spear_flame", (px, py - 0.004, 1.99), (0.017, 0.007, 0.095), M["flame"], 12, 8), "hand.R"),
        (strand("spear_tassel", [(px, py, 1.86, 0.018), (px - 0.015, py + 0.01, 1.74, 0.02), (px - 0.03, py + 0.02, 1.62, 0.0)],
                M["crimson"]), "hand.R"),
    ]
    return J, R, M, parts, H, {"Idle": idle_keys, "Thrust": kai_thrust_keys}


def kai_thrust_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (10, 25, -40, 15), (16, -55, -10, -20), (30, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["chest"], f, z=ch * 0.6, x=-abs(ch) * 0.2)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.3)


bc.RECIPES.update(sora=recipe_sora, kai=recipe_kai)

if __name__ == "__main__":
    bc.main()
