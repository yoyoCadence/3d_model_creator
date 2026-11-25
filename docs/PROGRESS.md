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
4. [x] 段落 13：水墨武俠 NPR「墨白」＋水墨 shader（`blender/build_ink.py`、viewer `setShading('ink')`）— 68 零件、47,776 tris；shader：亮度→三階墨色、只保留真正的紅（smoothstep 0.25–0.4）、宣紙顆粒、粗墨線
5. [x] 段落 14：頁面整合（八個角色、十一種做法、競技場「四種新風格」角色組）→ artifact 第 5 版（89 MB，分兩批 publish）

6. [x] 段落 15：AI 模型骨架改用姿勢偵測 — `tools/free_ai/pose_keypoints.py`（ViTPose，平均信心 0.89–0.96）→
   `postprocess_ai.py --pose`：2D 關節投到 3D（深度取周圍頂點截面中心），低信心點回退模板；新增 ArmsUp 測試動作
   對照圖 `assets/renders/rig_template_vs_pose.png`（模板骨架抬手會扭曲，姿勢偵測後手臂與武器正確跟隨）

使用者新需求（2026-11-25）：**每種風格 2 個角色**＋**基本動作要能看出效果**
7. [x] 段落 16：共用動作庫＋Q版第二角色「可可」
   - `build_character.py`：`BASE_CLIPS` = Walk(24f 循環)/Run(16f)/Jump(40f，含蹲、起跳、滯空收腿、落地緩衝)/Wave/Hit；
     `with_base_clips(actions)` 讓每個配方自動帶上，角色專屬動作（Attack/Cast/Twirl/Slash…）照舊保留
   - **手臂軸向修正**：A 字站姿（Q版、AI 模型）手臂的 roll-0 座標是斜的 → 大角度擺臂會穿過身體。
     做法：手臂骨 `align_roll(+Y)`，並在 `key_rot()` 把手臂旋轉以「世界軸」重新表達（以靜止姿勢共軛、改用四元數），
     動作只要依「手臂自然下垂」來寫，任何站姿都正確
   - Wave 依「手臂長／頭長」自動調整：Q版頭大手短，高舉會把手藏進頭裡 → 改成側舉
   - 可可（`build_chibi.py` 的 `recipe_cocoa`）：118 零件、46,612 tris；臉部抽成 `chibi_head_face()` 與布丁共用
   - 時間單位：`render.html?clip=Jump&t=0.83` 的 t 是**秒**（24 fps），不是比例

接下來（每項一個 PR）：
8. [x] 段落 17：機甲第二角色「夜梟 RX-9」（`build_mecha.py` 的 `recipe_nightowl`）— 198 零件、44,504 tris
   - 貓頭鷹頭盔（雙光學鏡＋臉盤環＋耳羽）、V 形胸甲、折疊羽翼刃（每側 5 片）、破邊斗篷 `cloak()`、爪足 `talon()`、長狙擊槍
   - 專屬動作 Snipe：蹲低→舉槍瞄準→後座力→收槍；`oriented(dir, hint)` 讓薄片零件的薄軸朝指定方向
   - 陷阱：`make_mat(edge=…)` 的曲率高光用 SCREEN 混色，pointiness 是逐頂點 → 大平面整片變亮，深色塗裝會褪成灰；深色要把 edge 降到 ≤0.07
   - 鐵鷹同步重建（帶共用動作），Aim 角度依新手臂軸向調整
9. [x] 段落 18：體素第二角色「方塊魔女」— `build_voxel.py` 改成多角色（`CHARS` 表、`--char cuberanger|witch`、每角色 joints/palette/design/clips/發光色）
   - 32,505 體素、29,592 tris：彎尖帽（金星點、紅帶＋金扣）、喇叭袖、交叉綁帶馬甲、鋸齒裙襬＋金星、條紋襪、尖翹靴、斗篷高領、
     長髮＋紅緞帶、掃帚、螢光綠藥水（自發光）、肩上黑貓；專屬動作 Cast（舉藥水搖晃）
   - 技巧：**裙子下半部依 x 正負分給左右大腿骨** → 走路時腿不會穿出硬裙（遊戲常用作法）
10. [x] 段落 19：水墨第二角色「青蓮」（`build_ink.py` 的 `recipe_qinglian`）— 143 零件、54,800 tris
   - 齊胸襦裙（內外兩層＋前開衩）、紅腰帶＋長垂帶、披帛（背後垂掛＋兩肘垂下）、廣袖、高髻＋玉簪＋蓮花步搖、花鈿、玉耳墜
   - `umbrella()` 油紙傘（交替傘面、16 傘骨＋撐骨、紅傘緣、傘穗）、`lotus()` 兩層花瓣紅蓮
   - 專屬動作 Dance（張袖旋身一圈）；`bc.wave_keys(arm, side="L")` 可改用左手揮（右手撐傘）
   - 墨白同步重建（帶共用動作）
11. [x] 段落 20：全部角色重建（翠羽、ソラ、カイ＋AI 後處理 6 隻 `--pose`）都帶共用動作；頁面：
    - 競技場新增「動作」切換（待機/走/跑/跳/揮手/受擊/招式），`viewer.playCastClip()` 交叉淡入；「招式」= 各角色非共用的動作
    - 角色組：奇幻、動漫、Q版、機甲、體素、水墨（各兩隻）＋「四種新風格 全員」八人金字塔站位；每組可設 `cam: [目標高度, 距離]`
    - 競技場畫面改成撐滿右側面板高度（手機仍 16:10）；標題/介紹改為十二個角色
    - 新圖：`assets/renders/comparison_styles.png`（八人）、`assets/renders/stage_actions.png`（跑步＋招式）
12. [ ] artifact 重新發布（同一 URL，>64 MB 分批）

待辦（暫緩）：
- 動漫角色 v2：眨眼 morph、臉部法線編輯、髮束物理；比較頁縮圖

## 決策紀錄
- 使用者無 Tripo 會員 → 全部改免費工具（2026-11-18）
- 預覽渲染用 three.js（接近遊戲引擎即時效果），Cycles 只用於烘焙
