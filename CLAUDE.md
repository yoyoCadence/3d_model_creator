# CLAUDE.md — 給接手的 agent

本 repo 目標：用**免費工具**開發遊戲用 3D 角色（兩個角色：`anvil` 鐵砧・布蘭、`verdant` 翠羽・萊拉），
比較各工具效果，並用 HTML 頁面（`site/`）呈現「每個模型用什麼做的、效果如何」。

## 工作規則（使用者指定）
- **每完成一個段落就開 PR 並 merge 到 `main`**，然後繼續下一段；不必詢問使用者，除非真的必要。
- 開發分支：用該 session 指定的 `claude/...` 分支（每個 session 不同；merge 後從最新 `main` 繼續）。
- 進度與下一步一律更新在 `docs/PROGRESS.md`，讓任何 agent 能接手。
- 使用者**沒有 Tripo 付費會員**，不要再要 Tripo API key；用免費替代方案。
- 文件用繁體中文；程式碼註解英文即可。

## 環境安裝（雲端容器每次是新的）
```bash
apt-get install -y blender python3-numpy          # Blender 4.0.2（Ubuntu 套件，無 OIDN、Eevee 無法 headless）
python3 -m venv .venv && .venv/bin/pip install gradio_client trimesh pillow numpy   # 雲端 Space 用
.venv/bin/pip install torch torchvision einops omegaconf "transformers<5" huggingface_hub scikit-image pymcubes  # 本機 AI（CPU）
cd /tmp/web && npm i three@0.170.0                 # 截圖用（THREE_DIR=/tmp/web/node_modules/three）
```
網路是白名單制：Hugging Face、PyTorch、Steam、Poly Haven、Sketchfab 等已加入環境設定。
`download.pytorch.org` 會轉址到 `download-r2.pytorch.org`（未開放）→ torch 改從 PyPI 裝。

## 免費工具清單（本機 CPU、不需帳號）
| 工具 | 腳本 | 備註 |
|---|---|---|
| Blender 程序化 | `blender/build_character.py` | 含骨架/動畫/烘焙貼圖 |
| LCM-Dreamshaper（概念圖） | `tools/free_ai/lcm_concept_local.py` | ~40 秒/張 |
| TripoSR | `tools/free_ai/triposr_local.py` | 需 `TRIPOSR_DIR`（git clone VAST-AI-Research/TripoSR） |
| Hunyuan3D-2mini | `tools/free_ai/hunyuan3d_local.py` | 需 `HY3D_DIR`（git clone Tencent/Hunyuan3D-2）；吃 ~12 GB RAM |
| Shap-E（文生 3D） | `tools/free_ai/shap_e_local.py` | `pip install git+https://github.com/openai/shap-e` |
| AI 模型後處理 | `blender/postprocess_ai.py` | 減面 + UV + 高模→低模烘焙 + 骨架（`--pose` 用 ViTPose 關節） |
| 姿勢偵測 | `tools/free_ai/pose_keypoints.py` | ViTPose（Apache-2.0）→ `<char>_pose.json` |
| 動漫角色（程序化） | `blender/build_anime.py` | `--char sora|kai`；卡通渲染在 viewer（`setShading('toon')`） |
| LOD | `blender/make_lod.py` | `--tris 15000 --tex 1024`；硬表面加 `--planar 12 --smooth 35 --min-ratio 0.15` |
| 四種新風格（程序化） | `build_chibi.py`／`build_mecha.py`／`build_voxel.py`／`build_ink.py` | `--char pudding|cocoa`、`ironhawk|nightowl`、`cuberanger|witch`、`mobai|qinglian` |

使用者**拒絕提供** Tripo key 與 HF token → 雲端 HF Spaces（TRELLIS.2 等）不要再要，頁面上標為「未測試」。

## 常用指令
```bash
# 程序化角色（Blender，免費、可控、含骨架+動畫+烘焙貼圖）
blender -b --factory-startup -P blender/build_character.py -- --char anvil --out assets/models/blender/anvil.glb --tex 2048
# 截圖（three.js + headless Chromium，與 HTML 頁面同一套打光）
THREE_DIR=/tmp/web/node_modules/three node tools/render/shoot.mjs jobs.json
# 統一截圖（讀 site/data/tools.json，每個模型 5 張）＋ 頁面預覽
THREE_DIR=/tmp/web/node_modules/three python3 tools/render/render_all.py
THREE_DIR=/tmp/web/node_modules/three node tools/render/preview_page.mjs /tmp/out
```
HTML 比較頁：`site/index.html`（artifact 片段，無 doctype）＋ `site/js/viewer.js` ＋ `site/data/tools.json`。
已發布：https://claude.ai/artifact/6mBLUeDnbfMsJm5KmeanMH（更新時傳這個 `url`，不要另開新的）。
Artifact 不提供 `.glb` → 先產生 base64 文字檔，再把 `assets/.../x.glb.b64.txt` 以相同路徑放進 `files`：
```bash
python3 -c "import base64,glob;[open(g+'.b64.txt','w').write(base64.b64encode(open(g,'rb').read()).decode()) for g in glob.glob('assets/arena/*.glb')+glob.glob('assets/models/*/*.glb') if not g.endswith('_raw.glb')]"
```

## 結構
- `config/characters.json` — 角色設定（配色、形狀語言、AI 提示詞）
- `blender/` — Blender 程序化建模/烘焙/匯出腳本
- `tools/free_ai/` — 免費 AI 工具管線（HF Spaces、TripoSR、Hunyuan3D 本機 CPU）
- `tools/render/` — 統一截圖工具
- `site/` — HTML 比較頁（`site/js/viewer.js` 是共用 three.js viewer，含打光預設）
- `assets/models/<tool>/<char>.glb`、`assets/renders/<tool>/`、`results/runs.json`（每次生成的耗時/面數紀錄）

## 動作
所有配方經 `bc.with_base_clips()` 自動帶 Idle/Walk/Run/Jump/Wave/Hit；手臂動作以「手臂自然下垂」撰寫，
`key_rot()` 會依骨架靜止姿勢換成世界軸（A 字站姿也正確）。`render.html?clip=Walk&t=0.5` 的 t 單位是秒。
招式函式加 `@bc.hit(影格)` 標註命中時間 → 建置時寫進 GLB `animations[].extras.hit`（`set_clip_extras()`），viewer 對打用它觸發受擊。

## 已知陷阱
- Blender：設定 `obj.scale/location` 後要 `view_layer.update()` 才能用 `matrix_world`。
- Blender 4.0 Ubuntu 版沒有 OIDN → `scene.cycles.use_denoising = False`，否則 bake 全黑。
- HF ZeroGPU 匿名額度很快用完（`exceeded your ZeroGPU runs limit`）→ 需要免費 HF token。
