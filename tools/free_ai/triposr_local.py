"""Image -> 3D on CPU with TripoSR (MIT licence, open-sourced by Tripo AI + Stability AI).

Needs the TripoSR repo checked out (TRIPOSR_DIR) and the weights from stabilityai/TripoSR.
torchmcubes (a CUDA/C++ build) is replaced by PyMCubes through a tiny shim.

Usage: TRIPOSR_DIR=/path/TripoSR python tools/free_ai/triposr_local.py --image assets/concepts/anvil_lcm_s12.png --char anvil
Output: assets/models/triposr/<char>.glb (vertex colours) + assets/models/triposr/<char>_input.png
"""
from __future__ import annotations

import argparse
import os
import sys
import types

import numpy as np
import torch
import trimesh
from PIL import Image

from common import ASSETS, Timer, record_run, srgb_u8_to_linear_u8
from preprocess import centre_rgba, on_grey, remove_bg


def install_mcubes_shim() -> None:
    import mcubes

    def marching_cubes(vol: torch.Tensor, thresh: float):
        v, f = mcubes.marching_cubes(vol.cpu().numpy().astype(np.float64), thresh)
        # torchmcubes returns vertices in reversed axis order (TripoSR swaps back with [2, 1, 0]);
        # winding is made outward-facing after extraction
        return torch.from_numpy(v[:, ::-1].copy()).float(), torch.from_numpy(f.astype(np.int64).copy())

    mod = types.ModuleType("torchmcubes")
    mod.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = mod


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--char", required=True)
    ap.add_argument("--resolution", type=int, default=256)
    ap.add_argument("--threshold", type=float, default=25.0)
    args = ap.parse_args()

    sys.path.insert(0, os.environ["TRIPOSR_DIR"])
    install_mcubes_shim()
    from tsr.system import TSR

    torch.set_grad_enabled(False)
    with Timer() as t_load:
        model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
        model.renderer.set_chunk_size(8192)
        model.to("cpu")

    out_dir = ASSETS / "models" / "triposr"
    out_dir.mkdir(parents=True, exist_ok=True)
    with Timer() as t_run:
        rgba = centre_rgba(remove_bg(Image.open(args.image)), ratio=0.85, size=512)
        rgba.save(out_dir / f"{args.char}_input.png")
        codes = model([on_grey(rgba)], device="cpu")
        mesh = model.extract_mesh(codes, True, resolution=args.resolution, threshold=args.threshold)[0]
    vc = mesh.visual.vertex_colors
    vc[:, :3] = srgb_u8_to_linear_u8(vc)
    mesh.visual.vertex_colors = vc
    if mesh.volume < 0:  # outward-facing normals
        mesh.invert()
    # TripoSR space -> glTF (Y up, front = +Z)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))  # face +Z (glTF front)
    out = out_dir / f"{args.char}.glb"
    mesh.export(out)
    print(f"{args.char}: {len(mesh.faces)} tris, load {t_load.seconds}s, run {t_run.seconds}s -> {out}")
    record_run({
        "tool": "triposr", "character": args.char, "kind": "image-to-3d",
        "input": os.path.relpath(args.image, ASSETS.parent), "output": str(out.relative_to(ASSETS.parent)),
        "seconds": t_run.seconds, "load_seconds": t_load.seconds, "triangles": int(len(mesh.faces)),
        "texture": "vertex colours", "where": "local CPU (4 vCPU)", "licence": "MIT",
    })


if __name__ == "__main__":
    main()
