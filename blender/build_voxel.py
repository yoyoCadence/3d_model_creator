"""Voxel-art character (體素藝術) - original design 「方塊遊俠」 Cube Ranger, an explorer.

How it is built (no texture bake - colour lives in the voxels):
  * shapes are painted into a 2.5 cm voxel grid in metres (boxes, ellipsoids, capsules), each voxel
    carrying a palette colour and the bone it belongs to (rigid skinning per voxel)
  * face culling: only faces between a filled and an empty cell become quads
  * per-vertex voxel ambient occlusion (two edge neighbours + the corner neighbour, the classic
    voxel-game formula) multiplied into the vertex colour, plus +-5% per-voxel colour jitter
  * emissive palette entries (lantern glass) get a second material with emission
Exports a skinned GLB with COLOR_0 vertex colours, Idle + Swing clips.

Usage: blender -b --factory-startup -P blender/build_voxel.py -- --out assets/models/voxel/cuberanger.glb
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


def build_mesh(g: Grid, palette, glow_ids, bone_names, seed=7):
    rng = random.Random(seed)
    occ = np.pad(g.col > 0, 1)
    verts, faces, cols, vbone, fmat = [], [], [], [], []
    jitter = {}
    filled = np.argwhere(g.col > 0)
    for (i, j, k) in filled:
        ci = int(g.col[i, j, k])
        key = (i, j, k)
        jitter[key] = 0.95 + 0.1 * rng.random()
        base = np.array(palette[ci]) * jitter[key]
        for (dx, dy, dz), axis in DIRS:
            if occ[i + 1 + dx, j + 1 + dy, k + 1 + dz]:
                continue
            n = np.array((dx, dy, dz))
            # the two in-plane axes
            u_ax, v_ax = [a for a in range(3) if a != axis]
            quad = []
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                corner = np.array([i, j, k], dtype=float) + 0.5 + n * 0.5
                corner[u_ax] += 0.5 * su
                corner[v_ax] += 0.5 * sv
                # voxel AO: neighbours in the layer in front of the face
                f = np.array([i, j, k]) + n
                s1 = f.copy(); s1[u_ax] += su
                s2 = f.copy(); s2[v_ax] += sv
                cc = f.copy(); cc[u_ax] += su; cc[v_ax] += sv
                o1, o2, o3 = (occ[tuple(p + 1)] for p in (s1, s2, cc))
                ao = 0 if (o1 and o2) else 3 - (int(o1) + int(o2) + int(o3))
                shade_k = (0.5, 0.67, 0.84, 1.0)[ao]
                verts.append(tuple(g.o + corner * V))
                cols.append(tuple(np.clip(base * shade_k, 0, 1)) + (1.0,))
                vbone.append(int(g.bone[i, j, k]))
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
    obj = bc.link(bpy.data.objects.new("cuberanger_mesh", me))
    me.color_attributes.active_color = ca
    for p, m in zip(me.polygons, fmat):
        p.material_index = m
    for bi, name in enumerate(bone_names):
        idx = [vi for vi, b in enumerate(vbone) if b == bi]
        if idx:
            obj.vertex_groups.new(name=name).add(idx, 1.0, "REPLACE")
    return obj


def voxel_material(name, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    if emit:  # glTF has no vertex-colour emission -> constant warm glow
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def design(g: Grid, B, C):
    """Paint the Cube Ranger. B: bone name -> index, C: colour name -> palette index."""
    J = JOINTS
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


def swing_keys(arm):
    P = arm.pose.bones
    seq = [(1, 0, 0, 0), (10, -110, -20, 15), (18, -20, -5, -15), (30, 0, 0, 0)]
    for f, ua, fa, ch in seq:
        key_rot(P["upper_arm.R"], f, x=ua)
        key_rot(P["forearm.R"], f, x=fa)
        key_rot(P["chest"], f, z=ch, x=-abs(ch) * 0.3)
        key_rot(P["upper_arm.L"], f, x=-ua * 0.15)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[argv.index("--out") + 1])
    t0 = time.time()
    bc.reset_scene()
    names = list(PALETTE)
    lin = [bc.hex_rgb(PALETTE[k]) for k in names]
    palette = [(0, 0, 0)] + [tuple(c) for c in lin]
    C = {k: i + 1 for i, k in enumerate(names)}
    bone_names = [b[0] for b in bc.BONES]
    B = {n: i for i, n in enumerate(bone_names)}
    g = Grid()
    design(g, B, C)
    n_vox = int((g.col > 0).sum())
    obj = build_mesh(g, palette, {C["glow"]}, bone_names)
    obj.data.materials.append(voxel_material("M_voxel"))
    obj.data.materials.append(voxel_material("M_voxel_glow", emit=2.5))
    arm = bc.build_armature(JOINTS)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    arm.animation_data_create()
    for name, fn in {"Idle": idle_keys, "Swing": swing_keys}.items():
        act = bpy.data.actions.new(name)
        arm.animation_data.action = act
        fn(arm)
        act.use_fake_user = True
        tr = arm.animation_data.nla_tracks.new()
        tr.name = name
        tr.strips.new(name, 1, act)
        tr.mute = True
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_skins=True, export_colors=True)
    tris = len(obj.data.polygons) * 2
    stats = {"character": "cuberanger", "voxels": n_vox, "voxel_size_m": V, "vertices": len(obj.data.vertices),
             "triangles": tris, "bones": len(arm.data.bones), "materials": 2, "texture_size": 0,
             "animations": ["Idle", "Swing"], "build_seconds": round(time.time() - t0, 1), "glb_bytes": os.path.getsize(out)}
    with open(out.replace(".glb", ".stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
