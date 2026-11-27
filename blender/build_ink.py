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
from mathutils import Matrix, Vector

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
    pony = bc.spring("hairTail", tail[1:], "head")
    parts.append((strand("ponytail", tail, M["ink"], res=3), pony))
    for sx in (-1, 1):
        p0 = knot + Vector((0.02 * sx, 0.04, -0.02))
        rp = [p0, p0 + Vector((0.05 * sx, 0.06, -0.15)), p0 + Vector((0.09 * sx, 0.1, -0.35)), p0 + Vector((0.08 * sx, 0.13, -0.55))]
        parts.append((ribbon(f"hair_ribbon{sx}", rp, [0.025, 0.024, 0.022, 0.018], (sx * 0.3, 1, 0), M["white"], thickness=0.003),
                      bc.spring(f"clothRibbon{'LR'[sx > 0]}", rp, "head")))

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
        sp = [p0, p0 + Vector((0.01, -0.03, -ln * 0.5)), p0 + Vector((0.025, -0.04, -ln))]
        parts.append((ribbon(f"sash_tail{k}", sp, [0.035, 0.033, 0.03], (0, -1, 0), M["ink"], thickness=0.004),
                      bc.spring(f"clothSash{k}", sp, "hips")))
    robe = bc.radial_springs("skirt", 0.9, 0.12, 0.17, 0.31, n=12, segs=4, parent="hips", yscale=0.85)
    parts.append((robe_cone("robe_lower", 1.04, 0.12, 0.145, 0.3, M["grey"], M["dark"], slit=(0.04, -1)), robe))
    parts.append((robe_cone("robe_inner", 0.98, 0.1, 0.12, 0.2, M["white"], M["wash"], folds=7, amp=0.008), robe))
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
    sp = [(-0.14, 0.06, 1.44), (-0.18, 0.16, 1.3), (-0.26, 0.24, 1.05), (-0.3, 0.3, 0.75), (-0.27, 0.36, 0.42), (-0.32, 0.42, 0.15)]
    parts.append((ribbon("scarf", sp, [0.05, 0.07, 0.08, 0.08, 0.07, 0.06], (-0.7, 0.7, 0), M["white"], thickness=0.003, rim=M["wash"]),
                  bc.spring("clothScarf", sp, "chest")))
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


@bc.hit(16)  # blade cuts down across the front
def mobai_slash_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (12, -120, -30, 20), (18, -30, -10, -25), (24, 20, 10, -30), (40, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua, z=ua * 0.2)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["chest"], f, z=ch, x=-abs(ch) * 0.2)
        key_rot(P["head"], f, z=-ch * 0.5)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.2, z=-abs(ua) * 0.15)


# ----------------------------------------------------------------------------------------
# 青蓮 Qing Lian - wandering swordswoman with an oil-paper umbrella (Mo Bai's companion)
# ----------------------------------------------------------------------------------------

def _frame(z, hint):
    """Euler with local Z along `z` and local Y leaning towards `hint`."""
    z = Vector(z).normalized()
    x = Vector(hint).cross(z).normalized()
    return Matrix((x, z.cross(x), z)).transposed().to_euler()


def lotus(prefix, c, up, M, scale=1.0):
    """Two rings of cupped petals around a seed pod."""
    up = Vector(up).normalized()
    side = up.cross(Vector((0, 0, 1)) if abs(up.z) < 0.9 else Vector((1, 0, 0))).normalized()
    fwd = up.cross(side)
    out = [(cyl_between(f"{prefix}_pod", c, c + up * 0.014 * scale, 0.011 * scale, 0.013 * scale, M["pod"], 12))]
    for ring, (n, tilt, rad, size, mat) in enumerate(((6, 0.45, 0.012, 0.032, "lotus_in"), (8, 0.95, 0.018, 0.038, "lotus_out"))):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * ring) / n
            radial = side * math.cos(a) + fwd * math.sin(a)
            d = (up * math.cos(tilt) + radial * math.sin(tilt)).normalized()
            pc = c + radial * rad * scale + d * size * 0.8 * scale
            out.append(ellipsoid(f"{prefix}_petal{ring}{k}", pc, (0.014 * scale, 0.005 * scale, size * scale), M[mat], 12, 8,
                                 rot=_frame(d, radial)))
    return out


