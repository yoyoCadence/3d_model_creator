"""Chibi designer-toy style (Q版潮玩公仔風) - original character 「布丁」 Pudding, a dessert magical girl.

2.5-head proportions, glossy vinyl finish (clearcoat), layered eyes (white / limbal ring / gradient iris /
pupil / three highlights / thick upper lid + lashes), twin buns with bows and twin-tails, three-layer
scalloped skirt with lace, striped stockings, Mary-Jane shoes, candy-cane staff topped with a macaron and a
seeded strawberry. Blink morph target + Idle / Twirl clips.

Usage: blender -b --factory-startup -P blender/build_chibi.py -- --char pudding --out assets/models/chibi/pudding.glb
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
from build_anime import face_y, ribbon, strand  # noqa: E402
from build_character import (build_body, cyl_between, ellipsoid, idle_keys, key_rot, make_mat,  # noqa: E402
                             mirror_joints, rounded_box, set_mat, shade, solidify, subsurf, tag_blink, torus)

bc.STYLE.update(gradient=(0.9, 1.05), ao_in_albedo=0.3, normal_map=False, coat=0.3)


# ----------------------------------------------------------------------------------------
# pattern materials (baked into the albedo like everything else)
# ----------------------------------------------------------------------------------------

def _swap_color(m, new_socket):
    bc.CHANNELS[m.name]["color"] = new_socket
    m.node_tree.links.new(new_socket, m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])


def stripe_mat(name, c1, c2, scale, direction="Z", rough=0.5, height=1.0):
    m = make_mat(name, c1, rough, noise=0.02, height=height)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.bands_direction = direction
    w.wave_profile = "SIN"
    w.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*bc.hex_rgb(c1), 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*bc.hex_rgb(c2), 1)
    nt.links.new(w.outputs["Fac"], ramp.inputs["Fac"])
    _swap_color(m, ramp.outputs["Color"])
    return m


def vgrad_mat(name, top, bottom, z0, z1, rough=0.25, emit=0.0):
    """Vertical gradient (used for the iris: dark top -> light bottom, a classic toy/anime eye)."""
    m = make_mat(name, top, rough, noise=0.0, emit_strength=emit)
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*bc.hex_rgb(bottom), 1)
    mix.inputs[7].default_value = (*bc.hex_rgb(top), 1)
    nt.links.new(mr.outputs["Result"], mix.inputs[0])
    _swap_color(m, mix.outputs[2])
    return m


def scallop_cone(name, z_top, z_bot, r_top, r_bot, waves, amp, mat, rim=None, open_front=False, seg=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r_bot, radius2=r_top, depth=z_top - z_bot)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, (z_top + z_bot) / 2))
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-4], cuts=4)
    if open_front:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < -0.6 * r_bot], context="FACES")
    for v in bm.verts:
        k = (z_top - v.co.z) / (z_top - z_bot)
        a = math.atan2(v.co.y, v.co.x)
        v.co.z += amp * math.cos(a * waves) * k ** 3  # scalloped hem
        r = 1 + 0.035 * math.sin(a * waves) * k  # soft pleats
        v.co.x *= r
        v.co.y *= r * 0.9
    obj = bc.mesh_from_bmesh(name, bm)
    set_mat(obj, mat, [rim] if rim else [])
    solidify(obj, 0.006, rim_mat_offset=1 if rim else None)
    subsurf(obj, 1)
    bc.apply_modifiers(obj)
    shade(obj, True, 180)
    return obj


def bow(prefix, c, size, mat, knot_mat, facing=(0, -1, 0), tails=0.0, tail_mat=None):
    """Two loops + knot (+ optional tails). `facing` = direction the bow's front points to."""
    f = Vector(facing).normalized()
    side = f.cross(Vector((0, 0, 1))).normalized()
    out = []
    for sx in (-1, 1):
        out.append(ellipsoid(f"{prefix}_loop{sx}", c + side * (size * 0.95 * sx), (size * 0.9, size * 0.38, size * 0.6),
                             mat, 18, 10, rot=(0, 0.35 * sx, math.atan2(side.y, side.x))))
    out.append(ellipsoid(f"{prefix}_knot", c + f * size * 0.15, (size * 0.32, size * 0.3, size * 0.34), knot_mat, 12, 8))
    if tails:
        for sx in (-1, 1):
            p0 = c + side * size * 0.25 * sx
            out.append(ribbon(f"{prefix}_tail{sx}", [p0, p0 + side * size * 0.4 * sx + Vector((0, 0, -tails * 0.5)),
                                                    p0 + side * size * 0.7 * sx + Vector((0, 0, -tails))],
                              [size * 0.5, size * 0.45, size * 0.4], f, tail_mat or mat))
    return out


