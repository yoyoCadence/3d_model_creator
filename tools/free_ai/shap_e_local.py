"""Text -> 3D directly (no concept image) on CPU with OpenAI Shap-E (MIT licence, no account).

Install: pip install git+https://github.com/openai/shap-e  (weights come from openaipublic.azureedge.net)
Usage:   python tools/free_ai/shap_e_local.py --char anvil [--steps 64]
Output:  assets/models/shap-e/<char>.glb (vertex colours)
"""
from __future__ import annotations

import argparse

import numpy as np
import torch
import trimesh

from common import ASSETS, Timer, load_characters, record_run

PROMPTS = {  # Shap-E was trained on short object captions -> keep prompts short and concrete
    "anvil": "a stocky armored knight with a round shield and a war hammer",
    "verdant": "a female mage in a green hooded cloak holding a wooden staff",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--steps", type=int, default=64)
    ap.add_argument("--guidance", type=float, default=15.0)
    args = ap.parse_args()

    from shap_e.diffusion.gaussian_diffusion import diffusion_from_config
    from shap_e.diffusion.sample import sample_latents
    from shap_e.models.download import load_config, load_model
    from shap_e.util.notebooks import decode_latent_mesh

    torch.set_grad_enabled(False)
    dev = torch.device("cpu")
    with Timer() as t_load:
        xm = load_model("transmitter", device=dev)
        model = load_model("text300M", device=dev)
        diffusion = diffusion_from_config(load_config("diffusion"))
    torch.manual_seed(1234)
    with Timer() as t_run:
        latents = sample_latents(batch_size=1, model=model, diffusion=diffusion, guidance_scale=args.guidance,
                                 model_kwargs=dict(texts=[PROMPTS[args.char]]), progress=True, clip_denoised=True,
                                 use_fp16=False, use_karras=True, karras_steps=args.steps, sigma_min=1e-3,
                                 sigma_max=160, s_churn=0)
        tm = decode_latent_mesh(xm, latents[0]).tri_mesh()
    cols = np.stack([tm.vertex_channels[c] for c in "RGB"], -1)
    mesh = trimesh.Trimesh(tm.verts, tm.faces, vertex_colors=(np.clip(cols, 0, 1) * 255).astype(np.uint8))
    # Shap-E is Z-up and faces -Y -> glTF Y-up, front +Z
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    out = ASSETS / "models" / "shap-e" / f"{args.char}.glb"
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    print(f"{args.char}: {len(mesh.faces)} tris, load {t_load.seconds}s, run {t_run.seconds}s -> {out}")
    record_run({"tool": "shap-e", "character": args.char, "kind": "text-to-3d", "prompt": PROMPTS[args.char],
                "output": str(out.relative_to(ASSETS.parent)), "seconds": t_run.seconds,
                "load_seconds": t_load.seconds, "triangles": int(len(mesh.faces)), "texture": "vertex colours",
                "where": "local CPU (4 vCPU)", "licence": "MIT"})


if __name__ == "__main__":
    load_characters()
    main()
