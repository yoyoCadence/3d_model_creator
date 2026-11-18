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
