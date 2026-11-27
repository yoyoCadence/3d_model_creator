"""Voxel-art characters (體素藝術) - original designs 「方塊遊俠」 Cube Ranger and 「方塊魔女」 Voxel Witch.

How it is built (no texture bake - colour lives in the voxels):
  * shapes are painted into a 2.5 cm voxel grid in metres (boxes, ellipsoids, capsules), each voxel
    carrying a palette colour and the bone it belongs to (rigid skinning per voxel)
  * face culling: only faces between a filled and an empty cell become quads
  * per-vertex voxel ambient occlusion (two edge neighbours + the corner neighbour, the classic
    voxel-game formula) multiplied into the vertex colour, plus +-5% per-voxel colour jitter
  * emissive palette entries (lantern glass) get a second material with emission
Exports a skinned GLB with COLOR_0 vertex colours, shared base clips + a signature clip.

Usage: blender -b --factory-startup -P blender/build_voxel.py -- --char witch --out assets/models/voxel/witch.glb
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import build_character as bc  # noqa: E402
from build_character import idle_keys, key_rot, mirror_joints  # noqa: E402

V = 0.02  # voxel size (m)
DIRS = [((1, 0, 0), 0), ((-1, 0, 0), 0), ((0, 1, 0), 1), ((0, -1, 0), 1), ((0, 0, 1), 2), ((0, 0, -1), 2)]


class Grid:
    def __init__(self, xr=(-0.5, 0.5), yr=(-0.36, 0.36), zr=(0.0, 1.66)):
        self.o = np.array([xr[0], yr[0], zr[0]])
        self.n = (np.ceil((np.array([xr[1], yr[1], zr[1]]) - self.o) / V)).astype(int)
        self.col = np.zeros(self.n, dtype=np.int16)  # 0 = empty, else palette index
        self.bone = np.zeros(self.n, dtype=np.int16)
        self.centres = self.o + (np.indices(self.n).transpose(1, 2, 3, 0) + 0.5) * V

    def paint(self, mask, col, bone):
        self.col[mask] = col
        self.bone[mask] = bone

    def box(self, lo, hi, col, bone):
        c = self.centres
        m = np.all((c >= np.array(lo)) & (c <= np.array(hi)), axis=-1)
        self.paint(m, col, bone)

    def ellipsoid(self, ctr, r, col, bone):
        d = (self.centres - np.array(ctr)) / np.array(r)
        self.paint((d ** 2).sum(-1) <= 1.0, col, bone)

    def capsule(self, p1, p2, r, col, bone, r2=None):
        p1, p2 = np.array(p1), np.array(p2)
        ab = p2 - p1
        t = np.clip(((self.centres - p1) @ ab) / (ab @ ab), 0, 1)
        closest = p1 + t[..., None] * ab
        rr = r if r2 is None else r + (r2 - r) * t
        self.paint(np.linalg.norm(self.centres - closest, axis=-1) <= rr, col, bone)

    def carve(self, mask):
        self.col[mask] = 0


CORNERS = ((-1, -1), (1, -1), (1, 1), (-1, 1))
SHADE = (0.5, 0.67, 0.84, 1.0)  # voxel AO level 0..3 -> brightness


def build_mesh(g: Grid, palette, glow_ids, bone_names, seed=7, name="voxel", greedy=True):
    """Exposed voxel faces -> quads with per-corner voxel AO.

    Greedy meshing: per direction and slice, neighbouring faces with the same colour, bone and a uniform AO
    (all four corners equal) merge into one rectangle; faces with an AO gradient stay single so the shading
    is unchanged. Colour jitter is applied per emitted quad (merged areas read as one painted block).
    """
    rng = random.Random(seed)
    occ = np.pad(g.col > 0, 1)
    verts, faces, cols, vbone, fmat = [], [], [], [], []
    filled = np.argwhere(g.col > 0)
    for (dx, dy, dz), axis in DIRS:
        n = np.array((dx, dy, dz))
        u_ax, v_ax = [a for a in range(3) if a != axis]
        slices = {}
        for (i, j, k) in filled:
            if occ[i + 1 + dx, j + 1 + dy, k + 1 + dz]:
                continue
            f = np.array([i, j, k]) + n
            aos = []
            for su, sv in CORNERS:  # voxel AO: neighbours in the layer in front of the face
                s1 = f.copy(); s1[u_ax] += su
                s2 = f.copy(); s2[v_ax] += sv
                cc = f.copy(); cc[u_ax] += su; cc[v_ax] += sv
                o1, o2, o3 = (occ[tuple(p + 1)] for p in (s1, s2, cc))
                aos.append(0 if (o1 and o2) else 3 - (int(o1) + int(o2) + int(o3)))
            idx = (i, j, k)
            slices.setdefault(idx[axis], {})[(idx[u_ax], idx[v_ax])] = (int(g.col[i, j, k]), int(g.bone[i, j, k]), tuple(aos))
        for sl in sorted(slices):
            cells, done = slices[sl], set()
            for (u, v) in sorted(cells):
                if (u, v) in done:
                    continue
                val = cells[(u, v)]
                w = h = 1
                if greedy and len(set(val[2])) == 1:
                    same = lambda c: c in cells and c not in done and cells[c] == val  # noqa: E731
                    while same((u + w, v)):
                        w += 1
                    while all(same((uu, v + h)) for uu in range(u, u + w)):
                        h += 1
                for uu in range(u, u + w):
                    for vv in range(v, v + h):
                        done.add((uu, vv))
                ci, bone, aos = val
                base = np.array(palette[ci]) * (0.95 + 0.1 * rng.random())
                quad = []
                for (su, sv), ao in zip(CORNERS, aos):
                    corner = np.zeros(3)
                    corner[axis] = sl + 0.5 + 0.5 * n[axis]
                    corner[u_ax] = u if su < 0 else u + w
                    corner[v_ax] = v if sv < 0 else v + h
                    verts.append(tuple(g.o + corner * V))
                    cols.append(tuple(np.clip(base * SHADE[ao], 0, 1)) + (1.0,))
                    vbone.append(bone)
                    quad.append(len(verts) - 1)
                if sum(n) < 0:  # consistent outward winding
                    quad = quad[::-1]
                if axis == 1:
                    quad = quad[::-1]
                faces.append(quad)
                fmat.append(1 if ci in glow_ids else 0)
    me = bpy.data.meshes.new("voxels")
    me.from_pydata(verts, [], faces)
    me.update()
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.array(cols, dtype=np.float32).ravel())
    obj = bc.link(bpy.data.objects.new(f"{name}_mesh", me))
    me.color_attributes.active_color = ca
    for p, m in zip(me.polygons, fmat):
        p.material_index = m
    for bi, name in enumerate(bone_names):
        idx = [vi for vi, b in enumerate(vbone) if b == bi]
        if idx:
            obj.vertex_groups.new(name=name).add(idx, 1.0, "REPLACE")
    return obj


def voxel_material(name, emit=0.0, emit_color=(1.0, 0.62, 0.22)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    if emit:  # glTF has no vertex-colour emission -> constant warm glow
        bsdf.inputs["Emission Color"].default_value = (*emit_color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def design(g: Grid, B, C, J):
    """Paint the Cube Ranger. B: bone name -> index, C: colour name -> palette index."""
    # legs + boots
    for s, sx in (("L", 1), ("R", -1)):
        g.capsule(J[f"hip.{s}"], J[f"knee.{s}"], 0.075, C["pants"], B[f"thigh.{s}"])
        g.capsule(J[f"knee.{s}"], J[f"ankle.{s}"], 0.068, C["pants"], B[f"shin.{s}"])
        x = 0.1 * sx
        g.box((x - 0.085, -0.17, 0.0), (x + 0.085, 0.09, 0.07), C["sole"], B[f"foot.{s}"])
        g.box((x - 0.08, -0.16, 0.025), (x + 0.08, 0.085, 0.17), C["boot"], B[f"foot.{s}"])
        g.box((x - 0.085, -0.09, 0.15), (x + 0.085, 0.09, 0.2), C["boot_cuff"], B[f"shin.{s}"])
        g.box((x - 0.03, -0.17, 0.09), (x + 0.03, -0.155, 0.14), C["lace"], B[f"foot.{s}"])
    # torso: shirt, jacket, belt, buckle, pockets
    g.box((-0.17, -0.12, 0.6), (0.17, 0.12, 0.95), C["jacket"], B["chest"])
    g.box((-0.17, -0.12, 0.6), (0.17, 0.12, 0.72), C["jacket"], B["spine"])
    g.box((-0.06, -0.13, 0.66), (0.06, -0.11, 0.95), C["shirt"], B["chest"])
    for sx in (-1, 1):
        g.box((0.07 * sx - 0.045, -0.135, 0.73), (0.07 * sx + 0.045, -0.115, 0.8), C["jacket_dark"], B["chest"])
    g.box((-0.18, -0.13, 0.58), (0.18, 0.13, 0.64), C["belt"], B["hips"])
    g.box((-0.03, -0.14, 0.585), (0.03, -0.125, 0.635), C["gold"], B["hips"])
    g.box((-0.17, -0.12, 0.52), (0.17, 0.12, 0.6), C["pants"], B["hips"])
    # arms + gloves + hands
    for s, sx in (("L", 1), ("R", -1)):
        g.capsule(J[f"shoulder.{s}"], J[f"elbow.{s}"], 0.068, C["jacket"], B[f"upper_arm.{s}"])
        g.capsule(J[f"elbow.{s}"], J[f"wrist.{s}"], 0.062, C["jacket"], B[f"forearm.{s}"])
        g.capsule(Vector(J[f"wrist.{s}"]).lerp(Vector(J[f"elbow.{s}"]), 0.15), J[f"wrist.{s}"], 0.07, C["glove"], B[f"forearm.{s}"])
        g.ellipsoid(Vector(J[f"wrist.{s}"]).lerp(Vector(J[f"hand_end.{s}"]), 0.6), (0.055, 0.05, 0.065), C["glove"], B[f"hand.{s}"])
    # head
    g.box((-0.22, -0.19, 0.97), (0.22, 0.19, 1.37), C["skin"], B["head"])
    g.box((-0.05, -0.05, 0.92), (0.05, 0.05, 0.98), C["skin"], B["neck"])
    # hair: back + sides + top, jagged bangs
    g.box((-0.23, -0.05, 1.05), (0.23, 0.2, 1.38), C["hair"], B["head"])
    g.box((-0.23, -0.2, 1.3), (0.23, 0.2, 1.38), C["hair"], B["head"])
    for k, x in enumerate(np.arange(-0.2, 0.21, 0.05)):
        h = (0.06, 0.1, 0.04, 0.08, 0.05, 0.11, 0.07, 0.04, 0.09)[k % 9]
        g.box((x - 0.025, -0.2, 1.3 - h), (x + 0.025, -0.18, 1.31), C["hair"], B["head"])
    for sx in (-1, 1):
        g.box((0.205 * sx - 0.025, -0.2, 1.02), (0.205 * sx + 0.025, 0.0, 1.32), C["hair"], B["head"])
    # face: eyes with highlight, brows, blush, mouth
    for sx in (-1, 1):
        ex = 0.085 * sx
        g.box((ex - 0.035, -0.2, 1.1), (ex + 0.035, -0.185, 1.2), C["eye"], B["head"])
        g.box((ex + 0.012 * sx - 0.013, -0.205, 1.162), (ex + 0.012 * sx + 0.013, -0.183, 1.195), C["white"], B["head"])
        g.box((ex - 0.045, -0.2, 1.225), (ex + 0.045, -0.185, 1.245), C["hair_dark"], B["head"])
        g.box((0.145 * sx - 0.03, -0.2, 1.075), (0.145 * sx + 0.03, -0.188, 1.095), C["blush"], B["head"])
    g.box((-0.035, -0.2, 1.035), (0.035, -0.188, 1.055), C["mouth"], B["head"])
    g.capsule((0, 0.19, 1.22), (0, 0.27, 1.07), 0.055, C["hair"], B["head"])  # back tuft
    g.capsule((0, 0.25, 1.1), (0.0, 0.29, 1.0), 0.035, C["hair_dark"], B["head"])
    # explorer hat: brim + crown + band + feather
    g.box((-0.33, -0.3, 1.36), (0.33, 0.3, 1.4), C["hat"], B["head"])
    brim_z = (g.centres[..., 2] > 1.355) & (g.centres[..., 2] < 1.405)
    g.carve(brim_z & (np.linalg.norm(g.centres[..., :2], axis=-1) > 0.33) & (g.bone == B["head"]))  # round the brim
    g.box((-0.21, -0.19, 1.4), (0.21, 0.19, 1.55), C["hat"], B["head"])
    g.box((-0.215, -0.195, 1.4), (0.215, 0.195, 1.45), C["hat_band"], B["head"])
    g.capsule((0.17, -0.1, 1.45), (0.27, 0.05, 1.62), 0.018, C["feather"], B["head"])
    # scarf + tail
    g.capsule((-0.15, -0.02, 0.95), (0.15, -0.02, 0.95), 0.06, C["scarf"], B["chest"])
    g.box((-0.15, -0.13, 0.9), (0.15, 0.13, 0.99), C["scarf"], B["chest"])
    g.capsule((0.1, -0.13, 0.93), (0.14, -0.16, 0.72), 0.035, C["scarf"], B["chest"])
    g.capsule((0.14, -0.16, 0.72), (0.15, -0.16, 0.68), 0.03, C["scarf_dark"], B["chest"])
    # belt pouch, compass medallion
    g.box((0.08, -0.15, 0.53), (0.17, -0.12, 0.63), C["pack_dark"], B["hips"])
    g.box((0.11, -0.16, 0.6), (0.14, -0.145, 0.62), C["gold"], B["hips"])
    g.box((-0.13, -0.135, 0.84), (-0.07, -0.12, 0.9), C["gold"], B["chest"])
    g.box((-0.11, -0.14, 0.86), (-0.09, -0.13, 0.88), C["glass"], B["chest"])
    # backpack + straps + bedroll
    g.box((-0.15, 0.12, 0.62), (0.15, 0.3, 0.92), C["pack"], B["chest"])
    g.box((-0.12, 0.29, 0.66), (0.12, 0.32, 0.8), C["pack_dark"], B["chest"])
    for sx in (-1, 1):
        g.box((0.11 * sx - 0.025, -0.13, 0.72), (0.11 * sx + 0.025, -0.115, 0.95), C["pack_dark"], B["chest"])
    g.capsule((-0.19, 0.22, 0.98), (0.19, 0.22, 0.98), 0.065, C["roll"], B["chest"])
    for x in (-0.12, 0.0, 0.12):
        g.box((x - 0.012, 0.15, 0.91), (x + 0.012, 0.29, 1.05), C["roll_stripe"], B["chest"])
    # rope coil on the side of the pack
    rope = (g.centres - np.array((0.17, 0.21, 0.77))) / np.array((0.035, 0.085, 0.085))
    ring = ((rope ** 2).sum(-1) <= 1.0) & ((((g.centres - np.array((0.17, 0.21, 0.77))) / np.array((0.05, 0.05, 0.05))) ** 2).sum(-1) > 1.0)
    g.paint(ring, C["rope"], B["chest"])
    # lantern (left hand): frame, glowing glass, cap, handle
    lx, ly = 0.39, -0.02
    g.box((lx - 0.06, ly - 0.06, 0.3), (lx + 0.06, ly + 0.06, 0.32), C["metal"], B["hand.L"])
    g.box((lx - 0.05, ly - 0.05, 0.32), (lx + 0.05, ly + 0.05, 0.44), C["glow"], B["hand.L"])
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        g.box((lx + dx * 0.05 - 0.012, ly + dy * 0.05 - 0.012, 0.32), (lx + dx * 0.05 + 0.012, ly + dy * 0.05 + 0.012, 0.44),
              C["metal"], B["hand.L"])
    g.box((lx - 0.065, ly - 0.065, 0.44), (lx + 0.065, ly + 0.065, 0.47), C["metal"], B["hand.L"])
    g.box((lx - 0.035, ly - 0.035, 0.47), (lx + 0.035, ly + 0.035, 0.49), C["metal"], B["hand.L"])
    g.capsule((lx, ly, 0.49), (lx, ly, 0.52), 0.015, C["metal"], B["hand.L"])
    # pickaxe (right hand)
    px, py = -0.385, -0.02
    g.capsule((px, py, 0.2), (px, py, 0.84), 0.022, C["wood"], B["hand.R"])
    g.box((px - 0.025, py - 0.03, 0.82), (px + 0.025, py + 0.03, 0.87), C["metal"], B["hand.R"])
    g.capsule((px, py - 0.24, 0.81), (px, py + 0.24, 0.86), 0.025, C["steel"], B["hand.R"], r2=0.03)
    g.carve((np.abs(g.centres[..., 0] - px) < 0.03) & (np.abs(g.centres[..., 1] - py) > 0.2) & (g.centres[..., 2] < 0.82))


JOINTS = mirror_joints({
    "hips": (0, 0, 0.62), "spine": (0, 0, 0.72), "chest": (0, 0, 0.84),
    "neck": (0, 0, 0.94), "head": (0, 0, 0.97), "head_top": (0, 0, 1.45),
    "shoulder.L": (0.21, 0, 0.9), "elbow.L": (0.3, 0.0, 0.74),
    "wrist.L": (0.37, -0.01, 0.58), "hand_end.L": (0.39, -0.015, 0.52),
    "hip.L": (0.1, 0, 0.58), "knee.L": (0.1, -0.01, 0.33),
    "ankle.L": (0.1, 0.01, 0.1), "toe.L": (0.1, -0.12, 0.04),
})

PALETTE = {
    "skin": "#F2C9A0", "hair": "#7A4A2A", "hair_dark": "#4E2E1A", "eye": "#2A2030", "white": "#FFFFFF",
    "blush": "#F29C9C", "mouth": "#A6453F", "jacket": "#C9A46A", "jacket_dark": "#A98650", "shirt": "#F1E6CF",
    "belt": "#6B4423", "gold": "#E3B341", "pants": "#5E6B3A", "boot": "#4A3020", "boot_cuff": "#5C3D28",
    "sole": "#2B2320", "lace": "#D9C9A8", "glove": "#7A5232", "hat": "#B89B6A", "hat_band": "#5A3A22",
    "feather": "#D2473A", "scarf": "#2BA39A", "scarf_dark": "#1E7C75", "pack": "#7A5232", "pack_dark": "#5A3C24",
    "roll": "#B5473A", "roll_stripe": "#EFE3C8", "metal": "#3E3E44", "glow": "#FFB347", "wood": "#8B5A2B",
    "steel": "#A7B0BA", "rope": "#C8A86A", "glass": "#7FD3E6",
}


@bc.hit(15)  # axe comes down in front
def swing_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (10, -110, -20, 15), (18, -20, -5, -15), (30, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["chest"], f, z=ch, x=-abs(ch) * 0.3)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.15)


# ----------------------------------------------------------------------------------------
# 方塊魔女 Voxel Witch
# ----------------------------------------------------------------------------------------

WITCH_JOINTS = mirror_joints({
    "hips": (0, 0, 0.62), "spine": (0, 0, 0.72), "chest": (0, 0, 0.84),
    "neck": (0, 0, 0.94), "head": (0, 0, 0.97), "head_top": (0, 0, 1.45),
    "shoulder.L": (0.2, 0, 0.9), "elbow.L": (0.29, 0.0, 0.74),
    "wrist.L": (0.36, -0.01, 0.58), "hand_end.L": (0.38, -0.015, 0.52),
    "hip.L": (0.09, 0, 0.58), "knee.L": (0.09, -0.01, 0.33),
    "ankle.L": (0.09, 0.01, 0.1), "toe.L": (0.09, -0.12, 0.04),
})

WITCH_PALETTE = {
    "skin": "#F6D2B8", "hair": "#3B2A5C", "hair_dark": "#261A3D", "eye": "#2FA36B", "eye_dark": "#14482F", "white": "#FFFFFF",
    "lash": "#1C1426", "blush": "#F4A0A8", "lips": "#C2506A", "dress": "#6A3FA0", "dress_dark": "#4A2A78", "trim": "#B79CE8",
    "gold": "#F0C24A", "lace": "#EDE2FF", "stocking": "#7E4FC2", "stocking_dark": "#221A2E", "boot": "#2A2032", "sole": "#16121C",
    "hat": "#3A2560", "hat_dark": "#26183F", "cape": "#2D1F4A", "cape_in": "#8E3A6E", "wood": "#8B5A2B", "wood_dark": "#6A4220",
    "straw": "#E2B65A", "straw_dark": "#B88A3A", "band": "#B83A4A", "glass": "#BFE8F0", "potion": "#7CFF6B", "cork": "#A8784A",
    "cat": "#1E1C24", "cat_light": "#34313E", "cat_eye": "#E8E04A", "cat_nose": "#E88AA0", "collar": "#B83A4A",
}


def design_witch(g: Grid, B, C, J):
    c = g.centres
    x, y, z = c[..., 0], c[..., 1], c[..., 2]
    # legs: striped stockings, curled-toe boots with buckles
    for s, sx in (("L", 1), ("R", -1)):
        g.capsule(J[f"hip.{s}"], J[f"knee.{s}"], 0.064, C["stocking"], B[f"thigh.{s}"])
        g.capsule(J[f"knee.{s}"], J[f"ankle.{s}"], 0.058, C["stocking"], B[f"shin.{s}"])
        leg = (np.abs(x - 0.09 * sx) < 0.08) & (z < 0.58) & (z > 0.15) & (g.col == C["stocking"])
        g.paint(leg & ((np.floor(z / 0.04) % 2) == 0), C["stocking_dark"], -1)
        g.bone[leg] = np.where(z[leg] > 0.33, B[f"thigh.{s}"], B[f"shin.{s}"])
        bx = 0.09 * sx
        g.box((bx - 0.07, -0.13, 0.0), (bx + 0.07, 0.08, 0.03), C["sole"], B[f"foot.{s}"])
        g.box((bx - 0.065, -0.12, 0.02), (bx + 0.065, 0.075, 0.18), C["boot"], B[f"foot.{s}"])
        g.capsule((bx, -0.12, 0.05), (bx, -0.2, 0.07), 0.04, C["boot"], B[f"foot.{s}"], r2=0.025)
        g.capsule((bx, -0.2, 0.07), (bx, -0.235, 0.12), 0.025, C["boot"], B[f"foot.{s}"], r2=0.012)
        g.box((bx - 0.03, -0.135, 0.07), (bx + 0.03, -0.12, 0.11), C["gold"], B[f"foot.{s}"])
        g.box((bx - 0.07, -0.125, 0.16), (bx + 0.07, 0.08, 0.19), C["trim"], B[f"shin.{s}"])
    # A-line skirt: upper half on the hips, lower half split per leg so legs never poke through
    t = np.clip((0.66 - z) / (0.66 - 0.3), 0, 1)
    r = 0.165 + 0.15 * t
    ang = np.arctan2(y, x)
    hem = 0.3 + 0.045 * np.abs(((ang * 10 / (2 * np.pi)) % 1.0) * 2 - 1)  # zig-zag hem
    skirt = ((x / r) ** 2 + (y / (r * 0.82)) ** 2 <= 1.0) & (z <= 0.66) & (z >= hem)
    g.paint(skirt, C["dress"], B["hips"])
    shell = skirt & ((x / (r - 0.03)) ** 2 + (y / ((r - 0.03) * 0.82)) ** 2 > 1.0)
    g.paint(skirt & (z < hem + 0.045), C["trim"], B["hips"])
    for k in range(10):  # gold star dots around the skirt
        a = (k + 0.5) * 2 * np.pi / 10
        sp = np.array((0.27 * np.cos(a), 0.27 * 0.82 * np.sin(a), 0.42 + 0.03 * (k % 2)))
        g.paint(shell & (np.linalg.norm(c - sp, axis=-1) < 0.022), C["gold"], B["hips"])
    low = skirt & (z < 0.5)
    g.bone[low & (x >= 0)] = B["thigh.L"]
    g.bone[low & (x < 0)] = B["thigh.R"]
    # bodice with criss-cross lacing, belt + buckle, potion pouch
    g.box((-0.15, -0.11, 0.64), (0.15, 0.11, 0.94), C["dress"], B["chest"])
    g.box((-0.15, -0.11, 0.62), (0.15, 0.11, 0.72), C["dress"], B["spine"])
    g.box((-0.045, -0.12, 0.68), (0.045, -0.105, 0.9), C["dress_dark"], B["chest"])
    for k in range(6):
        zz = 0.7 + k * 0.034
        for sx in (-1, 1):
            g.box((0.012 * sx * (1 if k % 2 else -1) - 0.012, -0.13, zz), (0.012 * sx * (1 if k % 2 else -1) + 0.012, -0.115, zz + 0.016),
                  C["lace"], B["chest"])
    g.box((-0.16, -0.12, 0.62), (0.16, 0.12, 0.67), C["dress_dark"], B["hips"])
    g.box((-0.03, -0.13, 0.615), (0.03, -0.115, 0.675), C["gold"], B["hips"])
    g.box((-0.17, -0.15, 0.52), (-0.08, -0.11, 0.62), C["cape"], B["hips"])
    for k, xx in enumerate((-0.155, -0.125, -0.095)):
        g.box((xx - 0.01, -0.145, 0.62), (xx + 0.01, -0.125, 0.68 + 0.01 * k), C["glass"], B["hips"])
        g.box((xx - 0.008, -0.143, 0.62), (xx + 0.008, -0.127, 0.645), (C["potion"], C["band"], C["trim"])[k], B["hips"])
    # cape: high pointed collar, back panel with lining at the hem
    g.box((-0.2, -0.04, 0.9), (0.2, 0.13, 0.97), C["cape"], B["chest"])
    g.box((-0.17, 0.08, 0.94), (0.17, 0.14, 1.1), C["cape"], B["chest"])
    for sx in (-1, 1):
        g.capsule((0.17 * sx, 0.1, 1.08), (0.21 * sx, 0.08, 1.16), 0.025, C["cape"], B["chest"])
    cape = (np.abs(x) <= 0.17 + 0.18 * np.clip((0.94 - z) / 0.6, 0, 1)) & (y >= 0.11) & (y <= 0.14 + 0.06 * np.clip((0.94 - z) / 0.6, 0, 1)) \
        & (z <= 0.94) & (z >= 0.36 + 0.05 * np.abs(((x * 8) % 1.0) * 2 - 1))
    g.paint(cape, C["cape"], B["chest"])
    g.paint(cape & (z < 0.45) & (y > 0.13), C["cape_in"], B["chest"])
    # bell sleeves with trim, hands
    for s, sx in (("L", 1), ("R", -1)):
        g.capsule(J[f"shoulder.{s}"], J[f"elbow.{s}"], 0.064, C["dress"], B[f"upper_arm.{s}"])
        g.capsule(J[f"elbow.{s}"], J[f"wrist.{s}"], 0.064, C["dress"], B[f"forearm.{s}"], r2=0.1)
        w, e = np.array(J[f"wrist.{s}"]), np.array(J[f"elbow.{s}"])
        g.capsule(w + (e - w) * 0.1, w, 0.09, C["trim"], B[f"forearm.{s}"])
        g.capsule(w + (e - w) * 0.05, w, 0.06, C["dress_dark"], B[f"forearm.{s}"])
        g.ellipsoid(Vector(J[f"wrist.{s}"]).lerp(Vector(J[f"hand_end.{s}"]), 0.6), (0.048, 0.045, 0.06), C["skin"], B[f"hand.{s}"])
    # head, long hair, bangs, face
    g.box((-0.21, -0.19, 0.97), (0.21, 0.19, 1.36), C["skin"], B["head"])
    g.box((-0.05, -0.05, 0.92), (0.05, 0.05, 0.98), C["skin"], B["neck"])
    hw = 0.225 - 0.3 * np.clip(1.0 - z, 0, 1)  # long hair narrows towards a jagged tip
    hem_h = 0.7 + 0.06 * np.abs(((x / 0.06) % 1.0) * 2 - 1)
    g.paint((np.abs(x) <= hw) & (y >= -0.04) & (y <= 0.21 - 0.15 * np.clip(1.0 - z, 0, 1)) & (z >= hem_h) & (z <= 1.38), C["hair"], B["head"])
    g.box((-0.225, -0.2, 1.28), (0.225, 0.2, 1.38), C["hair"], B["head"])
    for k, xx in enumerate(np.arange(-0.19, 0.2, 0.04)):
        h = (0.08, 0.05, 0.1, 0.06, 0.04, 0.09, 0.05, 0.11, 0.06, 0.08)[k % 10]
        g.box((xx - 0.02, -0.205, 1.28 - h), (xx + 0.02, -0.185, 1.29), C["hair"], B["head"])
    for sx in (-1, 1):
        g.box((0.2 * sx - 0.03, -0.2, 0.86), (0.2 * sx + 0.03, -0.02, 1.3), C["hair"], B["head"])
        g.box((0.2 * sx - 0.03, -0.2, 0.86), (0.2 * sx + 0.03, -0.17, 0.9), C["hair_dark"], B["head"])
    hair_back = (g.col == C["hair"]) & (y > 0.15) & (np.floor(x / 0.04) % 2 == 0)
    g.paint(hair_back, C["hair_dark"], -1)
    g.bone[hair_back] = B["head"]
    # ribbon tying the long hair: band + two loops + tails
    g.paint((g.col == C["hair"]) & (np.abs(z - 0.9) < 0.022) & (y > 0.0), C["band"], B["head"])
    for sx in (-1, 1):
        g.ellipsoid((0.07 * sx, 0.2, 0.92), (0.06, 0.025, 0.04), C["band"], B["head"])
        g.capsule((0.02 * sx, 0.2, 0.88), (0.05 * sx, 0.21, 0.8), 0.015, C["band"], B["head"])
    g.box((-0.02, 0.18, 0.89), (0.02, 0.23, 0.94), C["collar"], B["head"])
    for sx in (-1, 1):
        ex = 0.085 * sx
        g.box((ex - 0.04, -0.2, 1.08), (ex + 0.04, -0.185, 1.19), C["eye"], B["head"])
        g.box((ex - 0.04, -0.2, 1.08), (ex + 0.04, -0.185, 1.11), C["eye_dark"], B["head"])
        g.box((ex - 0.012, -0.203, 1.1), (ex + 0.012, -0.183, 1.16), C["eye_dark"], B["head"])
        g.box((ex + 0.02 * sx - 0.012, -0.205, 1.155), (ex + 0.02 * sx + 0.012, -0.183, 1.18), C["white"], B["head"])
        g.box((ex - 0.05, -0.2, 1.19), (ex + 0.05, -0.185, 1.21), C["lash"], B["head"])
        g.box((ex + 0.04 * sx, -0.2, 1.19), (ex + 0.06 * sx, -0.185, 1.23), C["lash"], B["head"])
        g.box((0.15 * sx - 0.03, -0.2, 1.05), (0.15 * sx + 0.03, -0.188, 1.07), C["blush"], B["head"])
    g.box((-0.03, -0.2, 1.01), (0.03, -0.188, 1.03), C["lips"], B["head"])
    g.box((-0.012, -0.205, 1.07), (0.012, -0.19, 1.09), C["blush"], B["head"])
    # hat: round brim, crooked cone crown, band + buckle, gold stars
    brim = (np.linalg.norm(c[..., :2] - np.array((0, 0.01)), axis=-1) <= 0.37) & (z >= 1.36) & (z <= 1.41)
    g.paint(brim, C["hat"], B["head"])
    g.paint(brim & (np.linalg.norm(c[..., :2] - np.array((0, 0.01)), axis=-1) > 0.34), C["hat_dark"], B["head"])
    tt = np.clip((z - 1.41) / 0.5, 0, 1)
    cx, cy, rr = 0.09 * tt ** 3, 0.16 * tt ** 2, 0.22 * (1 - tt) ** 0.85 + 0.012
    crown = ((x - cx) ** 2 + (y - cy) ** 2 <= rr ** 2) & (z > 1.41) & (z <= 1.91)
    g.paint(crown, C["hat"], B["head"])
    g.paint(crown & (z < 1.47), C["band"], B["head"])
    g.box((-0.035, -0.23, 1.415), (0.035, -0.16, 1.47), C["gold"], B["head"])
    g.box((-0.02, -0.24, 1.43), (0.02, -0.16, 1.455), C["band"], B["head"])
    for zz, a in ((1.56, -0.5), (1.66, 0.6), (1.75, -0.2)):
        t0 = (zz - 1.41) / 0.5
        sp = np.array((0.09 * t0 ** 3 + (0.22 * (1 - t0) ** 0.85 + 0.012) * np.sin(a), 0.16 * t0 ** 2 - (0.22 * (1 - t0) ** 0.85 + 0.012) * np.cos(a), zz))
        g.paint(crown & (np.linalg.norm(c - sp, axis=-1) < 0.03), C["gold"], B["head"])
    # broom (right hand): handle, binding, straw bristles
    px, py = -0.375, -0.02
    g.capsule((px, py, 0.3), (px, py, 1.22), 0.02, C["wood"], B["hand.R"])
    g.capsule((px, py, 1.22), (px + 0.03, py, 1.27), 0.022, C["wood_dark"], B["hand.R"])
    g.box((px - 0.035, py - 0.035, 0.26), (px + 0.035, py + 0.035, 0.31), C["band"], B["hand.R"])
    br = (np.abs(z - 0.17) <= 0.1) & (np.hypot(x - px, y - py) <= 0.035 + 0.35 * (0.27 - z).clip(0, 0.2))
    g.paint(br, C["straw"], B["hand.R"])
    g.paint(br & ((np.floor((x - px) / 0.02) + np.floor((y - py) / 0.02)) % 3 == 0), C["straw_dark"], B["hand.R"])
    # glowing potion flask (left hand)
    fx, fy = 0.39, -0.03
    g.ellipsoid((fx, fy, 0.42), (0.065, 0.065, 0.065), C["glass"], B["hand.L"])
    g.paint((((c - np.array((fx, fy, 0.42))) / 0.065) ** 2).sum(-1) <= 1.0, C["glass"], B["hand.L"])
    g.paint(((((c - np.array((fx, fy, 0.42))) / 0.065) ** 2).sum(-1) <= 1.0) & (z < 0.44), C["potion"], B["hand.L"])
    g.capsule((fx, fy, 0.46), (fx, fy, 0.53), 0.022, C["glass"], B["hand.L"])
    g.capsule((fx, fy, 0.53), (fx, fy, 0.56), 0.025, C["cork"], B["hand.L"])
    # black cat on the left shoulder
    kx = 0.335
    g.ellipsoid((kx, 0.0, 1.0), (0.06, 0.075, 0.07), C["cat"], B["chest"])
    g.box((kx - 0.055, -0.1, 1.06), (kx + 0.055, 0.0, 1.16), C["cat"], B["chest"])
    for sx in (-1, 1):
        g.box((kx + 0.035 * sx - 0.02, -0.07, 1.16), (kx + 0.035 * sx + 0.02, -0.03, 1.2), C["cat"], B["chest"])
        g.box((kx + 0.035 * sx - 0.01, -0.075, 1.16), (kx + 0.035 * sx + 0.01, -0.065, 1.185), C["cat_nose"], B["chest"])
        g.box((kx + 0.025 * sx - 0.012, -0.105, 1.11), (kx + 0.025 * sx + 0.012, -0.095, 1.135), C["cat_eye"], B["chest"])
    g.box((kx - 0.008, -0.106, 1.09), (kx + 0.008, -0.096, 1.102), C["cat_nose"], B["chest"])
    g.box((kx - 0.055, -0.105, 1.06), (kx + 0.055, -0.095, 1.075), C["cat_light"], B["chest"])
    g.box((kx - 0.045, -0.08, 0.93), (kx + 0.045, -0.06, 1.03), C["cat_light"], B["chest"])
    g.box((kx - 0.06, -0.075, 1.04), (kx + 0.06, 0.06, 1.06), C["collar"], B["chest"])
    g.box((kx - 0.012, -0.085, 1.025), (kx + 0.012, -0.07, 1.045), C["gold"], B["chest"])
    g.capsule((kx + 0.04, 0.06, 0.96), (kx + 0.1, 0.1, 1.04), 0.02, C["cat"], B["chest"])
    g.capsule((kx + 0.1, 0.1, 1.04), (kx + 0.09, 0.07, 1.13), 0.018, C["cat"], B["chest"])


@bc.hit(20)  # potion shaken out at the opponent
def witch_cast_keys(arm):
    """Raise the potion, shake it over the cauldron-less air, lean back with the broom."""
    P = arm.pose.bones
    for f, k, w in ((1, 0, 0), (10, 1, 0), (15, 1, 1), (20, 1, -1), (25, 1, 1), (30, 1, -1), (42, 0, 0)):
        key_rot(P["upper_arm.L"], f, x=-95 * k, z=-15 * k)
        key_rot(P["forearm.L"], f, x=-25 * k, z=18 * w * k)
        key_rot(P["hand.L"], f, z=20 * w * k)
        key_rot(P["upper_arm.R"], f, x=-25 * k, z=12 * k)
        key_rot(P["chest"], f, x=-8 * k, z=6 * k)
        key_rot(P["head"], f, x=-10 * k, z=8 * k)


CHARS = {
    "cuberanger": dict(joints=JOINTS, palette=PALETTE, design=design, clips={"Swing": swing_keys}, glow="glow",
                       emit=(1.0, 0.62, 0.22), grid={}),
    "witch": dict(joints=WITCH_JOINTS, palette=WITCH_PALETTE, design=design_witch, clips={"Cast": witch_cast_keys}, glow="potion",
                  emit=(0.42, 1.0, 0.36), grid=dict(xr=(-0.52, 0.52), yr=(-0.4, 0.4), zr=(0.0, 1.94))),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[argv.index("--out") + 1])
    char = argv[argv.index("--char") + 1] if "--char" in argv else "cuberanger"
    greedy = "--no-greedy" not in argv
    spec = CHARS[char]
    t0 = time.time()
    bc.reset_scene()
    names = list(spec["palette"])
    lin = [bc.hex_rgb(spec["palette"][k]) for k in names]
    palette = [(0, 0, 0)] + [tuple(c) for c in lin]
    C = {k: i + 1 for i, k in enumerate(names)}
    bone_names = [b[0] for b in bc.BONES]
    B = {n: i for i, n in enumerate(bone_names)}
    g = Grid(**spec["grid"])
    spec["design"](g, B, C, spec["joints"])
    n_vox = int((g.col > 0).sum())
    obj = build_mesh(g, palette, {C[spec["glow"]]}, bone_names, name=char, greedy=greedy)
    obj.data.materials.append(voxel_material("M_voxel"))
    obj.data.materials.append(voxel_material("M_voxel_glow", emit=2.5, emit_color=spec["emit"]))
    arm = bc.build_armature(spec["joints"])
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    arm.animation_data_create()
    clips = bc.with_base_clips(spec["clips"])
    for name, fn in clips.items():
        act = bpy.data.actions.new(name)
        arm.animation_data.action = act
        fn(arm)
        act.use_fake_user = True
        tr = arm.animation_data.nla_tracks.new()
        tr.name = name
        tr.strips.new(name, 1, act)
        tr.mute = True
        arm.animation_data.action = None
    bc.reset_pose(arm)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_skins=True, export_colors=True)
    bc.set_clip_extras(out, bc.clip_extras(clips))
    tris = len(obj.data.polygons) * 2
    stats = {"character": char, "voxels": n_vox, "voxel_size_m": V, "greedy": greedy, "vertices": len(obj.data.vertices),
             "triangles": tris, "bones": len(arm.data.bones), "materials": 2, "texture_size": 0,
             "animations": list(clips), "hits": bc.clip_extras(clips), "build_seconds": round(time.time() - t0, 1), "glb_bytes": os.path.getsize(out)}
    with open(out.replace(".glb", ".stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