def umbrella(prefix, base, d, M, R=0.46, length=0.86, gores=16):
    """Oil-paper umbrella: alternating paper gores, ribs + stretchers underneath, red rim and finial."""
    d = Vector(d).normalized()
    apex = base + d * length
    rot = Vector((0, 0, 1)).rotation_difference(d).to_euler()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=gores * 2, radius1=R, radius2=0.02, depth=0.15)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-4], cuts=3)
    for v in bm.verts:  # slight scallop between ribs
        a = math.atan2(v.co.y, v.co.x)
        k = (0.075 - v.co.z) / 0.15
        v.co.z -= 0.012 * abs(math.sin(a * gores / 2)) * k
    can = bc.mesh_from_bmesh(f"{prefix}_canopy", bm)
    set_mat(can, M["paper"], [M["paper_b"]])
    for poly in can.data.polygons:
        c = poly.center
        poly.material_index = int(((math.atan2(c.y, c.x) + math.pi) / (2 * math.pi) * gores)) % 2
    can.rotation_euler = rot
    can.location = apex - d * 0.075
    bc.apply_transform(can)
    solidify(can, 0.004)
    bc.apply_modifiers(can)
    shade(can, True, 180)
    out = [can]
    side = d.cross(Vector((0, 0, 1))).normalized()
    fwd = d.cross(side)
    rim_c = apex - d * 0.15
    runner = base + d * (length * 0.62)
    for k in range(gores):
        a = 2 * math.pi * k / gores
        r_dir = side * math.cos(a) + fwd * math.sin(a)
        tip = rim_c + r_dir * R - d * 0.006
        out.append(cyl_between(f"{prefix}_rib{k}", apex - d * 0.01, tip, 0.0035, 0.003, M["bamboo"], 6))
        mid = apex.lerp(tip, 0.55) - d * 0.004
        out.append(cyl_between(f"{prefix}_stretcher{k}", runner, mid, 0.0025, 0.0025, M["bamboo"], 5))
    out += [
        torus(f"{prefix}_rim", rim_c, R, 0.006, M["red"], rot=rot, seg=gores * 4, mseg=6),
        cyl_between(f"{prefix}_shaft", base - d * 0.1, apex + d * 0.03, 0.009, 0.008, M["bamboo"], 10),
        cyl_between(f"{prefix}_runner", runner - d * 0.02, runner + d * 0.02, 0.016, 0.016, M["dark"], 12),
        cyl_between(f"{prefix}_handle", base - d * 0.1, base + d * 0.06, 0.013, 0.013, M["dark"], 12),
        ellipsoid(f"{prefix}_finial", apex + d * 0.04, (0.016, 0.016, 0.016), M["red"], 12, 8),
    ]
    out.append(strand(f"{prefix}_tassel", [(*(base - d * 0.1), 0.004), (*(base - d * 0.1 + Vector((0.0, 0.01, -0.06))), 0.008),
                                         (*(base - d * 0.1 + Vector((0.005, 0.015, -0.13))), 0.0)], M["red"]))
    return out


