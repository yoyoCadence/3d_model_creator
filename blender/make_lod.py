"""Level-of-detail copies of a finished, rigged character GLB (mobile / far-distance budgets).

Imports the GLB (mesh + armature + all actions), collapses the mesh with the Decimate modifier
(UVs and skin weights are interpolated, textures are reused), and re-exports every clip. The Blink
morph is dropped on LODs (it is invisible at LOD distances and Decimate cannot keep shape keys).
Spring / collider bones survive, so secondary motion still works on every LOD.

Usage: blender -b --factory-startup -P blender/make_lod.py -- --src assets/models/ink/qinglian.glb \
         --tris 20000 --out assets/models/ink/qinglian_lod1.glb
"""
from __future__ import annotations

import argparse
import json
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
    args = ap.parse_args(argv)
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.src))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    count = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)  # noqa: E731
    before = sum(count(o) for o in meshes)
    ratio = min(1.0, args.tris / max(1, before))
    after = 0
    for obj in meshes:
        if obj.data.shape_keys:
            bpy.context.view_layer.objects.active = obj
            obj.shape_key_clear()
        mod = obj.modifiers.new("lod", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        # keep the armature modifier last so the decimated mesh is what gets skinned
        while obj.modifiers.find("lod") > 0:
            bpy.ops.object.modifier_move_up(modifier="lod")
        bpy.ops.object.modifier_apply(modifier="lod")
        after += count(obj)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for obj in meshes:
        obj.select_set(True)
    out = os.path.abspath(args.out)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_skins=True, export_image_format="AUTO",
                              export_tangents=False, export_morph=False)
    stats = {"src": args.src, "triangles_before": before, "triangles": after, "seconds": round(time.time() - t0, 1),
             "glb_bytes": os.path.getsize(out)}
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
