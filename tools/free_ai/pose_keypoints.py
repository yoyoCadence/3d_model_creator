"""2D body keypoints on the AI input images with ViTPose (usyd-community/vitpose-base-simple, Apache-2.0, CPU).

The keypoints are later lifted onto the 3D mesh by blender/postprocess_ai.py (--pose) so the skeleton follows
the generated body instead of a fixed template.

Usage: python tools/free_ai/pose_keypoints.py hunyuan3d-mini/anvil hunyuan3d-mini/sora triposr/verdant ...
Writes assets/models/<tool>/<char>_pose.json (COCO-17 keypoints in input-image pixels + scores + alpha bbox).
"""
from __future__ import annotations

import json
import sys

import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, VitPoseForPoseEstimation

from common import ASSETS

COCO = ["nose", "l_eye", "r_eye", "l_ear", "r_ear", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist",
        "r_wrist", "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle"]
MODEL = "usyd-community/vitpose-base-simple"


def main() -> None:
    processor = AutoProcessor.from_pretrained(MODEL)
    model = VitPoseForPoseEstimation.from_pretrained(MODEL).eval()
    for item in sys.argv[1:]:
        tool, char = item.split("/")
        src = ASSETS / "models" / tool / f"{char}_input.png"
        rgba = Image.open(src).convert("RGBA")
        a = np.asarray(rgba)[..., 3] > 16
        ys, xs = np.nonzero(a)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        rgb = Image.new("RGB", rgba.size, (255, 255, 255))
        rgb.paste(rgba, mask=rgba.split()[3])
        pad = 0.05 * (y1 - y0)
        box = [[[max(0, x0 - pad), max(0, y0 - pad), (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad]]]  # COCO xywh
        inputs = processor(rgb, boxes=box, return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
        res = processor.post_process_pose_estimation(out, boxes=box)[0][0]
        kps = res["keypoints"].tolist()
        sc = res["scores"].tolist()
        data = {"image": src.name, "size": list(rgba.size), "alpha_bbox": [x0, y0, x1, y1],
                "keypoints": {n: {"x": k[0], "y": k[1], "score": s} for n, k, s in zip(COCO, kps, sc)}}
        dst = src.with_name(f"{char}_pose.json")
        dst.write_text(json.dumps(data, indent=2))
        low = [n for n, s in zip(COCO, sc) if s < 0.3]
        print(f"{tool}/{char}: mean score {np.mean(sc):.2f}, low-confidence: {low or 'none'} -> {dst.name}")


if __name__ == "__main__":
    main()