def recipe_qinglian():
    H = 1.7
    J = mirror_joints({
        "hips": (0, 0, 0.92), "spine": (0, 0, 1.05), "chest": (0, 0, 1.2),
        "neck": (0, 0, 1.36), "head": (0, 0, 1.4), "head_top": (0, 0, 1.66),
        "shoulder.L": (0.15, 0, 1.32), "elbow.L": (0.31, 0.01, 1.1),
        "wrist.L": (0.42, -0.02, 0.89), "hand_end.L": (0.45, -0.035, 0.82),
        "hip.L": (0.085, 0, 0.88), "knee.L": (0.09, -0.012, 0.49),
        "ankle.L": (0.095, 0.012, 0.085), "toe.L": (0.095, -0.11, 0.03),
    })
    R = {"hips": (0.12, 0.095), "spine": (0.095, 0.075), "chest": (0.12, 0.09), "neck": 0.038,
         "shoulder": 0.042, "elbow": 0.034, "wrist": 0.028, "hip": 0.075, "knee": 0.05,
         "ankle": 0.036, "toe": 0.03}
    M = dict(
        skin=make_mat("skin", "#F1DDCB", 0.6, noise=0.02, height=H),
        white=make_mat("white", "#F4F1EA", 0.75, noise=0.04, noise_scale=8, height=H),
        grey=make_mat("grey", "#DAD5CC", 0.75, noise=0.05, noise_scale=8, height=H),
        wash=make_mat("wash", "#9C978F", 0.7, noise=0.05, height=H),
        dark=make_mat("dark", "#2E2D2F", 0.6, noise=0.04, height=H),
        ink=make_mat("ink", "#141416", 0.5, noise=0.03, height=H),
        red=make_mat("red", "#B8322A", 0.5, noise=0.03, height=H),
        jade=make_mat("jade", "#7FB59A", 0.25, noise=0.03, height=H),
        lip=make_mat("lip", "#B0403E", 0.45, noise=0.0, height=H),
        paper=make_mat("paper", "#EFE6D2", 0.8, noise=0.1, noise_scale=30, height=H),
        paper_b=make_mat("paper_b", "#C9BFAA", 0.8, noise=0.1, noise_scale=30, height=H),
        bamboo=make_mat("bamboo", "#8C7448", 0.6, noise=0.06, height=H),
        lotus_in=make_mat("lotus_in", "#C83A4A", 0.5, noise=0.04, height=H),
        lotus_out=make_mat("lotus_out", "#DE5A6C", 0.5, noise=0.05, height=H),
        pod=make_mat("pod", "#C9B458", 0.6, noise=0.05, height=H),
    )
    parts = [(build_body(J, R, M["white"]), None)]
    hc, hr = Vector((0, -0.005, 1.485)), (0.085, 0.095, 0.112)
    parts.append((anime_head(hc, hr, M["skin"]), "head"))
    # --- face: almond eyes with lid strokes and a flick of lashes, gentle brows, red lips, lotus forehead mark
    for sx, side in ((-1, "R"), (1, "L")):
        x, dz = 0.036 * sx, -0.008
        c = Vector((x, face_y(hc, hr, x, dz) + 0.001, hc.z + dz))
        parts.append((tag_blink(ellipsoid(f"eye.{side}", c, (0.018, 0.003, 0.0085), M["ink"], 16, 8, rot=(0, -0.12 * sx, 0.12 * sx)),
                                side, hc.z + dz), "head"))
        lid = []
        for i in range(6):
            u = -1 + 2 * i / 5
            px = x + u * 0.024 * sx
            pz = dz + 0.0095 * (1 - u * u) + 0.004 * max(u, 0)
            lid.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, 0.0032 if abs(u) < 0.8 else 0.0012))
        parts.append((tag_blink(strand(f"lid.{side}", lid, M["ink"]), side, hc.z + dz), "head"))
        lx = x + 0.024 * sx
        parts.append((tag_blink(strand(f"lash.{side}", [(lx, face_y(hc, hr, lx, dz + 0.006) - 0.002, hc.z + dz + 0.006, 0.0022),
                                                        (lx + 0.009 * sx, face_y(hc, hr, lx + 0.009 * sx, dz + 0.012) - 0.003,
                                                         hc.z + dz + 0.012, 0.0)], M["ink"]), side, hc.z + dz), "head"))
        brow = []
        for i in range(5):
            u = -1 + 2 * i / 4
            px = x + u * 0.026 * sx
            pz = dz + 0.03 + 0.006 * (1 - u * u) + 0.003 * u
            brow.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, 0.0025 if u < 0.5 else 0.001))
        parts.append((strand(f"brow.{side}", brow, M["ink"]), "head"))
        parts.append((ellipsoid(f"ear.{side}", hc + Vector((0.083 * sx, 0.01, -0.012)), (0.01, 0.016, 0.024), M["skin"], 10, 8), "head"))
        parts.append((ellipsoid(f"earring.{side}", hc + Vector((0.088 * sx, 0.006, -0.05)), (0.007, 0.007, 0.011), M["jade"], 10, 8), "head"))
    parts.append((ellipsoid("nose", Vector((0, face_y(hc, hr, 0, -0.035) - 0.003, hc.z - 0.035)), (0.007, 0.009, 0.02), M["skin"], 10, 8,
                            rot=(0.25, 0, 0)), "head"))
    mz = -0.066
    parts.append((ellipsoid("lips", Vector((0, face_y(hc, hr, 0, mz) - 0.001, hc.z + mz)), (0.012, 0.004, 0.0045), M["lip"], 14, 8), "head"))
    fz = 0.058
    for k, (ox, oz, rz) in enumerate(((0, 0.004, 0), (-0.005, -0.002, 0.6), (0.005, -0.002, -0.6))):
        parts.append((ellipsoid(f"huadian{k}", Vector((ox, face_y(hc, hr, ox, fz + oz) - 0.0005, hc.z + fz + oz)), (0.0025, 0.0015, 0.0065),
                                M["red"], 8, 6, rot=(0, rz, 0)), "head"))

    # --- hair: centre part, long side locks, high bun with jade pin, lotus hairpin + dangling beads, long back hair
    parts.append((hair_cap(hc, hr, M["ink"], face_open=0.06), "head"))
    top = hc.z + hr[2]
    for sx in (-1, 1):
        for k in range(4):
            x0 = 0.008 * sx + 0.02 * k * sx
            parts.append((strand(f"part{sx}{k}", [(x0 * 0.4, -0.05, top + 0.004, 0.018), (x0 * 1.7 + 0.01 * sx, -hr[1] * 1.02, hc.z + 0.075, 0.016),
                                                  (x0 * 2.5 + 0.03 * sx, -hr[1] * 0.8, hc.z + 0.02, 0.0)], M["ink"]), "head"))
        parts.append((strand(f"lock{sx}", [(0.065 * sx, -0.065, hc.z + 0.06, 0.014), (0.088 * sx, -0.075, hc.z - 0.04, 0.012),
                                           (0.09 * sx, -0.07, hc.z - 0.16, 0.009), (0.1 * sx, -0.06, hc.z - 0.3, 0.0)], M["ink"]), "head"))
    bun = hc + Vector((0, 0.035, hr[2] + 0.03))
    parts += [
        (ellipsoid("bun", bun + Vector((0, 0, 0.012)), (0.045, 0.042, 0.058), M["ink"], 24, 14, rot=(-0.2, 0, 0)), "head"),
        (torus("bun_coil", bun + Vector((0, 0, -0.015)), 0.05, 0.016, M["ink"], rot=(0.25, 0, 0)), "head"),
        (torus("bun_coil2", bun + Vector((0, -0.004, 0.03)), 0.036, 0.012, M["ink"], rot=(0.15, 0, 0)), "head"),
        (cyl_between("hairpin", bun + Vector((-0.1, 0.01, 0.0)), bun + Vector((0.1, 0.0, 0.03)), 0.0045, 0.0035, M["jade"], 8), "head"),
        (ellipsoid("hairpin_bead", bun + Vector((-0.105, 0.01, -0.002)), (0.01, 0.01, 0.01), M["jade"], 10, 8), "head"),
    ]
    pin = bun + Vector((0.07, -0.02, -0.03))
    parts += [(o, "head") for o in lotus("hair_lotus", pin, (0.6, -0.4, 0.7), M, scale=0.7)]
    for k in range(3):
        p0 = pin + Vector((0.01 + 0.008 * k, 0.0, -0.01))
        p1 = p0 + Vector((0.01, -0.005, -0.06 - 0.025 * k))
        parts.append((strand(f"buyao{k}", [(*p0, 0.0015), (*p1, 0.0015)], M["red"]), "head"))
        parts.append((ellipsoid(f"buyao_bead{k}", p1, (0.005, 0.005, 0.006), M["jade"] if k % 2 else M["red"], 8, 6), "head"))
    back = [(0.0, 0.08, bun.z - 0.03, 0.05), (0.0, 0.12, hc.z - 0.04, 0.06), (0.0, 0.13, hc.z - 0.25, 0.055),
            (0.01, 0.12, hc.z - 0.48, 0.04), (0.02, 0.11, hc.z - 0.62, 0.0)]
    hair_ch = [bc.spring("hairC", back[1:], "head")]
    for sx in (-1, 1):
        hp = [(0.04 * sx, 0.07, hc.z + 0.02, 0.03), (0.06 * sx, 0.11, hc.z - 0.15, 0.035),
              (0.065 * sx, 0.1, hc.z - 0.4, 0.02), (0.06 * sx, 0.09, hc.z - 0.55, 0.0)]
        hair_ch.append(bc.spring(f"hair{'LR'[sx > 0]}", hp[1:], "head"))
    hair_mark = "spring:" + ",".join(h[len("spring:"):] for h in hair_ch)
    parts.append((strand("back_hair", back, M["ink"], res=3), hair_mark))
    for sx in (-1, 1):
        parts.append((strand(f"back_hair{sx}", [(0.04 * sx, 0.07, hc.z + 0.02, 0.03), (0.06 * sx, 0.11, hc.z - 0.15, 0.035),
                                                (0.065 * sx, 0.1, hc.z - 0.4, 0.02), (0.06 * sx, 0.09, hc.z - 0.55, 0.0)], M["ink"]), hair_mark))

    # --- ruqun: white cross-collar top, chest-high layered skirt, red sash with long tails
    parts += [
        (ellipsoid("top", (0, -0.002, 1.2), (0.13, 0.093, 0.15), M["white"], 32, 20), "chest"),
        (cyl_between("collar_inner", (0, 0, 1.3), (0, 0.004, 1.385), 0.05, 0.045, M["white"], 24, cap=False), "neck"),
    ]
    # cross collar, left over right: the under lapel stops at the centre, the over lapel runs on to the side
    parts.append((ribbon("collar_under", [(-0.05, -0.05, 1.37), (-0.015, -0.09, 1.3), (0.01, -0.1, 1.24)],
                         [0.026, 0.026, 0.022], (0, -1, 0.2), M["wash"], thickness=0.004), "chest"))
    parts.append((ribbon("collar_over", [(0.05, -0.052, 1.37), (0.0, -0.097, 1.28), (-0.06, -0.098, 1.215)],
                         [0.028, 0.028, 0.024], (0, -1, 0.2), M["wash"], thickness=0.004), "chest"))
    skirt = bc.radial_springs("skirt", 0.95, 0.05, 0.17, 0.33, n=12, segs=4, parent="hips", yscale=0.85)
    parts.append((robe_cone("skirt_inner", 1.2, 0.03, 0.125, 0.33, M["grey"], M["wash"], folds=11, amp=0.012), skirt))
    parts.append((robe_cone("skirt_outer", 1.21, 0.3, 0.13, 0.3, M["white"], M["wash"], slit=(0.07, -1), folds=9, amp=0.014), skirt))
    parts += [
        (torus("sash", (0, 0, 1.19), 0.128, 0.02, M["red"], scale=(1, 0.8, 1.2)), "chest"),
        (ellipsoid("sash_knot", (0.0, -0.11, 1.19), (0.022, 0.014, 0.02), M["red"], 12, 8), "chest"),
    ]
    for sx in (-1, 1):
        parts.append((ellipsoid(f"sash_loop{sx}", (0.035 * sx, -0.112, 1.2), (0.03, 0.01, 0.018), M["red"], 12, 8, rot=(0, 0.4 * sx, 0)),
                      "chest"))
        p0 = Vector((0.012 * sx, -0.122, 1.18))  # tails ride on the outer skirt's surface
        tp = [p0, p0 + Vector((0.02 * sx, -0.055, -0.25)), p0 + Vector((0.035 * sx, -0.1, -0.55)), p0 + Vector((0.03 * sx, -0.13, -0.75))]
        parts.append((ribbon(f"sash_tail{sx}", tp, [0.022, 0.022, 0.02, 0.018], (0, -1, 0), M["red"], thickness=0.003),
                      bc.spring(f"clothSash{'LR'[sx > 0]}", tp, "hips")))
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        parts += [
            (ellipsoid(f"shoulder_robe.{s}", sh + Vector((0, 0, -0.012)), (0.044, 0.048, 0.032), M["white"], 18, 12), f"upper_arm.{s}"),
            (wide_sleeve(f"sleeve_up.{s}", sh, el, M["white"], M["wash"], r1=0.05, r2=0.075, droop=0.03), f"upper_arm.{s}"),
            (wide_sleeve(f"sleeve.{s}", el, wr, M["white"], M["wash"], r1=0.07, r2=0.19, droop=0.22), f"forearm.{s}"),
            (cyl_between(f"cuff_inner.{s}", el.lerp(wr, 0.6), wr, 0.034, 0.03, M["grey"], 16), f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.026, 0.022, 0.04), M["skin"], 14, 10), f"hand.{s}"),
            (rounded_box(f"shoe.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.045, -0.05)), (0.035, 0.09, 0.03), M["dark"], 0.024, 3),
             f"foot.{s}"),
            (ellipsoid(f"shoe_tip.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.13, -0.045)), (0.014, 0.014, 0.012), M["red"], 10, 6),
             f"foot.{s}"),
        ]
    # --- pibo (披帛): long scarf draped behind the back, ends hanging from the elbows
    parts.append((ribbon("pibo_back", [(0.3, 0.03, 1.1), (0.2, 0.13, 1.16), (0.0, 0.16, 1.1), (-0.2, 0.13, 1.16), (-0.3, 0.03, 1.1)],
                         [0.05, 0.06, 0.065, 0.06, 0.05], (0, 1, 0.3), M["grey"], thickness=0.003, rim=M["wash"]), "chest"))
    for s, sx in (("L", 1), ("R", -1)):
        el = Vector(J[f"elbow.{s}"])
        pts = [el + Vector((0.0, 0.03, 0.0)), el + Vector((0.07 * sx, 0.06, -0.25)), el + Vector((0.1 * sx, 0.1, -0.55)),
               el + Vector((0.13 * sx, 0.16, -0.85))]
        parts.append((ribbon(f"pibo_end.{s}", pts, [0.05, 0.055, 0.055, 0.05], (sx, 0.4, 0), M["grey"], thickness=0.003, rim=M["wash"]),
                      bc.spring(f"clothPibo{s}", pts, f"forearm.{s}")))
    # --- oil-paper umbrella over the right shoulder, red lotus in the left hand
    hb = Vector(J["hand_end.R"]) + Vector((0.0, -0.01, 0.03))
    parts += [(o, "hand.R") for o in umbrella("umbrella", hb, (0.12, 0.32, 1.0), M)]
    lh = Vector(J["hand_end.L"]) + Vector((0.0, -0.02, 0.02))
    top_l = lh + Vector((0.01, -0.09, 0.13))
    parts.append((cyl_between("lotus_stem", lh + Vector((0, 0.01, -0.03)), top_l, 0.004, 0.004, M["jade"], 8), "hand.L"))
    parts += [(o, "hand.L") for o in lotus("lotus", top_l, (0.1, -0.5, 1.0), M, scale=1.0)]
    return J, R, M, parts, H, {"Idle": idle_keys, "Wave": lambda arm: bc.wave_keys(arm, side="L"), "Dance": qinglian_dance_keys}


@bc.hit(21)  # open sleeve sweeps the front a quarter into the turn
def qinglian_dance_keys(arm):
    """A slow full turn with the sleeves opened out, umbrella lifted."""
    P = arm.pose.bones
    seq = [(1, 0, 0), (12, 1, 0), (24, 1, 120), (36, 1, 240), (48, 1, 360), (60, 0, 360)]
    for f, k, spin in seq:
        key_rot(P["hips"], f, y=spin)
        key_rot(P["upper_arm.L"], f, z=-55 * k, x=-15 * k)
        key_rot(P["forearm.L"], f, z=-25 * k)
        key_rot(P["upper_arm.R"], f, x=-12 * k)  # keep the umbrella upright over the head while turning
        key_rot(P["forearm.R"], f, x=-28 * k)
        key_rot(P["chest"], f, z=6 * k, x=-5 * k)
        key_rot(P["head"], f, z=10 * k, x=-6 * k)


bc.RECIPES.update(mobai=recipe_mobai, qinglian=recipe_qinglian)

if __name__ == "__main__":
    bc.main()
