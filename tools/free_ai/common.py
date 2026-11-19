"""Shared helpers for the free-tool pipelines."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "characters.json"
ASSETS = ROOT / "assets"
RESULTS = ROOT / "results" / "runs.json"


def load_characters() -> list[dict]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))["characters"]


def copy_out(src: str | Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def record_run(entry: dict) -> None:
    """Append/replace one run record (keyed by tool+character) in results/runs.json."""
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    runs = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    key = (entry["tool"], entry["character"])
    runs = [r for r in runs if (r["tool"], r["character"]) != key]
    entry.setdefault("recorded_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    runs.append(entry)
    runs.sort(key=lambda r: (r["tool"], r["character"]))
    RESULTS.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        self.seconds = round(time.time() - self.t0, 1)


def srgb_u8_to_linear_u8(rgb_u8):
    """glTF COLOR_0 is *linear*; AI models predict display (sRGB) colours -> convert before export."""
    import numpy as np

    c = np.asarray(rgb_u8, dtype=np.float64)[..., :3] / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.clip(np.round(lin * 255), 0, 255).astype(np.uint8)


def add_default_material(glb_path, roughness: float = 0.8) -> None:
    """trimesh writes vertex-colour GLBs without a material; glTF's default material is
    metallic=1 / roughness=1 (dark rough metal). Add an explicit non-metal material instead."""
    import json
    import struct
    from pathlib import Path

    p = Path(glb_path)
    b = p.read_bytes()
    jlen = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jlen])
    rest = b[20 + jlen:]
    j.setdefault("materials", []).append(
        {"name": "ai_vertex_colour", "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": roughness}})
    mi = len(j["materials"]) - 1
    for m in j.get("meshes", []):
        for prim in m["primitives"]:
            prim.setdefault("material", mi)
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + len(rest)
    p.write_bytes(b[:8] + struct.pack("<I", total) + struct.pack("<I", len(js)) + b"JSON" + js + rest)
