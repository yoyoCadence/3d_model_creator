# 角色設計 — 餘燼遺跡競技場（Ember Ruins Arena）

**遊戲假設**：第三人稱、風格化奇幻競技場動作遊戲。美術方向為 **Stylized PBR**：
手繪感配色（低頻色塊變化、上亮下暗漸層、金屬邊緣高光），但粗糙度/金屬度維持物理正確，
這樣在任何引擎打光下都穩定。比例約 5 頭身的英雄比例，剪影清楚，遠距離也認得出。

兩個角色刻意做成**對比**：形狀語言（方 vs 三角）、配色（暖紅/鋼 vs 冷綠/金）、重量感（重 vs 輕）。

| | 鐵砧・布蘭（anvil） | 翠羽・萊拉（verdant） |
|---|---|---|
| 定位 | 重裝先鋒／坦克 | 秘法遊俠／敏捷法師 |
| 形狀語言 | 方形、上重下輕：大圓肩甲、寬胸甲、粗短四肢 | 三角形、細長：尖兜帽、A 字披風、長法杖 |
| 主色 | 深紅 `#9A2B2B` + 鋼 `#9EA7B2` | 翡翠綠 `#1F6F5C` + 皮革 `#6B4A2F` |
| 點綴色 | 黃銅 `#C9A045` | 金 `#D8B45A`、發光青 `#5FF2E6` |
| 剪影辨識點 | 圓盾、靠在地上的戰錘、頭盔紅冠 | 法杖頂端的新月環＋發光水晶、兜帽 |
| 材質對比 | 金屬（低粗糙）vs 布料（高粗糙） | 布料 vs 皮革 vs 自發光 |
| 動畫 | Idle、Attack（錘擊） | Idle、Cast（舉杖施法） |

## 技術規格（目標）
- 三角面：每角色 15k–30k tris（第三人稱主角等級；手機版可用 Decimate 做 LOD1 ~8k）
- 單一材質、單一貼圖組（BaseColor / ORM / Emissive）→ 1 draw call
- 骨架：19 骨（hips→spine→chest→neck→head；四肢各 3–4 節），命名 `.L/.R`，可對應 Mixamo/Unity Humanoid
- 尺寸：公尺制，腳底在原點，正面朝 glTF +Z
- 格式：`.glb`（含骨架、動畫、貼圖）

## AI 提示詞
見 `config/characters.json` 的 `flux_prompt`。重點：
`full body, A-pose, front view, symmetrical, plain white background, no ground shadow`
— 這是 image-to-3D 模型最喜歡的輸入（正面、對稱、白底、四肢不遮擋）。
