"""Re-colour existing Hunyuan3D meshes with the current projection (no regeneration needed).

Usage: python tools/free_ai/reproject_colors.py anvil verdant sora kai
"""
from __future__ import annotations

import sys

import trimesh
from PIL import Image

from common import ASSETS, add_default_material
from hunyuan3d_local import project_front_colours

for char in sys.argv[1:]:
    d = ASSETS / "models" / "hunyuan3d-mini"
    mesh = trimesh.load(d / f"{char}.glb", force="mesh")
    project_front_colours(mesh, Image.open(d / f"{char}_input.png"))
    mesh.export(d / f"{char}.glb")
    add_default_material(d / f"{char}.glb")
    print(char, len(mesh.faces), "faces re-coloured")
