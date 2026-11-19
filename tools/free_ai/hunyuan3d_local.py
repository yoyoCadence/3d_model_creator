"""Image -> 3D shape on CPU with Hunyuan3D-2mini-turbo (Tencent Hunyuan Community Licence; free,
commercial use allowed below 1M MAU, not licensed in EU/UK/South Korea).

Texture generation (Hunyuan3D-Paint) needs CUDA, so on CPU we only get the shape. To make the
result comparable we add *front-projected vertex colours* from the input image (our post-process,
not part of Hunyuan3D) — the HTML page labels this clearly.

Usage: HY3D_DIR=/path/Hunyuan3D-2 python tools/free_ai/hunyuan3d_local.py --image ... --char anvil
Output: assets/models/hunyuan3d-mini/<char>.glb
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import torch
import trimesh
from PIL import Image

from common import ASSETS, Timer, record_run, srgb_u8_to_linear_u8, add_default_material
from preprocess import centre_rgba, remove_bg


def project_front_colours(mesh: trimesh.Trimesh, rgba: Image.Image) -> None:
    """Planar projection of the input image along -Z (front view) onto vertex colours."""
    img = np.asarray(rgba.convert("RGBA")).astype(np.float32) / 255
    h, w = img.shape[:2]
    v = mesh.vertices
    lo, hi = v.min(0), v.max(0)
    a = np.asarray(rgba)[..., 3] > 16
    ys, xs = np.nonzero(a)
    # map mesh bbox (x, y) onto the image's alpha bbox
    u = (v[:, 0] - lo[0]) / (hi[0] - lo[0])
    t = (v[:, 1] - lo[1]) / (hi[1] - lo[1])
    px = np.clip((xs.min() + u * (xs.max() - xs.min())).astype(int), 0, w - 1)
    py = np.clip((ys.max() - t * (ys.max() - ys.min())).astype(int), 0, h - 1)
    col = img[py, px, :3]
    n = mesh.vertex_normals
    back = n[:, 2] < -0.2
    col[back] *= 0.75  # back side has no information: darken the mirrored front colours
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=srgb_u8_to_linear_u8((np.clip(col, 0, 1) * 255).astype(np.uint8)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--char", required=True)
    ap.add_argument("--steps", type=int, default=5)
    ap.add_argument("--octree", type=int, default=256)
    ap.add_argument("--faces", type=int, default=40000)
    args = ap.parse_args()

    sys.path.insert(0, os.environ["HY3D_DIR"])
    from hy3dgen.shapegen import DegenerateFaceRemover, FaceReducer, FloaterRemover, Hunyuan3DDiTFlowMatchingPipeline

    torch.set_grad_enabled(False)
    with Timer() as t_load:
        pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            "tencent/Hunyuan3D-2mini", subfolder="hunyuan3d-dit-v2-mini-turbo", use_safetensors=True,
            device="cpu", dtype=torch.float32)
        pipe.enable_flashvdm(mc_algo="mc")
        pipe.to(device="cpu", dtype=torch.float32)  # the turbo VAE is loaded in fp16 by default
    out_dir = ASSETS / "models" / "hunyuan3d-mini"
    out_dir.mkdir(parents=True, exist_ok=True)
    rgba = centre_rgba(remove_bg(Image.open(args.image)), ratio=0.9, size=512)
    rgba.save(out_dir / f"{args.char}_input.png")
    with Timer() as t_run:
        mesh = pipe(image=rgba, num_inference_steps=args.steps, octree_resolution=args.octree,
                    num_chunks=20000, generator=torch.manual_seed(1234), output_type="trimesh")[0]
        raw_faces = len(mesh.faces)
        mesh.export(out_dir / f"{args.char}_raw.glb")  # keep the expensive result even if clean-up fails
        mesh = FloaterRemover()(mesh)
        mesh = DegenerateFaceRemover()(mesh)
        mesh = FaceReducer()(mesh, max_facenum=args.faces)
    project_front_colours(mesh, rgba)
    out = out_dir / f"{args.char}.glb"
    mesh.export(out)
    add_default_material(out)
    print(f"{args.char}: raw {raw_faces} -> {len(mesh.faces)} tris, load {t_load.seconds}s, run {t_run.seconds}s")
    record_run({
        "tool": "hunyuan3d-mini", "character": args.char, "kind": "image-to-3d (shape only)",
        "input": os.path.relpath(args.image, ASSETS.parent), "output": str(out.relative_to(ASSETS.parent)),
        "seconds": t_run.seconds, "load_seconds": t_load.seconds, "triangles": int(len(mesh.faces)),
        "raw_triangles": int(raw_faces), "texture": "none (front-projected vertex colours added by us)",
        "where": "local CPU (4 vCPU)", "licence": "Tencent Hunyuan Community License",
    })


if __name__ == "__main__":
    main()
