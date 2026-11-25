"""Prepare the comparison page for publishing as a claude.ai artifact.

Artifact hosting does not serve .glb, so every model referenced by site/data/tools.json (plus the
arena and the stage casts) is written next to itself as <name>.glb.b64.txt; site/js/viewer.js
loadGLTF() falls back to that copy when the .glb is not served.

Prints the `files` map (published path -> repo path) for the Artifact publish call and the total size.
Usage: python3 tools/render/publish_files.py > /tmp/files.json
Then delete the copies after publishing: find assets -name '*.b64.txt' -delete
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRA_MODELS = ["assets/arena/arena.glb"]  # loaded by the arena stage, not listed per tool


def main() -> None:
    data = json.loads((ROOT / "site/data/tools.json").read_text(encoding="utf-8"))
    files = {"js/viewer.js": "site/js/viewer.js", "data/tools.json": "site/data/tools.json"}
    models = list(EXTRA_MODELS)
    for tool in data["tools"]:
        for m in tool["models"].values():
            models.append(m["glb"])
            models += [lod["glb"] for lod in m.get("lods", [])]
            if m.get("renders", {}).get("studio_three_quarter"):
                r = m["renders"]["studio_three_quarter"]
                files[r] = r
    for c in data.get("concepts", []):
        files[c["src"]] = c["src"]
    for glb in dict.fromkeys(models):
        src = ROOT / glb
        b64 = src.with_name(src.name + ".b64.txt")
        b64.write_text(base64.b64encode(src.read_bytes()).decode())
        files[glb + ".b64.txt"] = glb + ".b64.txt"
    sizes = [(ROOT / v).stat().st_size for v in files.values()]
    print(json.dumps(files, ensure_ascii=False))
    print(f"{len(files)} files, {sum(sizes) / 1e6:.1f} MB, largest {max(sizes) / 1e6:.1f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
