"""Stylized ruined arena ("Ember Ruins Arena") for lighting tests and the HTML showcase.

Design notes (see docs/research.md §2):
  * low-contrast circular tile floor -> gameplay readability, characters pop
  * vertical landmarks (broken pillars, banners) for orientation and silhouettes
  * braziers = light sources for the night preset (emissive flames)
  * per-tile colour variation via vertex colours -> hand-painted feel, zero textures

Usage: blender -b --factory-startup -P blender/build_arena.py -- --out assets/arena/arena.glb
"""
from __future__ import annotations

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from build_character import (apply_modifiers, apply_transform, cyl_between, ellipsoid, hex_rgb,  # noqa: E402
                             link, mesh_from_bmesh, reset_scene, rounded_box, set_mat, shade, torus)

random.seed(7)


def pbr(name, color, rough=0.8, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hex_rgb(color), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*hex_rgb(color), 1)
        b.inputs["Emission Strength"].default_value = emit
    # multiply by the vertex colour attribute so per-tile variation shows up in glTF (COLOR_0)
    attr = m.node_tree.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    mix = m.node_tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    mix.inputs[6].default_value = (*hex_rgb(color), 1)
    m.node_tree.links.new(attr.outputs["Color"], mix.inputs[7])
    m.node_tree.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def tint(obj, lo=0.85, hi=1.05, per_face_island=True):
    """Random per-island brightness in a 'Col' colour attribute (stylized stone variation)."""
    me = obj.data
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen, island_val = set(), {}
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        while stack:
            g = stack.pop()
            if g.index in seen:
                continue
            seen.add(g.index)
            isl.append(g.index)
            if per_face_island:
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            stack.append(h)
        v = random.uniform(lo, hi)
        w = random.uniform(-0.03, 0.03)  # slight warm/cool shift
        for i in isl:
            island_val[i] = (v + w, v, v - w)
    bm.free()
    for poly in me.polygons:
        r, g, b = island_val[poly.index]
        for li in poly.loop_indices:
            col.data[li].color = (min(r, 1), min(g, 1), min(b, 1), 1)


def floor(M):
    bm = bmesh.new()
    rings = [0.0, 1.2, 2.3, 3.4, 4.5, 5.6, 6.7]
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        n = max(6, int(2 * math.pi * r1 / 1.1))
        off = random.random()
        for k in range(n):
            a0 = 2 * math.pi * (k + off) / n
            a1 = 2 * math.pi * (k + 1 + off) / n
            gap = 0.035
            pts = []
            for r, a in ((r0 + gap, a0), (r1 - gap, a0), (r1 - gap, a1), (r0 + gap, a1)):
                aa = a + (gap / max(r, 0.3)) * (1 if a == a0 else -1)
                pts.append((r * math.cos(aa), r * math.sin(aa)))
            if r0 == 0.0:
                pts = [(0, 0), pts[1], pts[2]]
            h = 0.06 + random.uniform(-0.012, 0.012)
            bot = [bm.verts.new((x, y, 0)) for x, y in pts]
            top = [bm.verts.new((x, y, h)) for x, y in pts]
            bm.faces.new(top)
            for j in range(len(pts)):
                bm.faces.new((bot[j], bot[(j + 1) % len(pts)], top[(j + 1) % len(pts)], top[j]))
    obj = mesh_from_bmesh("floor", bm)
    set_mat(obj, M["stone"])
    shade(obj, False)
    tint(obj, 0.78, 1.04)
    base = cyl_between("floor_base", (0, 0, -0.3), (0, 0, 0.0), 6.75, 6.75, M["stone_dark"], 64)
    tint(base, 1, 1)
    emblem = torus("emblem", (0, 0, 0.07), 1.15, 0.05, M["brass"], seg=64)
    tint(emblem, 1, 1)
    return [obj, base, emblem]


def wall_and_pillars(M):
    objs = []
    # stepped ring wall with gaps (entrances at 4 sides)
    for k in range(32):
        a = 2 * math.pi * (k + 0.5) / 32
        if any(abs(math.remainder(a - g, 2 * math.pi)) < 0.22 for g in (0, math.pi / 2, math.pi, -math.pi / 2)):
            continue
        for step, (r, h) in enumerate(((7.1, 0.35), (7.6, 0.7))):
            b = rounded_box(f"wall{k}_{step}", (r * math.cos(a), r * math.sin(a), h / 2),
                            (0.26, 0.68, h / 2), M["stone"], 0.03, 2, rot=(0, 0, a))
            tint(b, 0.8, 1.0)
            objs.append(b)
    # pillars (some broken)
    for k in range(12):
        a = 2 * math.pi * k / 12 + 0.13
        p = Vector((8.6 * math.cos(a), 8.6 * math.sin(a), 0))
        broken = k % 3 == 1
        h = random.uniform(1.6, 2.6) if broken else 4.2
        base = rounded_box(f"pbase{k}", p + Vector((0, 0, 0.2)), (0.55, 0.55, 0.2), M["stone"], 0.04, 2)
        shaft = cyl_between(f"pshaft{k}", p + Vector((0, 0, 0.4)), p + Vector((0, 0, h)), 0.42, 0.36, M["stone"], 12)
        shade(shaft, False)
        objs += [base, shaft]
        if not broken:
            cap = rounded_box(f"pcap{k}", p + Vector((0, 0, h + 0.15)), (0.6, 0.6, 0.15), M["stone"], 0.04, 2)
            objs.append(cap)
        else:  # fallen chunk
            q = p + Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0.3))
            chunk = cyl_between(f"pchunk{k}", q, q + Vector((0.9, 0.3, 0.05)), 0.38, 0.38, M["stone"], 12)
            shade(chunk, False)
            objs.append(chunk)
        for o in objs[-3:]:
            tint(o, 0.82, 1.02)
        if k in (0, 3, 6, 9) and not broken:  # team banners: crimson (anvil) / green (verdant)
            team = M["crimson"] if k in (0, 6) else M["green"]
            d = -p.normalized()
            bp = p + d * 0.42 + Vector((0, 0, h - 1.0))
            ban = rounded_box(f"banner{k}", bp, (0.42, 0.02, 0.9), team, 0.01, 1, rot=(0, 0, a + math.pi / 2),
                              taper_bottom=0.7)
            trim = rounded_box(f"banner_trim{k}", bp - d * 0.01, (0.46, 0.012, 0.94), M["brass"], 0.01, 1,
                               rot=(0, 0, a + math.pi / 2), taper_bottom=0.7)
            rod = cyl_between(f"rod{k}", bp + Vector((0, 0, 0.92)) - d.cross(Vector((0, 0, 1))) * 0.55,
                              bp + Vector((0, 0, 0.92)) + d.cross(Vector((0, 0, 1))) * 0.55, 0.03, 0.03, M["brass"], 8)
            for o in (ban, trim, rod):
                tint(o, 1, 1)
            objs += [ban, trim, rod]
    return objs


