# 進度 / 交接（PROGRESS）

> 每個段落完成 → 更新本檔 → 開 PR → merge。接手者從「下一步」開始。

## 已完成
- [x] 段落 1：專案骨架、角色設定（`config/characters.json`、`docs/character_design.md`）
- [x] 段落 1：**Blender 程序化角色 v1**（兩隻皆完成）
  - Skin modifier 身體 + 原件組裝的盔甲/武器 → 單一 mesh、單一材質
  - 19 骨骼 armature、身體自動權重、配件剛性權重；動畫 `Idle` + `Attack`/`Cast`
  - Smart UV + Cycles 烘焙：BaseColor（含 AO）、ORM、Emissive，GLB 匯出
  - anvil：21,352 tris；verdant：23,932 tris（1024 貼圖）
- [x] 共用 three.js viewer（`site/js/viewer.js`）+ headless 截圖工具（`tools/render/shoot.mjs`）

- [x] 段落 2：研究文件 `docs/research.md`（參考遊戲質感、競技場、打光、建模管線，附來源）
- [x] 段落 2：競技場 `blender/build_arena.py` → `assets/arena/arena.glb`（14.6k tris、10 材質 = 10 draw calls）
  - `site/scene.html` + viewer scene mode：黃昏 / 夜間火盆（4 盞點光源）/ studio；截圖在 `assets/renders/arena/`
- [x] 段落 2：免費 AI 概念圖（本機 CPU）— LCM-Dreamshaper-v7（MIT），每張 ~40 秒
  - 採用：`anvil_lcm_s12.png`、`verdant_lcm_s13.png`（提示詞在 `config/characters.json` 的 `sd_prompt`）
  - 注意：Dreamshaper 對女性角色容易生成暴露服裝，提示詞需寫明 `fully clothed`、`long sleeve tunic`
- [x] 段落 2：TripoSR（MIT，本機 CPU）兩隻完成：anvil 84,492 tris / verdant 67,948 tris，各 25–50 秒
  - torchmcubes 用 PyMCubes shim 取代；輸出需旋轉 180° 才面向 glTF +Z（已寫進腳本）

- [x] 段落 3：Hunyuan3D-2mini 本機 CPU 兩隻完成（raw 29 萬/26 萬面 → 4 萬面，各 ~130 秒，吃 ~12 GB RAM）
  - CPU 版無貼圖 → 我們從概念圖正面投影頂點色（頁面有標註）
  - 需 `apt-get install libopengl0`（pymeshlab 讀 PLY 需要）
- [x] 段落 3：AI 後處理 `blender/postprocess_ai.py`（Hunyuan / TripoSR 各兩隻）：2 萬面、2048 高模→低模烘焙、模板 19 骨、Idle
  - 陷阱：要 `customdata_custom_splitnormals_clear` + `validate()` + `normals_make_consistent`，否則光照出現三角碎斑
- [x] 段落 3：顏色修正 — AI 頂點色是 sRGB，glTF COLOR_0 是線性 → `srgb_u8_to_linear_u8`；
  trimesh 匯出無材質 → three.js 預設為金屬 → `add_default_material`
- [x] 段落 3：Blender 角色貼圖升級到 2048；`render_all.py` 統一截圖（每模型 5 張）；`assets/renders/comparison_studio.png`
- [x] 段落 3：HTML 比較頁 `site/index.html`（競技場打光台、總覽表、工具卡、3D 檢查台、未測試清單）
- 使用者拒絕提供 HF token → TRELLIS.2 / Hunyuan3D-2.1 / SF3D / FLUX 標為未測試

- [x] 段落 4：Shap-E（OpenAI，MIT，文生 3D）兩隻完成：88k / 102k tris，CPU 19 / 11 分鐘；品質最差（只剩輪廓）
  - 權重快取在 `tools/free_ai/shap_e_model_cache/`（~4 GB，已 gitignore — 不要 commit，會讓 push 失敗）

- [x] 段落 5：HTML 比較頁已發布 → https://claude.ai/artifact/6mBLUeDnbfMsJm5KmeanMH（私人，需由擁有者分享）
  - Artifact 不提供 .glb → 模型以 base64 文字 `<name>.glb.b64.txt` 發布，`viewer.js` 的 `loadGLTF()` 先試 .b64.txt 再退回 .glb
  - 重新發布：`python3 -c "..."` 產生 *.b64.txt（見 CLAUDE.md），用同一個 artifact URL 更新

