"""Make a raw AI mesh game-ready with free Blender tools (no manual work):

  1. normalise height / feet on the ground / facing glTF +Z
  2. Decimate (collapse) to a triangle budget
  3. Smart UV + high->low bake of the original vertex colours into one BaseColor texture
     (selected-to-active Cycles EMIT bake: colours come from the untouched AI surface)
  4. Rig with the same 19-bone template skeleton as the procedural characters (auto weights)
  5. Idle animation, GLB export

Limitation: joints come from the template scaled to the mesh height, not detected on the mesh,
so arms can be slightly off -> fine for idle/small motions, large motions would need Mixamo/AccuRIG.

Usage: blender -b --factory-startup -P blender/postprocess_ai.py -- --char anvil \
         --src assets/models/triposr/anvil.glb --out assets/models/triposr-blender/anvil.glb [--tris 20000]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import build_character as bc  # noqa: E402


def template_joints(char: str) -> dict:
    if char not in bc.RECIPES:  # anime recipes register themselves on import
        import build_anime  # noqa: F401
    bc.reset_scene()
    J = bc.RECIPES[char]()[0]
    bc.reset_scene()
    return J


def pose_joints(J, pose_path, obj, H):
    """Lift ViTPose 2D keypoints onto the normalised mesh: image bbox -> mesh (x, z), depth = centre of the
    mesh cross-section around that point. Low-confidence keypoints keep the template joint."""
    import json as _json
    d = _json.load(open(pose_path))
    K = d["keypoints"]
    x0, y0, x1, y1 = d["alpha_bbox"]
    co = np.array([v.co[:] for v in obj.data.vertices])
    lo, hi = co.min(0), co.max(0)

    def to3d(name):
        k = K[name]
        if k["score"] < 0.3:
            return None
        x = lo[0] + (k["x"] - x0) / (x1 - x0) * (hi[0] - lo[0])
        z = lo[2] + (y1 - k["y"]) / (y1 - y0) * (hi[2] - lo[2])
        r = 0.035 * H
        m = (np.abs(co[:, 0] - x) < r) & (np.abs(co[:, 2] - z) < r)
        y = 0.5 * (co[m, 1].min() + co[m, 1].max()) if m.any() else 0.0
        return Vector((x, y, z))

    P = {n: to3d(n) for n in K}
    if P["l_shoulder"] is not None and P["r_shoulder"] is not None and P["l_shoulder"].x < P["r_shoulder"].x:
        for a in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"):  # keep .L on +X
            P[f"l_{a}"], P[f"r_{a}"] = P[f"r_{a}"], P[f"l_{a}"]
    out = {k: Vector(v) for k, v in J.items()}
    for s, side in (("L", "l"), ("R", "r")):
        for ours, coco in (("shoulder", "shoulder"), ("elbow", "elbow"), ("wrist", "wrist"), ("hip", "hip"),
                           ("knee", "knee"), ("ankle", "ankle")):
            if P[f"{side}_{coco}"] is not None:
                out[f"{ours}.{s}"] = P[f"{side}_{coco}"]
        out[f"hand_end.{s}"] = out[f"wrist.{s}"] + (out[f"wrist.{s}"] - out[f"elbow.{s}"]) * 0.35
        a = out[f"ankle.{s}"]
        out[f"toe.{s}"] = Vector((a.x, a.y - 0.065 * H, 0.02 * H))
    hips = (out["hip.L"] + out["hip.R"]) / 2 + Vector((0, 0, 0.03 * H))
    neck = (out["shoulder.L"] + out["shoulder.R"]) / 2 + Vector((0, 0, 0.035 * H))
    out.update(hips=hips, spine=hips.lerp(neck, 0.3), chest=hips.lerp(neck, 0.62), neck=neck,
               head=neck + Vector((0, 0, 0.03 * H)), head_top=Vector((neck.x, neck.y, hi[2])))
    return {k: tuple(v) for k, v in out.items()}


def arms_up_keys(arm):
    """Big-motion test clip: shows whether the skeleton really sits inside the arms."""
    from build_character import key_rot
    P = arm.pose.bones
    for f, k in ((1, 0.0), (15, 1.0), (30, 1.0), (45, 0.0)):
        for s, sx in (("L", 1), ("R", -1)):
            key_rot(P[f"upper_arm.{s}"], f, z=-70 * k * sx)
            key_rot(P[f"forearm.{s}"], f, z=-25 * k * sx)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tris", type=int, default=20000)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--uv-angle", type=float, default=80.0)
    ap.add_argument("--pose", help="ViTPose keypoints json (tools/free_ai/pose_keypoints.py) -> skeleton from the body")
    args = ap.parse_args(argv)
    t0 = time.time()

    J = template_joints(args.char)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(args.src))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    obj.parent = None
    bc.apply_transform(obj)
    if obj.data.has_custom_normals:  # imported split normals break after decimation; recompute instead
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    src_tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)

    # 1) normalise: template height (head top), feet at z=0, centred
    co = np.array([v.co[:] for v in obj.data.vertices])
    lo, hi = co.min(0), co.max(0)
    target_h = J["head_top"][2] + 0.02
    s = target_h / (hi[2] - lo[2])
    centre = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
    for v in obj.data.vertices:
        v.co = (v.co - centre) * s

    # keep the untouched high-poly as the colour source for a high->low bake
    hi = obj.copy()
    hi.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(hi)

    rig_source = "template"
    if args.pose and os.path.exists(args.pose):
        J = pose_joints(J, args.pose, obj, target_h)
        rig_source = "pose (ViTPose)"

    # 2) decimate to the budget
    ratio = min(1.0, args.tris / max(1, src_tris))
    dec = obj.modifiers.new("decimate", "DECIMATE")
    dec.ratio = ratio
    dec.use_collapse_triangulate = True
    bc.apply_modifiers(obj)
    # decimation can leave degenerate polygons -> repair, then recompute outward normals, smooth fully
    obj.data.validate(clean_customdata=False)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.dissolve_degenerate()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.validate(clean_customdata=False)
    bc.shade(obj, True, 180)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)

    # 3) UV + bake vertex colours -> texture
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # AI triangle soup -> many tiny islands; a wide angle limit keeps islands large so bake margins don't bleed
    bpy.ops.uv.smart_project(angle_limit=math.radians(args.uv_angle), island_margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")
    col_name = hi.data.color_attributes[0].name if hi.data.color_attributes else None
    # source material on the high-poly: vertex colours as emission
    src = bpy.data.materials.new(f"M_{args.char}_hi")
    src.use_nodes = True
    snt = src.node_tree
    sout = next(n for n in snt.nodes if n.type == "OUTPUT_MATERIAL")
    em = snt.nodes.new("ShaderNodeEmission")
    if col_name:
        attr = snt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = col_name
        snt.links.new(attr.outputs["Color"], em.inputs["Color"])
    snt.links.new(em.outputs[0], sout.inputs["Surface"])
    hi.data.materials.clear()
    hi.data.materials.append(src)
    # target material on the low-poly: the image being baked
    m = bpy.data.materials.new(f"M_{args.char}_ai")
    m.use_nodes = True
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    img = bpy.data.images.new(f"{args.char}_ai_basecolor", args.tex, args.tex, alpha=False)
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img
    nt.nodes.active = tn
    obj.data.materials.clear()
    obj.data.materials.append(m)
    sc = bpy.context.scene
    sc.cycles.samples = 1
    sc.render.bake.margin = 4
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=0.02, max_ray_distance=0.08)
    bpy.data.objects.remove(hi)
    tex_dir = os.path.join(os.path.dirname(os.path.abspath(args.out)), "textures")
    os.makedirs(tex_dir, exist_ok=True)
    img.filepath_raw = os.path.join(tex_dir, f"{args.char}_basecolor.png")
    img.file_format = "PNG"
    img.save()
    # final PBR material: baked colour, rough non-metal
    for n in list(nt.nodes):
        if n not in (out, tn):
            nt.nodes.remove(n)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.7
    nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    for ca in list(obj.data.color_attributes):
        obj.data.color_attributes.remove(ca)

    # 4) rig with the template skeleton
    arm = bc.build_armature(J)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    weighted = sum(1 for v in obj.data.vertices if len(v.groups))

    # 5) idle + arms-up test animations, export
    arm.animation_data_create()
    for clip, fn in bc.with_base_clips({"ArmsUp": arms_up_keys}).items():
        act = bpy.data.actions.new(clip)
        arm.animation_data.action = act
        fn(arm)
        act.use_fake_user = True
        track = arm.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, act)
        track.mute = True
        arm.animation_data.action = None
    bc.reset_pose(arm)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(args.out), export_format="GLB", use_selection=True,
                              export_animations=True, export_animation_mode="ACTIONS", export_skins=True)
    stats = {"character": args.char, "source": args.src, "source_triangles": src_tris, "triangles": tris,
             "weighted_vertex_ratio": round(weighted / len(obj.data.vertices), 3), "bones": len(arm.data.bones),
             "texture_size": args.tex, "rig_source": rig_source, "seconds": round(time.time() - t0, 1)}
    with open(os.path.abspath(args.out).replace(".glb", ".stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("STATS", json.dumps(stats))


if __name__ == "__main__":
    main()
