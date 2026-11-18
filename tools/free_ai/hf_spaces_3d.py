"""Image -> 3D through free Hugging Face Spaces (ZeroGPU). Free, but anonymous quota is tiny:
set HF_TOKEN (a free account token, read scope) for a usable daily GPU quota.

Spaces used (all official, all free):
  trellis2   microsoft/TRELLIS.2          MIT          shape + PBR texture
  hunyuan21  tencent/Hunyuan3D-2.1        Tencent CL   shape + texture
  sf3d       stabilityai/stable-fast-3d   Stability CL fast shape + texture

Usage: python tools/free_ai/hf_spaces_3d.py --tool trellis2 --image assets/concepts/x.png --char anvil
"""
from __future__ import annotations

import argparse
import os
import traceback

from gradio_client import Client, handle_file

from common import ASSETS, Timer, copy_out, record_run
from preprocess import centre_rgba, remove_bg

SPACES = {
    "trellis2": "microsoft/TRELLIS.2",
    "hunyuan21": "tencent/Hunyuan3D-2.1",
    "sf3d": "stabilityai/stable-fast-3d",
}


def run_trellis2(client, img_path):
    client.predict(api_name="/start_session")
    client.predict(image=handle_file(img_path), seed=1234, resolution="1024", api_name="/image_to_3d")
    glb, _ = client.predict(decimation_target=60000, texture_size=2048, api_name="/extract_glb")
    return glb


def run_hunyuan21(client, img_path):
    textured, white, *_ = client.predict(image=handle_file(img_path), steps=30, guidance_scale=5.0, seed=1234,
                                         octree_resolution=256, check_box_rembg=True, num_chunks=8000,
                                         randomize_seed=False, api_name="/generation_all")
    return textured or white


def run_sf3d(client, img_path):
    _, glb = client.predict(input_image=handle_file(img_path), foreground_ratio=0.85, remesh_option="None",
                            vertex_count=-1, texture_size=1024, api_name="/run_button")
    return glb


RUNNERS = {"trellis2": run_trellis2, "hunyuan21": run_hunyuan21, "sf3d": run_sf3d}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True, choices=SPACES)
    ap.add_argument("--image", required=True)
    ap.add_argument("--char", required=True)
    args = ap.parse_args()

    from PIL import Image

    out_dir = ASSETS / "models" / args.tool
    out_dir.mkdir(parents=True, exist_ok=True)
    inp = out_dir / f"{args.char}_input.png"
    centre_rgba(remove_bg(Image.open(args.image)), 0.85, 1024).save(inp)
    entry = {"tool": args.tool, "character": args.char, "kind": "image-to-3d",
             "input": os.path.relpath(args.image, ASSETS.parent),
             "where": f"Hugging Face Space {SPACES[args.tool]} (ZeroGPU, free)"}
    try:
        client = Client(SPACES[args.tool], token=os.environ.get("HF_TOKEN"), verbose=False)
        with Timer() as t:
            glb = RUNNERS[args.tool](client, str(inp))
        out = copy_out(glb, out_dir / f"{args.char}.glb")
        entry.update(output=str(out.relative_to(ASSETS.parent)), seconds=t.seconds)
        print(f"{args.tool}/{args.char}: {t.seconds}s -> {out}")
    except Exception as e:  # quota errors etc. are part of the comparison
        entry.update(error=str(e).splitlines()[-1][:300])
        traceback.print_exc()
    record_run(entry)


if __name__ == "__main__":
    main()
