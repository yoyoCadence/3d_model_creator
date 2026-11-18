"""Text -> concept image on CPU with LCM-Dreamshaper-v7 (MIT licence, 4-8 steps, no account needed).

Usage: python tools/free_ai/lcm_concept_local.py [--seeds 1 2 3 4] [--steps 6]
Output: assets/concepts/<id>_lcm_s<seed>.png  (+ a contact sheet per character)
"""
from __future__ import annotations

import argparse

import torch
from diffusers import DiffusionPipeline
from PIL import Image

from common import ASSETS, Timer, load_characters, record_run

MODEL = "SimianLuo/LCM_Dreamshaper_v7"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--only")
    args = ap.parse_args()
    torch.set_num_threads(max(1, torch.get_num_threads()))
    pipe = DiffusionPipeline.from_pretrained(MODEL, torch_dtype=torch.float32, safety_checker=None)
    pipe.to("cpu")
    for ch in load_characters():
        if args.only and ch["id"] != args.only:
            continue
        imgs = []
        for seed in args.seeds:
            with Timer() as t:
                img = pipe(ch["sd_prompt"], num_inference_steps=args.steps, guidance_scale=8.0,
                           width=512, height=768, generator=torch.manual_seed(seed)).images[0]
            out = ASSETS / "concepts" / f"{ch['id']}_lcm_s{seed}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out)
            imgs.append(img)
            print(f"{ch['id']} seed {seed}: {t.seconds}s -> {out}", flush=True)
            record_run({"tool": f"lcm-dreamshaper-s{seed}", "character": ch["id"], "kind": "text-to-image",
                        "output": str(out.relative_to(ASSETS.parent)), "seconds": t.seconds, "seed": seed,
                        "where": "local CPU (4 vCPU)"})
        sheet = Image.new("RGB", (512 * len(imgs), 768), "white")
        for i, im in enumerate(imgs):
            sheet.paste(im, (512 * i, 0))
        sheet.save(ASSETS / "concepts" / f"{ch['id']}_lcm_sheet.png")


if __name__ == "__main__":
    main()
