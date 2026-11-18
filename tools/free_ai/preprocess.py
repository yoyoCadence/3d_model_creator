"""Shared image preprocessing for image-to-3D models: background removal + centring.

rembg (MIT, U^2-Net) downloads its ONNX weights from GitHub releases on first use.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

_session = None


def remove_bg(img: Image.Image) -> Image.Image:
    global _session
    import rembg

    if _session is None:
        _session = rembg.new_session("u2net")
    return rembg.remove(img.convert("RGB"), session=_session)


def centre_rgba(img: Image.Image, ratio: float = 0.85, size: int = 1024) -> Image.Image:
    """Crop to the alpha bbox, pad to a square so the subject fills `ratio` of it."""
    a = np.asarray(img.convert("RGBA"))
    ys, xs = np.nonzero(a[..., 3] > 16)
    crop = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    side = int(max(crop.size) / ratio)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return canvas.resize((size, size), Image.LANCZOS)


def on_grey(img: Image.Image, grey: float = 0.5) -> Image.Image:
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255
    rgb = a[..., :3] * a[..., 3:4] + grey * (1 - a[..., 3:4])
    return Image.fromarray((rgb * 255).astype(np.uint8))