def chibi_head_face(M, hc, hr, ez, lashes=True, brow_arch=0.013, brow_r=0.003, brow_dz=0.108, brow_len=0.024,
                    brow_tilt=0.0, mouth=(0.019, 0.004, 0.0085), tongue=True, blush=(0.03, 0.003, 0.015)):
    """Round chibi head + layered eyes (white, limbal ring, gradient iris, pupil, three glints, lid, lashes),
    brows, blush, mouth. Defaults are Pudding's face; Cocoa uses a boy variant (no lashes, straighter brows)."""
    parts = []
    head = bc.tag_face(ellipsoid("head", hc, hr, M["skin"], 40, 28))
    for v in head.data.vertices:
        dz = (hc.z - v.co.z) / hr[2]
        if dz > 0:
            v.co.x = hc.x + (v.co.x - hc.x) * (1 + 0.06 * math.sin(math.pi * min(dz, 1.0)) - 0.16 * dz ** 3)
            v.co.y = hc.y + (v.co.y - hc.y) * (1 - 0.08 * dz ** 3)
    parts.append((head, "head"))
    for sx, side in ((-1, "R"), (1, "L")):
        x = 0.072 * sx
        y = face_y(hc, hr, x, ez - hc.z) + 0.002
        rot = (0, 0, 0.3 * sx)
        c = Vector((x, y, ez))
        layer = [
            ("white", (0.047, 0.006, 0.057), 0.0, (0, 0), "eye_white"),
            ("ring", (0.04, 0.0055, 0.05), -0.0035, (-0.004 * sx, -0.003), "iris_ring"),
            ("iris", (0.0355, 0.005, 0.0455), -0.0045, (-0.004 * sx, -0.003), "iris"),
            ("pupil", (0.0155, 0.004, 0.022), -0.0062, (-0.004 * sx, -0.002), "pupil"),
            ("glintA", (0.0135, 0.002, 0.0175), -0.0078, (0.009 * sx, 0.017), "glint"),
            ("glintB", (0.0065, 0.002, 0.0065), -0.0078, (-0.014 * sx, -0.02), "glint"),
            ("glintC", (0.0035, 0.002, 0.0035), -0.0078, (0.012 * sx, -0.012), "glint"),
        ]
        for nm, size, dy, (ox, oz), mat in layer:
            o = ellipsoid(f"{nm}.{side}", c + Vector((ox, dy, oz)), size, M[mat], 20, 10, rot=rot)
            parts.append((tag_blink(o, side, ez), "head"))
        lid = []
        for i in range(8):
            u = -1 + 2 * i / 7
            px = x + u * 0.05 * sx
            pz = (ez - hc.z) + 0.058 * (1 - 0.6 * u * u) + (0.003 if u > 0.8 else 0) + 0.012 * max(-u, 0) ** 1.5
            lid.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, 0.0065 if abs(u) < 0.75 else 0.0035))
        parts.append((tag_blink(strand(f"lid.{side}", lid, M["liner"]), side, ez), "head"))
        if lashes:
            for k in range(2):  # outer lashes
                bx, bz = x + 0.048 * sx, ez + 0.03 - k * 0.016
                parts.append((tag_blink(strand(f"lash{k}.{side}", [
                    (bx, face_y(hc, hr, bx, bz - hc.z) - 0.002, bz, 0.004),
                    (bx + 0.014 * sx, face_y(hc, hr, bx + 0.014 * sx, bz - hc.z) + 0.002, bz + 0.012 - k * 0.004, 0.0)],
                    M["liner"]), side, ez), "head"))
            low = []
            for i in range(4):
                u = 0.2 + 0.8 * i / 3
                px = x + u * 0.042 * sx
                pz = (ez - hc.z) - 0.05 + 0.012 * u
                low.append((px, face_y(hc, hr, px, pz) - 0.001, hc.z + pz, 0.0025 if u < 0.9 else 0.001))
            parts.append((tag_blink(strand(f"lowlash.{side}", low, M["liner"]), side, ez), "head"))
        brow = []
        for i in range(4):
            u = -1 + 2 * i / 3
            px = x + u * brow_len * sx
            pz = (ez - hc.z) + brow_dz + brow_arch * (1 - u * u) + brow_tilt * u
            brow.append((px, face_y(hc, hr, px, pz) - 0.002, hc.z + pz, brow_r if abs(u) < 0.9 else brow_r * 0.4))
        parts.append((strand(f"brow.{side}", brow, M["hair"]), "head"))
        if blush:
            bx, bz = 0.118 * sx, ez - 0.055
            parts.append((ellipsoid(f"blush.{side}", Vector((bx, face_y(hc, hr, bx, bz - hc.z) + 0.001, bz)), blush,
                                    M["blush"], 16, 8, rot=(0, 0, 0.5 * sx)), "head"))
    mz = ez - 0.09
    parts += [
        (ellipsoid("mouth", Vector((0, face_y(hc, hr, 0, mz - hc.z) + 0.002, mz)), mouth, M["mouth"], 16, 8), "head"),
        (ellipsoid("nose", Vector((0, face_y(hc, hr, 0, ez - 0.05 - hc.z) - 0.002, ez - 0.05)), (0.006, 0.005, 0.005), M["skin"], 8, 6), "head"),
    ]
    if tongue:
        parts.append((ellipsoid("tongue", Vector((0, face_y(hc, hr, 0, mz - hc.z) - 0.001, mz - 0.004)), (0.009, 0.003, 0.005),
                                M["tongue"], 12, 6), "head"))
    return parts


# ----------------------------------------------------------------------------------------
# 布丁 Pudding
# ----------------------------------------------------------------------------------------

