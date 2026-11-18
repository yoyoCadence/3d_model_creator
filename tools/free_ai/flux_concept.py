"""Text -> concept image with FLUX.1-schnell (Apache-2.0) on its free Hugging Face Space.

Usage:  python tools/free_ai/flux_concept.py [--seed 42] [--only anvil]
Output: assets/concepts/<id>_flux.png
"""
from __future__ import annotations

import argparse

from gradio_client import Client

from common import ASSETS, Timer, copy_out, load_characters, record_run

SPACE = "black-forest-labs/FLUX.1-schnell"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only")
    ap.add_argument("--steps", type=int, default=4)
    args = ap.parse_args()

    client = Client(SPACE, verbose=False)
    for ch in load_characters():
        if args.only and ch["id"] != args.only:
            continue
        with Timer() as t:
            img, seed = client.predict(
                prompt=ch["flux_prompt"],
                seed=args.seed,
                randomize_seed=False,
                width=768,
                height=1024,
                num_inference_steps=args.steps,
                api_name="/infer",
            )
        path = img["path"] if isinstance(img, dict) else img
        out = copy_out(path, ASSETS / "concepts" / f"{ch['id']}_flux.png")
        print(f"{ch['id']}: {out} ({t.seconds}s, seed={seed})")
        record_run({
            "tool": "flux-schnell",
            "character": ch["id"],
            "kind": "text-to-image",
            "output": str(out.relative_to(ASSETS.parent)),
            "seconds": t.seconds,
            "seed": seed,
            "where": f"Hugging Face Space {SPACE} (ZeroGPU, free)",
        })


if __name__ == "__main__":
    main()
