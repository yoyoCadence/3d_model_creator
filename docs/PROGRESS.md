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

## 進行中 / 下一步
1. **免費 AI 工具**（`tools/free_ai/`）
   - [ ] 概念圖：FLUX.1-schnell Space（匿名額度已滿）→ 改用本機 CPU 文生圖或請使用者給免費 HF token
   - [ ] TripoSR（MIT，本機 CPU）image→3D
   - [ ] Hunyuan3D-2mini（本機 CPU，只做形狀）
   - [ ] TRELLIS.2 / Hunyuan3D-2.1 / SF3D（HF Spaces，需 HF token 才有 GPU 額度）
2. 研究文件 `docs/research.md`：參考遊戲質感、競技場場地參考、打光與建模技術
3. 競技場場景（Blender）+ 打光研究（studio / sunset / night / flat）
4. HTML 比較頁（`site/index.html`）→ 發布 artifact
5. Blender 角色 v2：2048 貼圖、high→low 法線烘焙、臉部細節、兜帽造型

## 決策紀錄
- 使用者無 Tripo 會員 → 全部改免費工具（2026-11-18）
- 預覽渲染用 three.js（接近遊戲引擎即時效果），Cycles 只用於烘焙
