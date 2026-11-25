"""Level-of-detail copies of a finished, rigged character GLB (mobile / far-distance budgets).

Imports the GLB (mesh + armature + all actions), collapses the mesh with the Decimate modifier
(UVs and skin weights are interpolated, textures are reused), and re-exports every clip. The Blink
morph is dropped on LODs (it is invisible at LOD distances and Decimate cannot keep shape keys).
Spring / collider bones survive, so secondary motion still works on every LOD.

Usage: blender -b --factory-startup -P blender/make_lod.py -- --src assets/models/ink/qinglian.glb \
         --tris 15000 --tex 1024 --out assets/models/ink/qinglian_lod1.glb
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tris", type=int, required=True, help="triangle budget")
    ap.add_argument("--tex", type=int, default=0, help="downscale textures to this size (0 = keep)")
    ap.add_argument("--smooth", type=float, default=50.0, help="auto-smooth angle for the recomputed normals")
    ap.add_argument("--min-ratio", type=float, default=0.08, help="big parts keep at least this share (hard-surface: 0.15)")
    ap.add_argument("--planar", type=float, default=0.0,
                    help="hard-surface: first dissolve near-coplanar faces (degrees) - keeps panels flat instead of collapsing boxes")
    args = ap.parse_args(argv)
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # merge seam-split vertices so loose parts are real parts (not UV islands) and seams are not decimation borders
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.src), merge_vertices=True)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    count = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)  # noqa: E731
    before = sum(count(o) for o in meshes)
    height = max(o.dimensions.z for o in meshes) or 1.0  # before splitting into parts
    # Decimate per loose part: a global ratio collapses thin, low-poly props (staffs, straps, pins) to
    # nothing. Parts that are already cheap (<= SMALL tris) stay untouched; bigger parts share the rest
    # of the budget but never drop below FLOOR tris.
    pieces = []
    for obj in meshes:
        if obj.data.shape_keys:
            bpy.context.view_layer.objects.active = obj
            obj.shape_key_clear()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
        group = list(bpy.context.selected_objects)
        pieces.append((obj, group))
    if args.planar:
        for _, group in pieces:
            for part in group:
                mod = part.modifiers.new("planar", "DECIMATE")
                mod.decimate_type = "DISSOLVE"
                mod.angle_limit = math.radians(args.planar)
                mod.delimit = {"UV"}
                tri = part.modifiers.new("tri", "TRIANGULATE")
                bpy.context.view_layer.objects.active = part
                for name in ("planar", "tri"):
                    while part.modifiers.find(name) > (0 if name == "planar" else 1):
                        bpy.ops.object.modifier_move_up(modifier=name)
                    bpy.ops.object.modifier_apply(modifier=name)
    SMALL, FLOOR, MIN_RATIO = 64, 12, args.min_ratio  # big parts keep a share so they never turn into spikes
    part_ratio = lambda t, r: 1.0 if t <= SMALL else min(1.0, max(r, MIN_RATIO, FLOOR / t))  # noqa: E731
    sizes = [count(o) for _, g in pieces for o in g]
    keep = lambda r: sum(t * part_ratio(t, r) for t in sizes)  # noqa: E731
    # far LODs may drop the tiniest props (rivets, knuckles, sprinkles) when they alone blow the budget
    dropped = 0
    if keep(0.0) > args.tris:
        small = sorted(((part.dimensions.length, gi, part) for gi, (_, g) in enumerate(pieces) for part in g),
                       key=lambda x: x[0])
        for diag, gi, part in small:
            if keep(0.0) <= args.tris or diag > 0.02 * height:
                break
            sizes.remove(count(part))
            pieces[gi][1].remove(part)
            bpy.data.objects.remove(part)
            dropped += 1
    lo, hi = 0.0, 1.0
    for _ in range(40):  # binary search the shared ratio
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if keep(mid) < args.tris else (lo, mid)
    ratio = lo
    after = 0
    for obj, group in pieces:
        for part in group:
            t = count(part)
            r = part_ratio(t, ratio)
            if r < 1.0:
                mod = part.modifiers.new("lod", "DECIMATE")
                mod.decimate_type = "COLLAPSE"
                mod.ratio = r
                mod.use_collapse_triangulate = True
                bpy.context.view_layer.objects.active = part
                while part.modifiers.find("lod") > 0:  # decimate before the armature modifier
                    bpy.ops.object.modifier_move_up(modifier="lod")
                bpy.ops.object.modifier_apply(modifier="lod")
        bpy.ops.object.select_all(action="DESELECT")
        for part in group:
            part.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()
        # imported custom split normals do not survive collapsing -> dark smears; recompute instead
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = math.radians(args.smooth)
        after += count(obj)
    if args.tex:  # LODs are seen smaller -> smaller textures (what mip levels would pick anyway)
        for img in bpy.data.images:
            if img.size[0] > args.tex:
                img.scale(args.tex, args.tex)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for obj in meshes:
        obj.select_set(True)
    out = os.path.abspath(args.out)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_skins=True, export_image_format="JPEG", export_jpeg_quality=88,
                              export_tangents=False, export_morph=False)
    stats = {"src": args.src, "parts": len(sizes), "small_parts": sum(t <= SMALL for t in sizes), "dropped_parts": dropped, "triangles_before": before, "triangles": after, "seconds": round(time.time() - t0, 1),
             "glb_bytes": os.path.getsize(out)}
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
