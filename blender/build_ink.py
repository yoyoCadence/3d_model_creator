"""Ink-wash wuxia style (水墨武俠) - original character 「墨白」 Mo Bai, a wandering swordsman.

Modelled in an ink palette (paper white, wash greys, ink black, one red accent) so it reads even in PBR;
the full look comes from the real-time ink shader (site/js/viewer.js, setShading('ink')): luminance ->
three ink tones, red accents preserved, paper grain, thick brush outlines on a paper background.

Details: topknot + jade hairpin, long high ponytail with white ribbons, framing locks, ink-stroke face
(sharp rising brows, almond eyes), cross-collar robe, wide sleeves drooping under gravity, long robe with a
front slit and folds, black sash with long tails and a red seal, cloth boots, bamboo hat slung on the back,
jian (straight sword) with red tassel, scabbard, long flowing scarf. Idle + Slash clips, Blink morph.

Usage: blender -b --factory-startup -P blender/build_ink.py -- --char mobai --out assets/models/ink/mobai.glb
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
import build_chibi  # noqa: E402,F401
from build_anime import anime_head, face_y, hair_cap, ribbon, strand  # noqa: E402
from build_character import (build_body, cyl_between, ellipsoid, idle_keys, key_rot, make_mat,  # noqa: E402
                             mirror_joints, rounded_box, set_mat, shade, solidify, subsurf, tag_blink, torus)

bc.STYLE.update(gradient=(0.95, 1.03), ao_in_albedo=0.25, normal_map=False, coat=0.0)


def robe_cone(name, z_top, z_bot, r_top, r_bot, mat, rim, slit=None, folds=9, amp=0.016, seg=64, yscale=0.85):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r_bot, radius2=r_top, depth=z_top - z_bot)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, (z_top + z_bot) / 2))
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-4], cuts=6)
    if slit:  # (half width, y sign) open slit down the front/back
        hw, ys = slit
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.calc_center_median().x) < hw and
                                   f.calc_center_median().y * ys > 0 and f.calc_center_median().z < z_top - 0.12], context="FACES")
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        k = min(1.0, max(0.0, (z_top - v.co.z) / (z_top - z_bot)))
        r = 1 + amp * 6 * math.sin(a * folds + 0.7) * k ** 1.5  # deepening folds toward the hem
        v.co.x *= r
        v.co.y *= r * yscale
        v.co.z += 0.01 * math.cos(a * folds) * k ** 2
    obj = bc.mesh_from_bmesh(name, bm)
    set_mat(obj, mat, [rim])
    solidify(obj, 0.008, rim_mat_offset=1)
    subsurf(obj, 1)
    bc.apply_modifiers(obj)
    shade(obj, True, 180)
    return obj


def wide_sleeve(name, sh, wr, mat, rim, r1=0.065, r2=0.17, droop=0.16):
    sh, wr = Vector(sh), Vector(wr)
    d = (wr - sh)
    end = wr + d.normalized() * 0.08
    obj = cyl_between(name, sh.lerp(wr, 0.15), end, r1, r2, mat, 32, cap=False)
    axis = (end - sh).normalized()
    L = (end - sh).length
    for v in obj.data.vertices:  # the underside of a wide sleeve hangs down
        t = max(0.0, (v.co - sh).dot(axis) / L)
        foot = sh + axis * (v.co - sh).dot(axis)
        below = (v.co - foot).z < 0
        if below:
            v.co.z -= droop * t ** 2
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1)
    bm.to_mesh(obj.data); bm.free()
    obj.data.materials.append(rim)
    solidify(obj, 0.007, rim_mat_offset=1)
    subsurf(obj, 1)
    bc.apply_modifiers(obj)
    shade(obj, True, 180)
    return obj


def recipe_mobai():
    H = 1.85
    J = mirror_joints({
        "hips": (0, 0, 0.98), "spine": (0, 0, 1.12), "chest": (0, 0, 1.3),
        "neck": (0, 0, 1.47), "head": (0, 0, 1.51), "head_top": (0, 0, 1.8),
        "shoulder.L": (0.165, 0, 1.42), "elbow.L": (0.35, 0.01, 1.18),
        "wrist.L": (0.47, -0.02, 0.95), "hand_end.L": (0.51, -0.035, 0.87),
        "hip.L": (0.09, 0, 0.93), "knee.L": (0.1, -0.015, 0.52),
        "ankle.L": (0.105, 0.015, 0.09), "toe.L": (0.105, -0.12, 0.03),
    })
    R = {"hips": (0.13, 0.1), "spine": (0.112, 0.085), "chest": (0.14, 0.1), "neck": 0.045,
         "shoulder": 0.05, "elbow": 0.04, "wrist": 0.032, "hip": 0.08, "knee": 0.055,
         "ankle": 0.04, "toe": 0.035}
    M = dict(
        skin=make_mat("skin", "#EEDAC6", 0.6, noise=0.02, height=H),
        white=make_mat("white", "#F2EFE8", 0.75, noise=0.04, noise_scale=8, height=H),
        grey=make_mat("grey", "#D3CFC6", 0.75, noise=0.05, noise_scale=8, height=H),
        wash=make_mat("wash", "#8F8B84", 0.7, noise=0.05, height=H),
        dark=make_mat("dark", "#2A2A2C", 0.6, noise=0.04, height=H),
        ink=make_mat("ink", "#141416", 0.5, noise=0.03, height=H),
        red=make_mat("red", "#B8322A", 0.5, noise=0.03, height=H),
        jade=make_mat("jade", "#7FB59A", 0.25, noise=0.03, height=H),
        straw=make_mat("straw", "#CDB98D", 0.8, noise=0.12, noise_scale=40, height=H),
        steel=make_mat("steel", "#BCC5CF", 0.25, 0.9, noise=0.03, edge=0.3, height=H),
        bronze=make_mat("bronze", "#8A6A3A", 0.4, 0.8, noise=0.05, edge=0.25, height=H),
        lip=make_mat("lip", "#B57A6E", 0.5, noise=0.0, height=H),
    )
    parts = [(build_body(J, R, M["white"]), None)]
    hc, hr = Vector((0, -0.005, 1.6)), (0.093, 0.104, 0.122)
    parts.append((anime_head(hc, hr, M["skin"]), "head"))
    # --- ink-stroke face
    for sx, side in ((-1, "R"), (1, "L")):
        x, dz = 0.04 * sx, -0.006
        c = Vector((x, face_y(hc, hr, x, dz) + 0.001, hc.z + dz))
        parts.append((tag_blink(ellipsoid(f"eye.{side}", c, (0.02, 0.003, 0.0075), M["ink"], 16, 8, rot=(0, -0.12 * sx, 0.3 * sx)),
                                side, hc.z + dz), "head"))
        lid = []
        for i in range(6):
            u = -1 + 2 * i / 5
            px = x + u * 0.026 * sx
            pz = dz + 0.008 * (1 - u * u) + 0.007 * max(u, 0)
            lid.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, 0.003 if abs(u) < 0.8 else 0.0012))
        parts.append((tag_blink(strand(f"lid.{side}", lid, M["ink"]), side, hc.z + dz), "head"))
        brow = []
        for i in range(5):
            u = -1 + 2 * i / 4
            px = x + u * 0.03 * sx
            pz = dz + 0.032 + 0.014 * (u + 1) / 2  # sharply rising toward the temple
            brow.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, 0.0045 if u < 0.6 else 0.0015))
        parts.append((strand(f"brow.{side}", brow, M["ink"]), "head"))
        parts.append((ellipsoid(f"ear.{side}", hc + Vector((0.09 * sx, 0.01, -0.012)), (0.011, 0.018, 0.026), M["skin"], 10, 8), "head"))
    parts.append((ellipsoid("nose", Vector((0, face_y(hc, hr, 0, -0.035) - 0.004, hc.z - 0.035)), (0.009, 0.011, 0.024), M["skin"], 10, 8,
                            rot=(0.25, 0, 0)), "head"))
    mouth = []
    for i in range(5):
        u = -1 + 2 * i / 4
        px, pz = u * 0.017, -0.072 - 0.002 * u * u
        mouth.append((px, face_y(hc, hr, px, pz) - 0.0015, hc.z + pz, 0.0018 if abs(u) < 0.9 else 0.0008))
    parts.append((strand("mouth", mouth, M["lip"]), "head"))

    # --- hair: cap, parted strands, framing locks, topknot + jade pin, long high ponytail, ribbons
    parts.append((hair_cap(hc, hr, M["ink"], face_open=0.06), "head"))
    top = hc.z + hr[2]
    for sx in (-1, 1):
        for k in range(3):
            x0 = 0.015 * sx + 0.025 * k * sx
            parts.append((strand(f"part{sx}{k}", [(x0 * 0.5, -0.04, top + 0.005, 0.02), (x0 * 1.6, -hr[1] * 1.03, hc.z + 0.085, 0.017),
                                                  (x0 * 2.4 + 0.02 * sx, -hr[1] * 0.95, hc.z + 0.04, 0.0)], M["ink"]), "head"))
        parts.append((strand(f"lock{sx}", [(0.07 * sx, -0.07, hc.z + 0.07, 0.016), (0.1 * sx, -0.085, hc.z - 0.03, 0.013),
                                           (0.095 * sx, -0.08, hc.z - 0.15, 0.01), (0.11 * sx, -0.07, hc.z - 0.26, 0.0)], M["ink"]), "head"))
    knot = hc + Vector((0, 0.03, hr[2] + 0.02))
    parts += [
        (ellipsoid("topknot", knot, (0.045, 0.045, 0.04), M["ink"], 20, 12), "head"),
        (torus("knot_band", knot + Vector((0, 0, -0.02)), 0.038, 0.008, M["white"]), "head"),
        (cyl_between("hairpin", knot + Vector((-0.09, 0.0, 0.01)), knot + Vector((0.09, 0.0, 0.025)), 0.0045, 0.0035, M["jade"], 8), "head"),
        (ellipsoid("hairpin_bead", knot + Vector((-0.095, 0.0, 0.008)), (0.01, 0.01, 0.01), M["jade"], 10, 8), "head"),
    ]
    tail = [(knot.x, knot.y + 0.03, knot.z - 0.02, 0.038), (0.0, knot.y + 0.1, knot.z - 0.08, 0.042), (0.02, 0.16, hc.z - 0.05, 0.04),
            (0.04, 0.17, hc.z - 0.3, 0.032), (0.03, 0.15, hc.z - 0.55, 0.02), (0.05, 0.13, hc.z - 0.72, 0.0)]
    parts.append((strand("ponytail", tail, M["ink"], res=3), "head"))
    for sx in (-1, 1):
        p0 = knot + Vector((0.02 * sx, 0.04, -0.02))
        parts.append((ribbon(f"hair_ribbon{sx}", [p0, p0 + Vector((0.05 * sx, 0.06, -0.15)), p0 + Vector((0.09 * sx, 0.1, -0.35)),
                                                   p0 + Vector((0.08 * sx, 0.13, -0.55))], [0.025, 0.024, 0.022, 0.018], (sx * 0.3, 1, 0),
                             M["white"], thickness=0.003), "head"))

    # --- robes
    parts += [
        (ellipsoid("robe_top", (0, -0.002, 1.27), (0.15, 0.104, 0.2), M["grey"], 32, 20), "chest"),
        (cyl_between("collar_inner", (0, 0, 1.4), (0, 0.005, 1.5), 0.06, 0.054, M["white"], 24, cap=False), "neck"),
    ]
    for sx in (-1, 1):  # cross collar (left over right)
        parts.append((ribbon(f"collar{sx}", [(0.06 * sx, -0.06, 1.47), (0.0, -0.11, 1.33), (-0.07 * sx, -0.11, 1.12)],
                             [0.035, 0.035, 0.03], (0, -1, 0.2), M["dark"], thickness=0.004), "chest"))
    parts += [
        (torus("sash", (0, 0, 1.02), 0.13, 0.035, M["ink"], scale=(1, 0.82, 1.4)), "hips"),
        (ellipsoid("sash_knot", (0.06, -0.11, 1.02), (0.03, 0.02, 0.03), M["ink"], 12, 8), "hips"),
        (rounded_box("seal", (-0.07, -0.118, 1.02), (0.016, 0.004, 0.016), M["red"], 0.003, 2), "hips"),
    ]
    for k, (dx, ln) in enumerate(((0.05, 0.45), (0.075, 0.38))):
        p0 = Vector((dx, -0.115, 1.0))
        parts.append((ribbon(f"sash_tail{k}", [p0, p0 + Vector((0.01, -0.02, -ln * 0.5)), p0 + Vector((0.025, -0.01, -ln))],
                             [0.035, 0.033, 0.03], (0, -1, 0), M["ink"], thickness=0.004), "hips"))
    parts.append((robe_cone("robe_lower", 1.04, 0.12, 0.145, 0.3, M["grey"], M["dark"], slit=(0.04, -1)), "hips"))
    parts.append((robe_cone("robe_inner", 0.98, 0.1, 0.12, 0.2, M["white"], M["wash"], folds=7, amp=0.008), "hips"))
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        parts += [
            (ellipsoid(f"shoulder_robe.{s}", sh + Vector((0.0, 0, 0.0)), (0.056, 0.06, 0.045), M["grey"], 18, 12), f"upper_arm.{s}"),
            (wide_sleeve(f"sleeve_up.{s}", sh, el, M["grey"], M["dark"], r1=0.06, r2=0.08, droop=0.03), f"upper_arm.{s}"),
            (wide_sleeve(f"sleeve.{s}", el, wr, M["grey"], M["dark"], r1=0.075, r2=0.17, droop=0.17), f"forearm.{s}"),
            (cyl_between(f"cuff_inner.{s}", el.lerp(wr, 0.6), wr, 0.04, 0.036, M["white"], 16), f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.03, 0.026, 0.045), M["skin"], 14, 10), f"hand.{s}"),
            (cyl_between(f"boot.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.12)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, -0.02)),
                         0.052, 0.045, M["ink"], 18), f"shin.{s}"),
            (rounded_box(f"boot_foot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.045, -0.045)), (0.04, 0.1, 0.035), M["ink"],
                         0.028, 3), f"foot.{s}"),
        ]
    # long flowing scarf (飄帶) from the shoulders
    parts.append((ribbon("scarf", [(-0.14, 0.06, 1.44), (-0.18, 0.16, 1.3), (-0.26, 0.24, 1.05), (-0.3, 0.3, 0.75), (-0.27, 0.36, 0.42),
                                   (-0.32, 0.42, 0.15)], [0.05, 0.07, 0.08, 0.08, 0.07, 0.06], (-0.7, 0.7, 0), M["white"],
                         thickness=0.003, rim=M["wash"]), "chest"))
    # bamboo hat slung on the back + cords
    hat_c = Vector((0.0, 0.19, 1.18))
    hat = cyl_between("douli", hat_c + Vector((0, -0.01, 0)), hat_c + Vector((0, 0.1, 0)), 0.26, 0.012, M["straw"], 48)
    for v in hat.data.vertices:  # concentric weave ridges
        rr = math.hypot(v.co.x - hat_c.x, v.co.z - hat_c.z)
        v.co.y += 0.004 * math.sin(rr * 90)
    shade(hat, True, 180)
    parts.append((hat, "chest"))
    parts.append((torus("douli_rim", hat_c + Vector((0, -0.008, 0)), 0.26, 0.008, M["wash"], rot=(math.pi / 2, 0, 0), seg=48), "chest"))
    for sx in (-1, 1):
        parts.append((strand(f"hat_cord{sx}", [(0.22 * sx, 0.18, 1.2, 0.004), (0.16 * sx, -0.02, 1.38, 0.004),
                                               (0.07 * sx, -0.08, 1.45, 0.003)], M["dark"]), "chest"))
    # jian in the right hand, pointing down; red tassel from the pommel
    gx, gy = -0.49, -0.035
    parts += [
        (cyl_between("grip", (gx, gy, 0.86), (gx, gy, 1.0), 0.016, 0.016, M["ink"], 12), "hand.R"),
        (ellipsoid("pommel", (gx, gy, 1.01), (0.02, 0.02, 0.016), M["bronze"], 12, 8), "hand.R"),
        (ellipsoid("guard", (gx, gy, 0.855), (0.055, 0.022, 0.014), M["bronze"], 16, 8), "hand.R"),
        (rounded_box("blade", (gx, gy, 0.47), (0.016, 0.0035, 0.38), M["steel"], 0.0025, 2, taper_bottom=0.55), "hand.R"),
        (rounded_box("blade_ridge", (gx, gy - 0.0035, 0.47), (0.002, 0.0015, 0.37), M["steel"], 0.001, 1, taper_bottom=0.5), "hand.R"),
        (strand("tassel_cord", [(gx, gy, 1.02, 0.003), (gx + 0.01, gy + 0.01, 0.97, 0.003), (gx + 0.02, gy + 0.015, 0.93, 0.003)],
                M["red"]), "hand.R"),
        (strand("tassel", [(gx + 0.02, gy + 0.015, 0.93, 0.016), (gx + 0.024, gy + 0.02, 0.86, 0.02), (gx + 0.028, gy + 0.024, 0.79, 0.0)],
                M["red"]), "hand.R"),
    ]
    # scabbard at the left hip
    parts += [
        (cyl_between("scabbard", (0.17, 0.02, 1.0), (0.33, 0.26, 0.36), 0.02, 0.016, M["ink"], 12), "hips"),
        (torus("scab_ring_a", Vector((0.17, 0.02, 1.0)).lerp(Vector((0.33, 0.26, 0.36)), 0.1), 0.022, 0.005, M["bronze"],
               rot=Vector((0, 0, 1)).rotation_difference(Vector((0.16, 0.24, -0.64))).to_euler()), "hips"),
        (ellipsoid("scab_tip", (0.33, 0.26, 0.36), (0.022, 0.022, 0.022), M["bronze"], 10, 8), "hips"),
    ]
    return J, R, M, parts, H, {"Idle": idle_keys, "Slash": mobai_slash_keys}


def mobai_slash_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (12, -120, -30, 20), (18, -30, -10, -25), (24, 20, 10, -30), (40, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua, z=ua * 0.2)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["chest"], f, z=ch, x=-abs(ch) * 0.2)
        key_rot(P["head"], f, z=-ch * 0.5)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.2, z=-abs(ua) * 0.15)


bc.RECIPES.update(mobai=recipe_mobai)

if __name__ == "__main__":
    bc.main()
