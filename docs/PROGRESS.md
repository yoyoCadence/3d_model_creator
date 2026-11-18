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

## 進行中 / 下一步
1. [ ] Hunyuan3D-2mini 本機 CPU（`tools/free_ai/hunyuan3d_local.py`；fp16→fp32 已修）
2. [ ] TRELLIS.2 / Hunyuan3D-2.1 / SF3D（`tools/free_ai/hf_spaces_3d.py`；匿名 ZeroGPU 額度已滿 → 需免費 HF token）
3. [ ] 統一截圖：每個工具 × 角色 × 打光預設（`tools/render/shoot.mjs`）
4. [ ] HTML 比較頁（`site/index.html`）→ 發布 artifact
5. [ ] Blender 角色 v2：2048 貼圖、high→low 法線烘焙、臉部細節、兜帽造型

## 決策紀錄
- 使用者無 Tripo 會員 → 全部改免費工具（2026-11-18）
- 預覽渲染用 three.js（接近遊戲引擎即時效果），Cycles 只用於烘焙
