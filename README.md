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

## 日系動漫角色（原創，卡通渲染）

| 角色 | 定位 | 檔案 |
|---|---|---|
| 蒼嵐・ソラ（sora） | 風之弓手 | `assets/models/anime-blender/sora.glb` |
| 緋槍・カイ（kai） | 炎之槍士 | `assets/models/anime-blender/kai.glb` |

![ソラ](assets/renders/anime-blender/sora_studio_three_quarter.png) ![カイ](assets/renders/anime-blender/kai_studio_three_quarter.png)

程序化建模（`blender/build_anime.py`）：曲線髮束、大眼貼片、天使環髮光、緞帶與圍巾；
卡通渲染在即時 shader 端完成（三階色帶＋描邊＋輪廓光，見 `site/js/viewer.js` 的 `setShading('toon')`）。
技術筆記見 `docs/research.md` §5。

## 四種新風格（更精緻的程序化角色）

![四種風格](assets/renders/comparison_styles.png)

| 風格 | 角色（原創） | 腳本 | 重點 |
|---|---|---|---|
| Q版潮玩公仔 | 布丁、可可 | `blender/build_chibi.py` | 164／118 零件、6.5／4.7 萬面、層疊大眼、clearcoat 亮漆、眨眼 morph |
| 科幻機甲硬表面 | 鐵鷹 MK-II、夜梟 RX-9 | `blender/build_mecha.py` | 192／198 零件、切角裝甲＋面板線、活塞、手指、文字標記、斗篷、狙擊槍 |
| 體素藝術 | 方塊遊俠、方塊魔女 | `blender/build_voxel.py` | 27,847／32,505 體素（2 cm）、逐頂點體素 AO、免貼圖 |
| 水墨武俠 NPR | 墨白、青蓮 | `blender/build_ink.py` | 廣袖長袍／齊胸襦裙＋油紙傘、即時水墨 shader（墨色三階＋宣紙＋墨線） |

### 動作（所有角色共用動作庫＋各自招式）

![跑步與招式](assets/renders/stage_actions.png)

| 動作 | 說明 |
|---|---|
| Idle / Walk / Run / Jump / Wave / Hit | `blender/build_character.py` 的 `BASE_CLIPS`，每個程序化角色與 AI 後處理模型自動帶上 |
| 招式 | 鐵砧 Attack、翠羽 Cast、ソラ Shoot、カイ Thrust、布丁 Twirl、可可 Slash、鐵鷹 Aim、夜梟 Snipe、遊俠 Swing、魔女 Cast、墨白 Slash、青蓮 Dance |

### 次級動態（spring bones）

![有無物理對照](assets/renders/spring_bones_compare.png)

披風、裙襬、長髮、飄帶掛在骨鏈上，由 viewer 即時模擬（慣性＋回復力＋重力＋腿部膠囊碰撞），
任何動作都會帶動布料；`render.html?springs=0` 可關閉做對照。實作見 `blender/build_character.py`（`spring()`、
`radial_springs()`、`spring_weights()`）與 `site/js/viewer.js`（`SpringBones`）。

手臂動作以「自然下垂」撰寫，`key_rot()` 依骨架靜止姿勢換成世界軸 → A 字站姿的 Q版與 AI 模型也正確；
揮手會依「手臂長／頭長」自動調整（Q版頭大手短 → 側舉）。互動頁的競技場可切換「動作」。

### LOD（手機／遠景）

![LOD 對照](assets/renders/lod_compare.png)

`blender/make_lod.py` 逐零件減面（小零件保留、硬表面先平面溶解），每個角色有 LOD1（1.5 萬面）與 LOD2（約 6 千面），
骨架、動作、物理骨鏈都保留。

## 免費工具比較（全部本機 CPU、$0、不需帳號）

![比較](assets/renders/comparison_studio.png)

| 做法 | 類型 | 面數 | 貼圖 | 骨架 | 每隻耗時 |
|---|---|---|---|---|---|
| Blender + Python | 程序化建模 | 21k / 24k | 2048 烘焙 PBR | 19 骨 + 動畫 | 48–89 秒（建置） |
| Hunyuan3D-2mini + Blender 後處理 | AI + 自動後處理 | 20k | 2048 烘焙 | 19 骨 + Idle | ~2 分鐘 |
| Hunyuan3D-2mini | 圖 → 3D | 40k | 頂點色（投影） | 無 | ~2 分鐘 |
| TripoSR + Blender 後處理 | AI + 自動後處理 | 20k | 2048 烘焙 | 19 骨 + Idle | < 1 分鐘 |
| TripoSR | 圖 → 3D | 68k–84k | 頂點色 | 無 | 25–50 秒 |
| Shap-E（OpenAI） | 文 → 3D | 88k–102k | 頂點色 | 無 | 11–19 分鐘 |

概念圖：LCM-Dreamshaper-v7（本機 CPU，~40 秒/張）。互動比較頁：`site/index.html`（已發布為 claude.ai artifact，見 `docs/PROGRESS.md`）。
未測試（需帳號）：TRELLIS.2、Hunyuan3D-2.1、Stable Fast 3D、FLUX.1（需免費 HF token）、Tripo API（付費）。