def recipe_pudding():
    H = 1.02
    J = mirror_joints({
        "hips": (0, 0, 0.31), "spine": (0, 0, 0.38), "chest": (0, 0, 0.455),
        "neck": (0, 0, 0.525), "head": (0, 0, 0.555), "head_top": (0, 0, 0.95),
        "shoulder.L": (0.075, 0, 0.495), "elbow.L": (0.15, 0.0, 0.43),
        "wrist.L": (0.2, -0.01, 0.35), "hand_end.L": (0.215, -0.015, 0.315),
        "hip.L": (0.05, 0, 0.29), "knee.L": (0.055, -0.005, 0.17),
        "ankle.L": (0.058, 0.005, 0.055), "toe.L": (0.058, -0.05, 0.02),
    })
    R = {"hips": (0.08, 0.066), "spine": (0.07, 0.058), "chest": (0.075, 0.062), "neck": 0.034,
         "shoulder": 0.033, "elbow": 0.029, "wrist": 0.025, "hip": 0.041, "knee": 0.033,
         "ankle": 0.03, "toe": 0.027}
    hc, hr = Vector((0, 0, 0.745)), (0.205, 0.19, 0.19)
    ez = hc.z - 0.03
    M = dict(
        skin=make_mat("skin", "#FFD8C4", 0.45, noise=0.02, height=H),
        hair=make_mat("hair", "#F497B8", 0.3, noise=0.04, noise_scale=3, height=H),
        hair_tip=make_mat("hair_tip", "#FFD3E3", 0.3, noise=0.03, height=H),
        eye_white=make_mat("eye_white", "#FFFFFF", 0.2, noise=0.0, height=H),
        iris=vgrad_mat("iris", "#4B2C7E", "#D9A6F2", ez - 0.04, ez + 0.04, emit=0.15),
        iris_ring=make_mat("iris_ring", "#35205A", 0.25, noise=0.0, height=H),
        pupil=make_mat("pupil", "#221233", 0.2, noise=0.0, height=H),
        glint=make_mat("glint", "#FFFFFF", 0.1, noise=0.0, emit_strength=1.2, height=H),
        liner=make_mat("liner", "#4A2638", 0.4, noise=0.0, height=H),
        mouth=make_mat("mouth", "#B93E52", 0.4, noise=0.0, height=H),
        tongue=make_mat("tongue", "#FF8EA2", 0.4, noise=0.0, height=H),
        blush=make_mat("blush", "#FF9DB4", 0.6, noise=0.0, height=H),
        cream=make_mat("cream", "#FFF3E3", 0.55, noise=0.03, height=H),
        pink=make_mat("pink", "#F6A3C2", 0.5, noise=0.03, height=H),
        mint=make_mat("mint", "#9EE3CF", 0.45, noise=0.03, height=H),
        red=make_mat("red", "#E5485A", 0.35, noise=0.03, height=H),
        lace=make_mat("lace", "#FFFFFF", 0.6, noise=0.02, height=H),
        stockings=stripe_mat("stockings", "#FFFFFF", "#F6A3C2", 55.0, "Z", 0.55, H),
        candy=stripe_mat("candy", "#FFFFFF", "#E5485A", 18.0, "DIAGONAL", 0.25, H),
        shoe=make_mat("shoe", "#D94052", 0.25, noise=0.02, height=H),
        macaron=make_mat("macaron", "#F7A0C0", 0.6, noise=0.06, noise_scale=40, height=H),
        filling=make_mat("filling", "#FFF8EE", 0.5, noise=0.02, height=H),
        berry=make_mat("berry", "#E3354A", 0.25, noise=0.05, height=H),
        leaf=make_mat("leaf", "#5DBE6C", 0.5, noise=0.04, height=H),
        seed=make_mat("seed", "#FFE07A", 0.4, noise=0.0, height=H),
    )
    parts = [(build_body(J, R, M["skin"]), None)]

    parts += chibi_head_face(M, hc, hr, ez)

    # --- hair: cap, thick bangs, side locks with curls, back, buns with wraps, twin-tails, bows, ahoge
    cap = ellipsoid("hair_cap", hc + Vector((0, 0.012, 0.022)), (hr[0] * 1.08, hr[1] * 1.08, hr[2] * 1.06), M["hair"], 40, 24)
    bm = bmesh.new(); bm.from_mesh(cap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co.y < -0.03 and v.co.z < hc.z + 0.065) or v.co.z < hc.z - 0.12],
                     context="VERTS")
    bm.to_mesh(cap.data); bm.free()
    solidify(cap, 0.01); bc.apply_modifiers(cap); shade(cap, True, 180)
    parts.append((cap, "head"))
    top = hc.z + hr[2]
    for i in range(6):
        x0 = -0.13 + i * 0.052
        sway = 0.012 * (1 if i % 2 else -1)
        parts.append((strand(f"bang{i}", [
            (x0 * 0.45, -0.06, top + 0.005, 0.042), (x0 * 1.05, -hr[1] * 1.07, hc.z + 0.105, 0.04),
            (x0 * 1.1 + sway, -hr[1] * 1.04, hc.z + 0.045, 0.024), (x0 * 1.12 + sway * 1.6, -hr[1] * 0.98, hc.z + 0.012, 0.0)],
            M["hair"]), "head"))
    for sx in (-1, 1):
        parts.append((strand(f"sidelock{sx}", [
            (0.15 * sx, -0.07, hc.z + 0.07, 0.04), (0.2 * sx, -0.08, hc.z - 0.04, 0.038),
            (0.205 * sx, -0.085, hc.z - 0.14, 0.03), (0.18 * sx, -0.1, hc.z - 0.19, 0.016), (0.155 * sx, -0.095, hc.z - 0.175, 0.0)],
            M["hair"]), "head"))
        bun = hc + Vector((0.16 * sx, 0.05, 0.15))
        parts += [
            (ellipsoid(f"bun{sx}", bun, (0.078, 0.075, 0.074), M["hair"], 28, 18), "head"),
            (torus(f"bun_wrap{sx}", bun + Vector((0, 0, -0.01)), 0.062, 0.016, M["hair_tip"], rot=(0.35, 0.3 * sx, 0)), "head"),
        ]
        parts += [(o, "head") for o in bow(f"bunbow{sx}", bun + Vector((0.035 * sx, -0.055, 0.045)), 0.032, M["mint"], M["red"],
                                           facing=(0.4 * sx, -1, 0.3))]
        tail = [(bun.x + 0.05 * sx, bun.y + 0.02, bun.z - 0.02, 0.05), (0.29 * sx, 0.09, hc.z + 0.03, 0.052),
                (0.31 * sx, 0.07, hc.z - 0.13, 0.044), (0.27 * sx, 0.04, hc.z - 0.25, 0.03), (0.22 * sx, 0.02, hc.z - 0.29, 0.0)]
        tt = bc.spring(f"hairTwin{'LR'[sx > 0]}", tail[1:], "head")
        parts.append((strand(f"twintail{sx}", tail, M["hair"], res=3), tt))
        parts.append((strand(f"twintail_tip{sx}", [tail[3][:3] + (0.03,), (0.245 * sx, 0.03, hc.z - 0.285, 0.016),
                                                   tail[4][:3] + (0.0,)], M["hair_tip"]), tt))
    for k in range(7):
        a = math.radians(25 + k * 21.7)
        ca, sa = math.cos(a), math.sin(a)
        parts.append((strand(f"back{k}", [
            (0.55 * hr[0] * ca, 0.55 * hr[1] * sa, top - 0.01, 0.05), (1.1 * hr[0] * ca, 1.12 * hr[1] * sa, hc.z + 0.0, 0.05),
            (1.12 * hr[0] * ca, 1.12 * hr[1] * sa, hc.z - 0.11, 0.0)], M["hair"]), "head"))
    parts.append((strand("ahoge", [(0, -0.02, top + 0.01, 0.018), (0.0, -0.05, top + 0.08, 0.014),
                                   (0.035, 0.0, top + 0.11, 0.008), (0.05, 0.03, top + 0.08, 0.0)], M["hair"]), "head"))

    # --- outfit
    parts += [
        (ellipsoid("bodice", (0, -0.002, 0.45), (0.088, 0.071, 0.085), M["cream"], 28, 18), "chest"),
        (torus("waistband", (0, 0, 0.405), 0.083, 0.014, M["pink"], scale=(1, 0.85, 1)), "spine"),
    ]
    parts.append((cyl_between("neck", (0, 0, 0.49), (0, 0, 0.6), 0.033, 0.035, M["skin"], 20), "neck"))
    collar = cyl_between("collar", (0, 0, 0.495), (0, 0, 0.528), 0.125, 0.042, M["mint"], 40, cap=False)
    collar.data.materials.append(M["lace"])
    solidify(collar, 0.006, rim_mat_offset=1); bc.apply_modifiers(collar); shade(collar, True, 180)
    parts.append((collar, "chest"))
    for k in range(28):  # lace scallops on the collar edge
        a = 2 * math.pi * k / 28
        parts.append((ellipsoid(f"lace_c{k}", (0.127 * math.cos(a), 0.127 * math.sin(a) * 0.97, 0.493), (0.013, 0.013, 0.009),
                                M["lace"], 10, 6), "chest"))
    parts += [(o, "chest") for o in bow("chestbow", Vector((0, -0.085, 0.49)), 0.038, M["red"], M["red"], tails=0.07)]
    sk = bc.radial_springs("skirt", 0.38, 0.215, 0.1, 0.19, n=10, segs=2, parent="hips")
    parts += [
        (scallop_cone("petticoat", 0.4, 0.215, 0.084, 0.19, 18, 0.012, M["lace"]), sk),
        (scallop_cone("skirt", 0.41, 0.245, 0.086, 0.178, 12, 0.016, M["pink"], rim=M["lace"]), sk),
        (scallop_cone("overskirt", 0.415, 0.31, 0.088, 0.16, 10, 0.012, M["cream"], rim=M["mint"], open_front=True), sk),
        (rounded_box("apron", (0, -0.13, 0.335), (0.055, 0.006, 0.06), M["lace"], 0.004, 2, rot=(0.3, 0, 0), taper_bottom=1.25), sk),
    ]
    for k in range(5):
        parts.append((ellipsoid(f"apron_lace{k}", (-0.06 + k * 0.03, -0.147, 0.277), (0.016, 0.006, 0.011), M["lace"], 10, 6), "hips"))
    for s, sx in (("L", 1), ("R", -1)):
        sh, el, wr = Vector(J[f"shoulder.{s}"]), Vector(J[f"elbow.{s}"]), Vector(J[f"wrist.{s}"])
        parts += [
            (ellipsoid(f"puff.{s}", sh + Vector((0.022 * sx, 0, -0.012)), (0.046, 0.045, 0.04), M["pink"], 20, 14), f"upper_arm.{s}"),
            (torus(f"puff_band.{s}", sh.lerp(el, 0.55), 0.034, 0.008, M["mint"],
                   rot=Vector((0, 0, 1)).rotation_difference(el - sh).to_euler()), f"upper_arm.{s}"),
            (torus(f"glove_cuff.{s}", wr, 0.03, 0.009, M["lace"], rot=Vector((0, 0, 1)).rotation_difference(wr - el).to_euler()), f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.03, 0.026, 0.034), M["lace"], 16, 12), f"hand.{s}"),
            (cyl_between(f"stock_thigh.{s}", Vector(J[f"hip.{s}"]) + Vector((0, 0, -0.035)), J[f"knee.{s}"], 0.044, 0.037, M["stockings"], 24), f"thigh.{s}"),
            (cyl_between(f"stock_shin.{s}", J[f"knee.{s}"], Vector(J[f"ankle.{s}"]) + Vector((0, 0, 0.01)), 0.037, 0.032, M["stockings"], 24), f"shin.{s}"),
            (rounded_box(f"shoe.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.025, -0.027)), (0.037, 0.058, 0.03), M["shoe"], 0.024, 4), f"foot.{s}"),
            (rounded_box(f"sole.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.025, -0.052)), (0.039, 0.06, 0.007), M["lace"], 0.005, 2), f"foot.{s}"),
            (torus(f"strap.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.01, -0.012)), 0.034, 0.006, M["shoe"],
                   rot=(0.4, 0, 0), scale=(1, 1.15, 1)), f"foot.{s}"),
        ]
        parts += [(o, f"foot.{s}") for o in bow(f"shoebow.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.07, -0.005)), 0.012,
                                               M["mint"], M["mint"], facing=(0, -1, 0.6))]
    # --- candy-cane staff with macaron + strawberry (right hand)
    sx_, sy_ = -0.2075, -0.0125
    parts += [
        (cyl_between("staff", (sx_, sy_, 0.06), (sx_, sy_, 0.8), 0.011, 0.013, M["candy"], 16), "hand.R"),
        (ellipsoid("staff_cap", (sx_, sy_, 0.055), (0.016, 0.016, 0.014), M["red"], 12, 8), "hand.R"),
        (ellipsoid("macaron_bottom", (sx_, sy_, 0.812), (0.07, 0.07, 0.026), M["macaron"], 32, 14), "hand.R"),
        (cyl_between("macaron_filling", (sx_, sy_, 0.824), (sx_, sy_, 0.84), 0.064, 0.064, M["filling"], 32), "hand.R"),
        (ellipsoid("macaron_top", (sx_, sy_, 0.852), (0.07, 0.07, 0.028), M["macaron"], 32, 14), "hand.R"),
        (torus("macaron_foot", (sx_, sy_, 0.832), 0.066, 0.006, M["macaron"], seg=48), "hand.R"),
    ]
    berry_c = Vector((sx_, sy_, 0.915))
    berry = ellipsoid("berry", berry_c, (0.036, 0.036, 0.045), M["berry"], 24, 16)
    for v in berry.data.vertices:  # strawberry: wide shoulders, pointed bottom
        dz = (berry_c.z - v.co.z) / 0.045
        k = 1 - 0.45 * max(dz, 0) ** 1.4
        v.co.x = berry_c.x + (v.co.x - berry_c.x) * k
        v.co.y = berry_c.y + (v.co.y - berry_c.y) * k
    parts.append((berry, "hand.R"))
    for k in range(16):
        a = 2 * math.pi * k / 16 + (k % 2) * 0.2
        z = berry_c.z + 0.025 - (k % 4) * 0.016
        r = 0.034 * (1 - 0.45 * max((berry_c.z - z) / 0.045, 0) ** 1.4)
        parts.append((ellipsoid(f"seed{k}", (berry_c.x + r * math.cos(a), berry_c.y + r * math.sin(a), z), (0.003, 0.003, 0.0045),
                                M["seed"], 6, 4), "hand.R"))
    for k in range(5):
        a = 2 * math.pi * k / 5
        parts.append((ellipsoid(f"leaf{k}", berry_c + Vector((0.022 * math.cos(a), 0.022 * math.sin(a), 0.04)), (0.022, 0.009, 0.004),
                                M["leaf"], 10, 6, rot=(0, 0.35, a)), "hand.R"))
    parts += [(o, "hand.R") for o in bow("staffbow", Vector((sx_, sy_ - 0.012, 0.78)), 0.022, M["mint"], M["red"], tails=0.05)]
    return J, R, M, parts, H, {"Idle": idle_keys, "Twirl": pudding_twirl_keys}


def pudding_twirl_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (12, -70, -20, 10), (20, -85, -30, -10), (28, -70, -20, 10), (40, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua * 0.6, z=ua * 0.4)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.3, z=-ua * 0.5)
        key_rot(P["chest"], f, z=ch)
        key_rot(P["head"], f, z=-ch, x=abs(ch) * 0.4)


# ----------------------------------------------------------------------------------------
# 可可 Cocoa - chocolate knight boy (Pudding's partner)
# ----------------------------------------------------------------------------------------

def recipe_cocoa():
    H = 1.04
    J = mirror_joints({
        "hips": (0, 0, 0.32), "spine": (0, 0, 0.39), "chest": (0, 0, 0.46),
        "neck": (0, 0, 0.53), "head": (0, 0, 0.56), "head_top": (0, 0, 0.95),
        "shoulder.L": (0.08, 0, 0.5), "elbow.L": (0.155, 0.0, 0.43),
        "wrist.L": (0.205, -0.01, 0.355), "hand_end.L": (0.22, -0.015, 0.32),
        "hip.L": (0.052, 0, 0.3), "knee.L": (0.057, -0.005, 0.175),
        "ankle.L": (0.06, 0.005, 0.055), "toe.L": (0.06, -0.05, 0.02),
    })
    R = {"hips": (0.085, 0.07), "spine": (0.076, 0.062), "chest": (0.082, 0.066), "neck": 0.036,
         "shoulder": 0.035, "elbow": 0.031, "wrist": 0.027, "hip": 0.044, "knee": 0.035,
         "ankle": 0.031, "toe": 0.028}
    hc, hr = Vector((0, 0, 0.745)), (0.2, 0.188, 0.188)
    ez = hc.z - 0.03
    M = dict(
        skin=make_mat("skin", "#FBD2BA", 0.45, noise=0.02, height=H),
        hair=make_mat("hair", "#5A3522", 0.3, noise=0.04, noise_scale=3, height=H),
        hair_tip=make_mat("hair_tip", "#8E5C3A", 0.3, noise=0.03, height=H),
        eye_white=make_mat("eye_white", "#FFFFFF", 0.2, noise=0.0, height=H),
        iris=vgrad_mat("iris", "#5E2F12", "#F0B058", ez - 0.04, ez + 0.04, emit=0.15),
        iris_ring=make_mat("iris_ring", "#3B1D0C", 0.25, noise=0.0, height=H),
        pupil=make_mat("pupil", "#2A140A", 0.2, noise=0.0, height=H),
        glint=make_mat("glint", "#FFFFFF", 0.1, noise=0.0, emit_strength=1.2, height=H),
        liner=make_mat("liner", "#3A2016", 0.4, noise=0.0, height=H),
        mouth=make_mat("mouth", "#9E3A3A", 0.4, noise=0.0, height=H),
        tongue=make_mat("tongue", "#F08A8A", 0.4, noise=0.0, height=H),
        tooth=make_mat("tooth", "#FFFFFF", 0.3, noise=0.0, height=H),
        blush=make_mat("blush", "#F7A08E", 0.6, noise=0.0, height=H),
        cream=make_mat("cream", "#FFF5E6", 0.5, noise=0.03, height=H),
        choco=make_mat("choco", "#5B341F", 0.3, noise=0.04, edge=0.15, height=H),
        choco_dark=make_mat("choco_dark", "#43261A", 0.28, noise=0.04, height=H),
        caramel=make_mat("caramel", "#D9822B", 0.4, noise=0.04, height=H),
        biscuit=make_mat("biscuit", "#DBA65C", 0.6, noise=0.1, noise_scale=30, height=H),
        cookie=make_mat("cookie", "#D59A52", 0.65, noise=0.16, noise_scale=45, height=H),
        candy=make_mat("candy", "#F27BA4", 0.25, noise=0.02, height=H),
        cherry=make_mat("cherry", "#D3203A", 0.2, noise=0.02, height=H),
        stem=make_mat("stem", "#5C7A2E", 0.5, noise=0.02, height=H),
        cocoa=make_mat("cocoa", "#7A4A2C", 0.55, noise=0.05, height=H),
        socks=stripe_mat("socks", "#FFF5E6", "#7A4A2C", 55.0, "Z", 0.55, H),
        wafer=stripe_mat("wafer", "#EBC57E", "#C9974B", 60.0, "DIAGONAL", 0.6, H),
        sprinkle_a=make_mat("sprinkle_a", "#F27BA4", 0.3, noise=0.0, height=H),
        sprinkle_b=make_mat("sprinkle_b", "#6FC7E8", 0.3, noise=0.0, height=H),
        sprinkle_c=make_mat("sprinkle_c", "#FFE07A", 0.3, noise=0.0, height=H),
    )
    parts = [(build_body(J, R, M["skin"]), None)]
    parts += chibi_head_face(M, hc, hr, ez, lashes=False, brow_arch=0.004, brow_r=0.0048, brow_dz=0.098, brow_len=0.028,
                             brow_tilt=0.007, mouth=(0.022, 0.004, 0.011), blush=(0.024, 0.003, 0.011))
    mz = ez - 0.09
    parts.append((ellipsoid("tooth", Vector((0.006, face_y(hc, hr, 0.006, mz - hc.z) - 0.0005, mz + 0.006)), (0.005, 0.002, 0.003),
                            M["tooth"], 8, 6), "head"))

    # --- hair: cap, chunky flicked bangs, side clumps, back, big cowlick
    cap = ellipsoid("hair_cap", hc + Vector((0, 0.012, 0.02)), (hr[0] * 1.08, hr[1] * 1.08, hr[2] * 1.06), M["hair"], 40, 24)
    bm = bmesh.new(); bm.from_mesh(cap.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co.y < -0.03 and v.co.z < hc.z + 0.07) or v.co.z < hc.z - (0.15 if v.co.y > 0.02 else 0.1)],
                     context="VERTS")
    bm.to_mesh(cap.data); bm.free()
    solidify(cap, 0.01); bc.apply_modifiers(cap); shade(cap, True, 180)
    parts.append((cap, "head"))
    top = hc.z + hr[2]
    for i in range(5):
        x0 = -0.12 + i * 0.06
        flick = 0.03 * (1 if x0 > 0 else -1) if abs(x0) > 0.05 else 0.0
        parts.append((strand(f"bang{i}", [
            (x0 * 0.5, -0.06, top + 0.01, 0.048), (x0 * 1.05, -hr[1] * 1.07, hc.z + 0.115, 0.044),
            (x0 * 1.12 + flick, -hr[1] * 1.04, hc.z + 0.06, 0.026), (x0 * 1.18 + flick * 1.8, -hr[1] * 0.98, hc.z + 0.045, 0.0)],
            M["hair"]), "head"))
    for sx in (-1, 1):
        parts.append((strand(f"side{sx}", [(0.16 * sx, -0.05, hc.z + 0.08, 0.045), (0.2 * sx, -0.06, hc.z - 0.02, 0.04),
                                           (0.205 * sx, -0.05, hc.z - 0.09, 0.0)], M["hair"]), "head"))
        parts.append((strand(f"side_flick{sx}", [(0.19 * sx, 0.02, hc.z + 0.02, 0.04), (0.23 * sx, 0.04, hc.z - 0.05, 0.03),
                                                 (0.25 * sx, 0.07, hc.z - 0.07, 0.0)], M["hair_tip"]), "head"))
    for k in range(9):
        a = math.radians(20 + k * 17.5)
        ca, sa = math.cos(a), math.sin(a)
        ln = 0.15 - 0.04 * abs(math.cos(a))
        parts.append((strand(f"back{k}", [
            (0.55 * hr[0] * ca, 0.55 * hr[1] * sa, top - 0.01, 0.05), (1.1 * hr[0] * ca, 1.12 * hr[1] * sa, hc.z + 0.0, 0.05),
            (1.12 * hr[0] * ca, 1.12 * hr[1] * sa, hc.z - ln * 0.7, 0.036),
            (1.05 * hr[0] * ca, 1.2 * hr[1] * sa, hc.z - ln, 0.0)], M["hair" if k % 3 else "hair_tip"]), "head"))
    parts.append((strand("cowlick", [(0.02, 0.0, top + 0.005, 0.022), (0.03, -0.03, top + 0.07, 0.018),
                                     (0.0, -0.06, top + 0.11, 0.01), (-0.035, -0.04, top + 0.12, 0.0)], M["hair"]), "head"))

    # --- wafer cap + soft-serve cream swirl + cherry
    wc = hc + Vector((0.05, 0.04, hr[2] * 0.82))
    wafer = ellipsoid("wafer_cap", wc, (0.12, 0.12, 0.07), M["wafer"], 32, 16, rot=(0.15, -0.35, 0))
    bm = bmesh.new(); bm.from_mesh(wafer.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co - wc).dot(Vector((-0.34, -0.15, 0.93))) < -0.005], context="VERTS")
    bm.to_mesh(wafer.data); bm.free()
    solidify(wafer, 0.01); bc.apply_modifiers(wafer); shade(wafer, True, 180)
    parts.append((wafer, "head"))
    up = Vector((-0.34, -0.15, 0.93)).normalized()
    for k, (r, rr) in enumerate(((0.07, 0.03), (0.052, 0.026), (0.034, 0.021), (0.018, 0.016))):
        parts.append((torus(f"swirl{k}", wc + up * (0.065 + k * 0.034), r, rr, M["cream"], rot=up.to_track_quat("Z", "Y").to_euler(),
                            seg=28, mseg=10), "head"))
    tip = wc + up * 0.2
    parts += [(ellipsoid("cherry", tip + up * 0.02, (0.022, 0.022, 0.02), M["cherry"], 16, 10), "head"),
              (strand("cherry_stem", [(*(tip + up * 0.038), 0.003), (*(tip + up * 0.065 + Vector((0.015, 0, 0))), 0.0025),
                                      (*(tip + up * 0.075 + Vector((0.03, 0.0, -0.01))), 0.0)], M["stem"]), "head")]

    # --- outfit: undershirt, chocolate-bar chest plate, pauldrons with cream drip, cape, belt, shorts, socks, boots
    parts.append((ellipsoid("tunic", (0, -0.002, 0.44), (0.092, 0.074, 0.102), M["wafer"], 28, 18), "chest"))
    parts.append((rounded_box("choco_plate", (0, -0.055, 0.455), (0.07, 0.025, 0.06), M["choco"], 0.012, 3), "chest"))
    for i in range(2):
        for j in range(3):
            parts.append((rounded_box(f"choco_sq{i}{j}", (-0.03 + i * 0.06, -0.08, 0.418 + j * 0.037), (0.025, 0.006, 0.015),
                                      M["choco_dark"], 0.005, 2), "chest"))
    parts.append((torus("collar", (0, 0, 0.515), 0.05, 0.016, M["caramel"], scale=(1, 0.92, 1)), "chest"))
    for s, sx in (("L", 1), ("R", -1)):
        sh = Vector(J[f"shoulder.{s}"])
        parts += [
            (ellipsoid(f"pauldron.{s}", sh + Vector((0.018 * sx, 0, 0.01)), (0.048, 0.048, 0.034), M["choco"], 20, 12), f"upper_arm.{s}"),
            (torus(f"drip.{s}", sh + Vector((0.018 * sx, 0, -0.002)), 0.044, 0.01, M["cream"], scale=(1, 1, 1)), f"upper_arm.{s}"),
            (cyl_between(f"sleeve.{s}", sh, sh.lerp(Vector(J[f"elbow.{s}"]), 0.6), 0.042, 0.038, M["cocoa"], 20), f"upper_arm.{s}"),
        ]
    cape = scallop_cone("cape", 0.52, 0.22, 0.085, 0.2, 9, 0.02, M["caramel"], rim=M["cream"])
    bm = bmesh.new(); bm.from_mesh(cape.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y < 0.01], context="FACES")
    bm.to_mesh(cape.data); bm.free()
    parts.append((cape, bc.radial_springs("clothCape", 0.49, 0.22, 0.1, 0.2, segs=2, parent="chest",
                                          angles=[math.radians(a) for a in (20, 60, 90, 120, 160)])))
    parts += [
        (torus("belt", (0, 0, 0.335), 0.085, 0.014, M["biscuit"], scale=(1, 0.85, 1)), "hips"),
        (ellipsoid("belt_candy", (0, -0.075, 0.335), (0.02, 0.01, 0.016), M["candy"], 14, 8), "hips"),
        (scallop_cone("shorts", 0.34, 0.24, 0.086, 0.11, 6, 0.004, M["cocoa"]), "hips"),
    ]
    for s, sx in (("L", 1), ("R", -1)):
        wr, el = Vector(J[f"wrist.{s}"]), Vector(J[f"elbow.{s}"])
        parts += [
            (torus(f"cuff.{s}", wr, 0.03, 0.009, M["caramel"], rot=Vector((0, 0, 1)).rotation_difference(wr - el).to_euler()), f"forearm.{s}"),
            (ellipsoid(f"hand.{s}", (wr + Vector(J[f"hand_end.{s}"])) / 2, (0.031, 0.027, 0.035), M["cream"], 16, 12), f"hand.{s}"),
            (cyl_between(f"sock.{s}", Vector(J[f"knee.{s}"]) + Vector((0, 0, -0.01)), Vector(J[f"ankle.{s}"]) + Vector((0, 0, 0.01)),
                         0.037, 0.033, M["socks"], 24), f"shin.{s}"),
            (rounded_box(f"boot.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.022, -0.02)), (0.04, 0.058, 0.037), M["choco"], 0.025, 4),
             f"foot.{s}"),
            (torus(f"boot_cuff.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, 0, 0.015)), 0.037, 0.011, M["cream"]), f"foot.{s}"),
            (rounded_box(f"sole.{s}", Vector(J[f"ankle.{s}"]) + Vector((0, -0.022, -0.054)), (0.042, 0.06, 0.007), M["choco_dark"], 0.005, 2),
             f"foot.{s}"),
        ]
    # --- cookie shield (left forearm) with chocolate chips
    el, wr = Vector(J["elbow.L"]), Vector(J["wrist.L"])
    n = Vector((0.7, -0.7, 0.0)).normalized()
    sc = el.lerp(wr, 0.5) + Vector((0.04, -0.02, 0.0))
    parts += [(cyl_between("cookie", sc - n * 0.009, sc + n * 0.009, 0.085, 0.085, M["cookie"], 40), "forearm.L"),
              (torus("cookie_rim", sc, 0.085, 0.008, M["biscuit"], rot=Vector((0, 0, 1)).rotation_difference(n).to_euler(), seg=48), "forearm.L")]
    side = n.cross(Vector((0, 0, 1))).normalized()
    for k, (u, v) in enumerate(((0.0, 0.0), (0.045, 0.03), (-0.04, 0.035), (0.03, -0.045), (-0.05, -0.02), (0.055, -0.01),
                                (-0.015, 0.06), (0.01, -0.06))):
        parts.append((ellipsoid(f"chip{k}", sc + n * 0.011 + side * u + Vector((0, 0, v)), (0.011, 0.008, 0.01), M["choco_dark"], 10, 6,
                                rot=(0.3 * k, 0.2, 0.5 * k)), "forearm.L"))
    # --- chocolate-dipped biscuit-stick sword with sprinkles (right hand)
    gx, gy = -0.2125, -0.0125
    parts += [
        (cyl_between("sword_grip", (gx, gy, 0.27), (gx, gy, 0.36), 0.011, 0.011, M["biscuit"], 14), "hand.R"),
        (cyl_between("sword_guard", (gx - 0.035, gy, 0.365), (gx + 0.035, gy, 0.365), 0.01, 0.01, M["candy"], 14), "hand.R"),
        (ellipsoid("sword_guard_c", (gx, gy, 0.365), (0.018, 0.018, 0.018), M["candy"], 14, 10), "hand.R"),
        (cyl_between("sword_stick", (gx, gy, 0.37), (gx, gy, 0.5), 0.013, 0.013, M["biscuit"], 14), "hand.R"),
        (cyl_between("sword_choco", (gx, gy, 0.5), (gx, gy, 0.78), 0.017, 0.015, M["choco"], 16), "hand.R"),
        (ellipsoid("sword_tip", (gx, gy, 0.782), (0.015, 0.015, 0.012), M["choco"], 12, 8), "hand.R"),
    ]
    rng = __import__("random").Random(3)
    for k in range(22):
        z = 0.52 + 0.25 * k / 21
        a = rng.uniform(0, 2 * math.pi)
        p0 = Vector((gx + 0.017 * math.cos(a), gy + 0.017 * math.sin(a), z))
        d = Vector((math.cos(a + 1.3), math.sin(a + 1.3), rng.uniform(-0.6, 0.6))).normalized()
        parts.append((cyl_between(f"sprinkle{k}", p0 - d * 0.005, p0 + d * 0.005, 0.0025, 0.0025,
                                  M[("sprinkle_a", "sprinkle_b", "sprinkle_c")[k % 3]], 6), "hand.R"))
    return J, R, M, parts, H, {"Idle": idle_keys, "Slash": cocoa_slash_keys}


def cocoa_slash_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (10, -60, -50, 25), (16, -130, -20, -10), (22, 20, -10, -30), (36, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua, z=abs(ua) * 0.3)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["upper_arm.L"], f, x=-abs(ua) * 0.25, z=-abs(ua) * 0.2)
        key_rot(P["chest"], f, y=ch, x=abs(ch) * 0.3)
        key_rot(P["head"], f, y=-ch * 0.6)


bc.RECIPES.update(pudding=recipe_pudding, cocoa=recipe_cocoa)

if __name__ == "__main__":
    bc.main()