- [x] 段落 6：Blender 角色 v2（`assets/renders/blender_v1_vs_v2.png`）
  - 程序化 bump（布紋、錘紋金屬、皮革、木紋、髮絲）→ 烘焙成 tangent-space 法線貼圖，不增加面數
  - 卡通眼（眼白 + 虹膜 + 高光）、翠羽加嘴巴與披肩（capelet）、鐵砧肩甲鉚釘；金屬度 1.0 → 0.9
  - 匯出前三角化（tangent 需要）＋ 貼圖改 JPEG 90（GLB 從 6 MB 降到 2.7–3.1 MB）
  - 已知小問題：翠羽背面頸部仍有小缺口
  - 陷阱：本機殘留的 `*.glb.b64.txt` 會蓋掉新模型 → `loadGLTF()` 改成先讀 .glb、失敗才讀 .b64.txt

- [x] 段落 7：**日系動漫角色 ×2（原創，Blender 程序化）**：蒼嵐・ソラ（風之弓手）、緋槍・カイ（炎之槍士）
  - `blender/build_anime.py`：NURBS 曲線髮束、大眼貼片（眼白/虹膜/瞳孔/雙高光/眼線/眉）、窄下巴、緞帶/圍巾、弓/長槍
  - 風格設定 `bc.STYLE`：平塗色、AO 只留 12%、不烘法線；`bc.RECIPES` 可由其他模組擴充
  - viewer 卡通渲染：MeshToonMaterial 三階色帶 + OutlineEffect 描邊 + fresnel 輪廓光 + Neutral tone mapping
  - 頁面：四個角色、競技場「角色組」切換、檢查台 PBR／卡通渲染切換、總覽表改成範圍顯示；修正手機寬度溢出

- [x] 段落 8：動漫組 AI 路線（LCM 概念圖 → Hunyuan3D-2mini → Blender 後處理，卡通渲染顯示）
  - 概念圖：`sora_lcm_s23.png`、`kai_lcm_s22.png`；Hunyuan raw 17 萬／22 萬面 → 4 萬 → 2 萬，各約 3.5 分鐘
  - 投影上色改良（4 隻 Hunyuan 模型都受惠）：透明邊緣以最近不透明像素補色、正面 z-buffer 判斷可見性、
    不可見頂點由鄰點擴散上色 → 修正側面黑塊與「第二張臉」；`tools/free_ai/reproject_colors.py` 不需重跑生成
  - 動漫頭髮「天使環」高光（烘進 albedo）；`tools/render/publish_files.py` 自動產生 artifact 檔案清單
  - `tools.json` 的模型可各自指定 `shading: toon`

- [x] 段落 9：比較頁重新發布（第 3 版，同一 URL）：四個角色、七種做法；檔案 68 MB → 分兩批 publish
  （第 1 批：頁面＋資料＋模型＋縮圖 60 MB；第 2 批：16 張概念圖 8 MB）；發布後刪除本機 *.b64.txt

## 進行中 / 下一步
使用者新需求（2026-11-25）：再加 **4 組不同風格、比現有更精緻** 的模型（每種風格 1 個原創角色，每段一個 PR）
1. [x] 段落 10：Q版潮玩公仔風「布丁」（`blender/build_chibi.py`）— 164 零件、64,988 tris、clearcoat、Blink morph（`bc.tag_blink`）
2. [x] 段落 11：科幻機甲硬表面「鐵鷹 MK-II」（`blender/build_mecha.py`）— 192 零件、36k tris；陷阱：`to_mesh()` 會把 material_index 夾到 0，要在 `set_mat` 之後才設定內嵌面材質
3. [x] 段落 12：體素藝術「方塊遊俠」（`blender/build_voxel.py`）— 27,847 體素（2 cm）、22k tris、頂點 AO；陷阱：盒子邊界剛好落在體素中心會因浮點誤差漏掉，邊界要留餘量
4. [ ] 段落 13：水墨武俠 NPR「墨白」＋水墨 shader（`blender/build_ink.py`、viewer `setShading('ink')`）
5. [ ] 頁面整合四種新風格 → 重新發布 artifact

待辦（暫緩）：
- AI 模型骨架改用姿勢偵測（ViTPose `usyd-community/vitpose-base-simple`，Apache-2.0，已下載到 HF cache）
- 動漫角色 v2：眨眼 morph、臉部法線編輯、髮束物理；比較頁縮圖

## 決策紀錄
- 使用者無 Tripo 會員 → 全部改免費工具（2026-11-18）
- 預覽渲染用 three.js（接近遊戲引擎即時效果），Cycles 只用於烘焙
