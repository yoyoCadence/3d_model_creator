# 研究筆記：參考質感、場地、打光與建模技術

> 目的：替「餘燼遺跡競技場」的兩個角色訂出質感目標與技術規格。
> 參考圖取自 Steam 商店頁截圖（版權屬各遊戲公司，僅連結不轉載）。

## 1. 參考遊戲：角色質感

| 遊戲 | 看什麼 | 我們採用的做法 |
|---|---|---|
| [Torchlight III](https://store.steampowered.com/app/1030210) | 粗壯誇張比例（大手、大肩）、手繪感 albedo、暖色主光＋冷色陰影 | 鐵砧的大圓肩甲／粗四肢；albedo 內含上亮下暗漸層 |
| [Marvel Rivals](https://store.steampowered.com/app/2767030) | 漫畫感 Stylized PBR：強逆光／輪廓光、夕陽暖逆光（Thanos 截圖）、材質細節少但色塊乾淨 | 打光預設「競技場黃昏」用低角度逆光做 rim |
| [SMITE 2](https://store.steampowered.com/app/2437170) | UE5 高精度風格化：金色飾邊、武器自發光、飽和配色、大型剪影武器 | 黃銅/金飾邊（solidify rim 材質）、翠羽的發光水晶 |
| [Kena: Bridge of Spirits](https://store.steampowered.com/app/1954200) | 動畫電影感：柔和 GI、體積光、布料層次；主角拿**發光藍水晶法杖**（與翠羽同構想） | 翠羽的配色與發光點做視覺焦點 |
| [Overwatch 2](https://store.steampowered.com/app/2357570) / [Sea of Thieves](https://store.steampowered.com/app/1172620) | 遠距離可讀性：大色塊、低頻細節、剪影優先 | 每角色 ≤ 3 主色、1 個點綴色 |

**質感重點（整理自截圖觀察與 80.lv / Polycount 作者分享）**
- 風格化 ≠ 不用 PBR：主流做法是「PBR 打底，手繪疊上去」——先有正確的粗糙度/金屬度，再在 albedo 畫光影與色彩變化。[^velan][^junkrat]
- 風格化金屬常故意不物理：金屬度 0.75–0.9、粗糙度 0.25–0.5，讓 albedo 顏色不會被反射吃掉。[^lisbon][^junkrat]
  → 我們 v1 的鋼用 metal 1.0 / rough 0.42，在 Studio 光下仍偏鏡面，v2 可降到 metal 0.85。
- 細節頻率要低：大面積留白、邊緣高光（edge wear）與凹處 AO 比高頻紋理更重要。

## 2. 場地參考：競技場

觀察 SMITE 2、Marvel Rivals、Torchlight III 的競技/戰鬥場：
- **圓形石板地面**，中央低對比（戰鬥可讀性），外圈用花紋／高差區隔邊界。[^topdown]
- **垂直地標**：斷柱、拱門、旗幟、火盆 — 給玩家方位感，也是燈光來源。
- **光的敘事**：黃昏暖光（金色砂岩反光）＋火盆火光；夜間版只靠火把，形成冷暖對比。[^coliseum]
- 背景遠景用霧與大氣透視降對比，角色永遠比背景亮/飽和。

→ `site/js/viewer.js` 的地面為低飽和石灰色＋外圈金屬環；打光預設 `sunset`、`night` 對應這兩種氛圍。

## 3. 打光技術

### 3.1 三點打光（角色展示/選角畫面）
- **Key 主光**：最強，45° 側上方；**Fill 補光**：在另一側 60–90°，強度約主光 20–30%（戲劇）～50–70%（自然）；**Rim 輪廓光**：在背後，把角色從背景切出來。[^unity3pt][^cb][^stray]
- 強度順序 Key > Fill > Rim 是 Unity 官方教學的建議；風格化遊戲常把 Rim 拉得比教科書更強（Marvel Rivals 風格）。
- 冷暖對比：Key 暖（~4500K）、Fill 冷（天空色）→ 立體感來自色溫差而非只有明暗。

我們的 `studio` 預設：Key 2.6（暖白）／Fill 0.7（冷藍，≈27%）／Rim 3.2（白）＋半球光 0.35。

### 3.2 遊戲內光照
- **Unreal**：Directional（主光）＋ Sky Light（補光）；Rect Light 放角色背後做 rim。**Unity**：Directional ＋ 烘焙 GI/環境光當補光、Spot 做 rim（最省效能）。[^gamine][^epic]
- **IBL / HDRI 環境光**：金屬一定要有環境反射才好看 → viewer 使用 PMREM 環境貼圖；可換 Poly Haven CC0 HDRI。
- **Tone mapping**：ACES Filmic（viewer 預設），避免自發光與高光爆白。
- **陰影**：Directional shadow 要調 bias/normalBias 防止 shadow acne；火把用 Point light ＋ 衰減 ＋ 閃爍。

### 3.3 四種打光預設（用來比較所有工具的產出）
| 預設 | 用途 | 檢查重點 |
|---|---|---|
| `flat` 平光 | 看貼圖/albedo 本身 | 色塊、接縫、AI 貼圖是否把光影「畫死」在貼圖裡 |
| `studio` 三點 | 角色展示 | 形體、輪廓、金屬感 |
| `sunset` 黃昏逆光 | 競技場白天 | 剪影可讀性、rim |
| `night` 火把 | 夜戰 | 自發光、點光衰減下的材質 |

## 4. 3D 建模技術（遊戲角色管線）

```
概念圖 → Blockout → 高模雕刻 → 重拓撲(Retopo) → UV → 烘焙(法線/AO) → 貼圖 → 骨架/蒙皮 → 動畫 → LOD → 引擎
```
- **面數預算**：第三人稱主角 PC/主機約 15k–50k tris、手機 1.5k–5k（hero 可到 20k–40k）；過場特寫另做高 LOD。[^neural][^ue]
  → 本專案目標 15k–30k，Blender v1 為 21k / 24k。
- **貼圖**：單一材質＋一組貼圖（BaseColor / ORM / Emissive）= 1 draw call；UV 注意 texel density 一致。
- **骨架**：命名一致（`.L/.R`），可重定向到 Mixamo / Unity Humanoid / UE Mannequin。
- **AI 生成模型的後處理**（重要！AI 輸出通常不是 game-ready）：
  1. 三角面很多且雜亂（10 萬～百萬）→ Decimate 或 Quad Remesh（Blender 內建 / Instant Meshes 免費）
  2. 貼圖常把光影烤死 → 用 `flat` 預設檢查，必要時重新烘焙
  3. 沒有骨架 → Blender 自動權重 / Mixamo（免費，需 Adobe 帳號）/ AccuRIG（免費）
  4. 武器與手黏在一起 → 需手動切開才能換武器或做動畫
- **給 AI 的輸入圖**：全身、A-pose、正面、對稱、白底、無地面陰影、四肢不遮擋 → 重建最穩。

## 5. 日系動漫（卡通渲染）角色技術

> 目標是「原神類」的日系卡通渲染美術風格，角色全部原創，不仿製任何既有角色。

| 技術 | 做什麼 | 本專案做法 | 引擎中的免費選項 |
|---|---|---|---|
| **色帶（Cel shading）** | 把光照壓成 2–3 階硬邊色塊 | `MeshToonMaterial` + 3 階 ramp（`viewer.js`） | Unity Toon Shader（UTS3，Unity 官方套件）[^uts]、開源 URP toon shader[^urptoon] |
| **描邊（Inverted hull）** | 沿法線放大的背面網格畫成深色輪廓 | three.js `OutlineEffect`（厚度 0.0035、深棕紫色） | UTS Outline + Outline Width Map 控制臉部線寬[^utsoutline]；烘焙平滑法線避免描邊斷裂[^urpex] |
| **輪廓光（Rim light）** | 邊緣補一圈亮色，讓暗色衣服也分得出剪影 | fresnel 項加在光照之後 | UTS Rim Light |
| **臉部陰影（SDF face shadow）** | 臉不用法線算陰影，改用預先畫好的 SDF 圖決定陰影線，避免臉上出現破碎陰影 | 尚未實作（目前臉部用平塗＋極弱 AO） | 社群 Genshin 風 URP shader 支援 SDF 臉影[^genshinurp]；SDF 圖生成流程[^sdf] |
| **髮絲高光（天使環）** | 頭髮上一圈固定位置的高光 | 尚未實作 | UTS MatCap 讓頭髮更有立體感[^uts] |
| **貼圖** | 平塗色、少量漸層、不靠法線貼圖 | `STYLE`：AO 只留 12%、不烘法線 | 一般再加「陰影色貼圖」（1st Shading Map）手動指定暗部色[^uts] |

**建模上的動漫特徵**：大頭小臉（6.5–7 頭身）、窄下巴、大眼（眼白＋虹膜＋瞳孔＋兩個高光＋粗上眼線）、
髮型由一束一束漸細的髮束組成（瀏海、側髮、呆毛），配件（緞帶、圍巾、披帛）製造飄動感。

## 來源
[^velan]: [Tip of the Brush: Creating Stylized Art in a PBR World — Velan Studios](https://medium.com/velan-studios/tip-of-the-brush-creating-stylized-art-in-a-pbr-world-b803b91c082f)
[^junkrat]: [Hand-painted Overwatch Junkrat's RV production — 80.lv](https://80.lv/articles/001agt-002mrs-hand-painted-overwatch-junkrats-rv-production)
[^lisbon]: [Creating an Overwatch-inspired environment: Lisbon Streets](https://gamesartist.co.uk/creating-an-overwatch-inspired-environment-lisbon-streets-georg-klein/)
[^topdown]: [Top-down fantasy arena backdrop（低對比可讀性）](https://www.summerengine.com/asset-store/top-down-fantasy-arena-backdrop-c9fb4ad6)
[^coliseum]: [Ancient Ruined Colosseum（暖金色調）](https://www.summerengine.com/asset-store/ancient-ruined-colosseum-46a2370d.md)
[^unity3pt]: [Unity Learn — Showcase your work with lighting](https://learn.unity.com/tutorial/showcase-your-work-with-lighting.md?language=en)
[^cb]: [How to use key, fill and rim lighting in 3D art — Creative Bloq](https://www.creativebloq.com/3d/how-to-use-key-fill-and-rim-lighting-in-3d-art)
[^stray]: [Lighting Is Storytelling — Strayspark](https://www.strayspark.studio/blog/cinematic-lighting-design-ue5)
[^gamine]: [Game lighting design — GamineAI](https://gamineai.com/blog/game-lighting-design-creating-atmosphere-and-mood-in-your-games)
[^epic]: [Lighting and color in UEFN — Epic Games](https://dev.epicgames.com/documentation/en-us/fortnite/making-cinematics-2-lighting-and-color-in-unreal-editor-for-fortnite)
[^neural]: [Polygon count guide for 3D game assets — Neural4D](https://blog.neural4d.com/user-guide/polygon-count-for-3d-game-assets/)
[^ue]: [Polygon count on 3rd person player characters — Unreal forums](https://forums.unrealengine.com/t/polygon-count-on-3rd-person-player-characters/125244)
[^uts]: [Unity Toon Shader — Getting started](https://docs.unity3d.com/Packages/com.unity.toonshader@0.13/manual/GettingStarted.html)
[^utsoutline]: [Unity Toon Shader — Outline](https://docs.unity3d.com/Packages/com.unity.toonshader@0.13/manual/Outline.html)
[^urptoon]: [delt06/urp-toon-shader（GitHub）](https://github.com/delt06/urp-toon-shader)
[^urpex]: [UnityURPToonLitShaderExample（GitHub）](https://www.github.com/tehyy/UnityURPToonLitShaderExample)
[^genshinurp]: [NoiRC256/URPSimpleGenshinShaders（GitHub）](https://github.com/NoiRC256/URPSimpleGenshinShaders)
[^sdf]: [Anime Shading Plus — Face shadow map creation and baking](https://erichu33.github.io/ASPDocs/en/articles/face-shadow-map-creation-and-baking-workflow.html)
