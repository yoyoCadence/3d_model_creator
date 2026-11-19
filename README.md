# 3d_model_creator

遊戲用 3D 角色開發：用**免費工具**做出兩個角色，並比較各工具的效果。

![Blender 程序化角色](assets/renders/blender/turnaround_studio.png)

| 角色 | 定位 | 檔案 |
|---|---|---|
| 鐵砧・布蘭（anvil） | 重裝先鋒 | `assets/models/blender/anvil.glb` |
| 翠羽・萊拉（verdant） | 秘法遊俠 | `assets/models/blender/verdant.glb` |

- 設計說明：[docs/character_design.md](docs/character_design.md)
- 進度與交接：[docs/PROGRESS.md](docs/PROGRESS.md)
- 給 agent 的說明：[CLAUDE.md](CLAUDE.md)

## 免費工具比較（全部本機 CPU、$0、不需帳號）

![比較](assets/renders/comparison_studio.png)

| 做法 | 類型 | 面數 | 貼圖 | 骨架 | 每隻耗時 |
|---|---|---|---|---|---|
| Blender + Python | 程序化建模 | 21k / 24k | 2048 烘焙 PBR | 19 骨 + 動畫 | 48–89 秒（建置） |
| Hunyuan3D-2mini + Blender 後處理 | AI + 自動後處理 | 20k | 2048 烘焙 | 19 骨 + Idle | ~2 分鐘 |
| Hunyuan3D-2mini | 圖 → 3D | 40k | 頂點色（投影） | 無 | ~2 分鐘 |
| TripoSR + Blender 後處理 | AI + 自動後處理 | 20k | 2048 烘焙 | 19 骨 + Idle | < 1 分鐘 |
| TripoSR | 圖 → 3D | 68k–84k | 頂點色 | 無 | 25–50 秒 |

概念圖：LCM-Dreamshaper-v7（本機 CPU，~40 秒/張）。互動比較頁：`site/index.html`。
未測試（需帳號）：TRELLIS.2、Hunyuan3D-2.1、Stable Fast 3D、FLUX.1（需免費 HF token）、Tripo API（付費）。