def braziers(M):
    objs = []
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        p = Vector((6.2 * math.cos(a), 6.2 * math.sin(a), 0))
        for j in range(3):
            b = 2 * math.pi * j / 3
            foot = p + Vector((0.32 * math.cos(b), 0.32 * math.sin(b), 0))
            objs.append(cyl_between(f"leg{k}{j}", foot, p + Vector((0, 0, 0.9)), 0.035, 0.03, M["iron"], 6))
        bowl = ellipsoid(f"bowl{k}", p + Vector((0, 0, 1.0)), (0.38, 0.38, 0.2), M["iron"], 16, 10)
        bm = bmesh.new(); bm.from_mesh(bowl.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > p.z + 1.06], context="VERTS")
        bm.to_mesh(bowl.data); bm.free()
        rim = torus(f"brim{k}", p + Vector((0, 0, 1.06)), 0.37, 0.035, M["brass"], seg=24, mseg=6)
        flame = cyl_between(f"flame{k}", p + Vector((0, 0, 1.0)), p + Vector((0, 0, 1.75)), 0.26, 0.0, M["fire"], 10)
        core = cyl_between(f"flamecore{k}", p + Vector((0, 0, 1.0)), p + Vector((0, 0, 1.45)), 0.15, 0.0, M["fire_core"], 8)
        for f_ in (flame, core):  # flicker-like twist
            for v in f_.data.vertices:
                h = v.co.z - p.z - 1.0
                v.co.x += 0.05 * math.sin(h * 9 + k)
                v.co.y += 0.05 * math.cos(h * 7 + k)
        objs += [bowl, rim, flame, core]
    for o in objs:
        tint(o, 1, 1)
    return objs


def backdrop(M):
    objs = []
    for k in range(18):
        a = 2 * math.pi * k / 18 + random.uniform(-0.1, 0.1)
        r = random.uniform(13, 16)
        s = random.uniform(1.8, 3.5)
        o = ellipsoid(f"rock{k}", (r * math.cos(a), r * math.sin(a), s * 0.6), (s * 1.3, s, s * 1.4), M["cliff"], 7, 5,
                      rot=(random.random(), random.random(), random.random()))
        shade(o, False)
        tint(o, 0.8, 1.0)
        objs.append(o)
    ground = cyl_between("ground", (0, 0, -0.32), (0, 0, -0.3), 22, 22, M["sand"], 48)
    tint(ground, 1, 1)
    objs.append(ground)
    return objs


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[argv.index("--out") + 1] if "--out" in argv else "assets/arena/arena.glb")
    reset_scene()
    M = dict(
        stone=pbr("stone", "#9E8C74", 0.9), stone_dark=pbr("stone_dark", "#7D6E5C", 0.95),
        brass=pbr("brass", "#C9A045", 0.4, 0.9), iron=pbr("iron", "#4A4744", 0.6, 0.8),
        crimson=pbr("banner_crimson", "#9A2B2B", 0.85), green=pbr("banner_green", "#1F6F5C", 0.85),
        fire=pbr("fire", "#FF6A1A", 0.5, 0, emit=2.2), fire_core=pbr("fire_core", "#FFC25A", 0.5, 0, emit=3.5),
        cliff=pbr("cliff", "#8E7A6A", 0.95), sand=pbr("sand", "#A88E6E", 0.95),
    )
    objs = floor(M) + wall_and_pillars(M) + braziers(M) + backdrop(M)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    # merge by material -> one draw call per material (game-engine friendly)
    groups = {}
    for o in objs:
        groups.setdefault(o.data.materials[0].name, []).append(o)
    merged = []
    for name, group in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for o in group:
            o.select_set(True)
        bpy.context.view_layer.objects.active = group[0]
        if len(group) > 1:
            bpy.ops.object.join()
        bpy.context.object.name = f"arena_{name}"
        merged.append(bpy.context.object)
    objs = merged
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_yup=True,
                              export_colors=True) if bpy.app.version < (4, 1) else \
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_yup=True)
    print(f"ARENA {len(objs)} objects, {tris} tris -> {out}")


if __name__ == "__main__":
    main()
