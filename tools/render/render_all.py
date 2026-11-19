"""Render every model listed in site/data/tools.json with the shared viewer (same light for all).

Usage: THREE_DIR=/path/node_modules/three python3 tools/render/render_all.py [--only triposr]
Writes assets/renders/<tool>/<char>_<preset>_<view>.png and fills "renders" in tools.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "site" / "data" / "tools.json"
SHOTS = [("studio", "three_quarter"), ("studio", "front"), ("studio", "back"), ("flat", "front"), ("sunset", "three_quarter")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    heights = {c["id"]: c["height"] for c in data["characters"]}
    jobs = []
    for tool in data["tools"]:
        if args.only and tool["id"] != args.only:
            continue
        for char, m in tool["models"].items():
            m["renders"] = {}
            for preset, view in SHOTS:
                out = f"assets/renders/{tool['id']}/{char}_{preset}_{view}.png"
                job = {"model": m["glb"], "out": out, "preset": preset, "view": view, "w": 480, "h": 600}
                if tool["id"] != "blender":  # AI meshes have arbitrary scale -> normalise height
                    job["height"] = heights[char]
                jobs.append(job)
                m["renders"][f"{preset}_{view}"] = out
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    subprocess.run(["node", str(ROOT / "tools/render/shoot.mjs"), f.name], check=True, env=os.environ)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rendered {len(jobs)} shots")


if __name__ == "__main__":
    main()
