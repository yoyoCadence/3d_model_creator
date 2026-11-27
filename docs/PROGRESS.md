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
12. [x] 段落 21：artifact 第 9 版（同一 URL）：72 個檔案、114.5 MB → 分三批 publish（模型 54 MB／模型＋概念圖 58 MB／縮圖 2 MB），發布後刪除本機 *.b64.txt

使用者（2026-11-25）：「繼續下一步、不要停」→ 依建議清單往下做
13. [x] 段落 22：**次級動態（spring bones）**— 披風、裙襬、長髮、飄帶在走/跑/跳時依物理甩動
    - Blender：`bc.spring(name, pts, parent)`／`bc.radial_springs(...)` 註冊骨鏈；零件的骨名寫 `"spring:a,b"` →
      `spring_weights()`：取最近兩條鏈（距離平方反比）＋沿鏈的帽形權重，鏈根以上留在父骨。鏈骨 `spring_<類型><id>_<i>`，
      結尾 `_end`（不變形）；類型前綴 = viewer 預設（hair／cloth／skirt）
    - 碰撞體：軀幹球 `col_<骨>_<半徑mm>`、四肢膠囊 `cap_<骨>_<半徑mm>`＋`_end`，半徑取自身體半徑 R × `bc.COLLIDER`（機甲放大）
    - 身體自動權重時暫時關閉鏈骨 deform（避免身體被鏈骨拉走）
    - viewer：`SpringBones`（VRM 式 verlet：慣性×(1−drag)＋回復力＋重力，長度約束、碰撞推出），60 Hz 固定步長；
      `viewer.seek(t)` 讓截圖也能模擬到指定時間；`render.html?springs=0` 可關閉做前後對照
    - 套用：青蓮（裙 12×4 鏈、髮、腰帶、披帛）、墨白（長袍、馬尾、髮帶、圍巾、腰帶）、夜梟（斗篷 5 鏈）、可可（披風）、
      布丁（雙馬尾、三層裙）、翠羽（斗篷、裙）、鐵砧（前後戰袍）、ソラ（髮帶、裙、圍巾）、カイ（馬尾、長外套下襬、腰帶）
    - 經驗：裙子 8 條鏈太稀、球形碰撞擋不住 → 12×4 鏈＋腿部膠囊碰撞後才不穿模
    - 未做：體素魔女（每個體素剛性綁骨，彎曲會裂開）

14. [x] 段落 23：**LOD（細節層級）**— `blender/make_lod.py`：10 個程序化角色各出 LOD1（15k 面＋1024 貼圖）、LOD2（6k 面＋512 貼圖）
    - 匯入 GLB 時 `merge_vertices=True`（否則 UV 接縫把模型拆成上千塊、接縫變成減面邊界）
    - **逐零件減面**：≤64 面的小零件不動（細杖、珠子不會被塌掉）、大零件共用剩餘預算（二分搜尋比例）但至少保留 8%（機甲 15%），
      預算仍不夠時從最小零件（< 身高 2%）開始捨棄
    - 機甲（硬表面）先做**平面溶解** `--planar 12` 再塌縮；減面後清除自訂法線改用自動平滑（否則出現黑色污斑）
    - 骨架、動作、物理骨鏈全部保留（LOD 一樣有 spring bones）；Blink morph 在 LOD 移除
    - 結果：一般角色 LOD2 ≈ 6k；機甲 LOD2 ≈ 9.4k–10k（零件太多，誠實標示）；檔案 0.8–1.3 MB
    - 頁面：檢查台新增 LOD0/1/2 切換（`tools.json` 的 `lods`），骨骼顯示「19 ＋ N 物理」；對照圖 `assets/renders/lod_compare.png`

15. [x] 段落 24：**動漫臉部陰影（SDF 式，程序化）**— 卡通渲染下臉部不再有法線造成的碎斑
    - Blender：`bc.tag_face(head)`（`anime_head()`、`chibi_head_face()` 自動標記）→ 合併後轉成 `_FACEMASK` 頂點屬性，
      匯出 `export_attributes=True`（LOD 也保留）
    - viewer：`makeFaceRig()` 載入時（靜止姿勢）記下臉中心、頭骨座標系、臉寬高；卡通 shader 對臉部用
      「光線繞頭的角度 φ」算分界：`edge = cos φ·1.1 + 0.22y² − 0.08y`，遠側臉頰超過分界就進陰影，
      再把法線換成「朝光／背光＋一點朝前」的合成法線 → 正好落在色帶的亮或暗一階；臉部不加輪廓光
    - 主光 = 會投影子的平行光（只看強度會挑到逆光輪廓光）
    - 對照圖 `assets/renders/face_shadow_compare.png`；套用 ソラ、カイ、布丁、可可、墨白、青蓮（＋各自 LOD）

16. [x] 段落 25：卡通渲染臉部不接收投影（瀏海的陰影貼圖不再弄髒 SDF 分界）— shader 內把
    `lights_fragment_begin` 的 `receiveShadow` 條件加上 `vFaceMask < 0.5`
17. [x] 段落 26：**體素 greedy meshing** — `build_voxel.build_mesh(greedy=True)`：每個方向、每一層，
    同色＋同骨＋四角 AO 相同的相鄰面合併成大矩形；AO 有漸層的面保留單格（明暗不變）；色彩抖動改成每塊合併面一個值
    - 遊俠 22,432 → 9,694 tris（−57%）、魔女 29,592 → 17,776（−40%，條紋／星點限制合併）；`--no-greedy` 可對照
    - 對照圖 `assets/renders/voxel_greedy_compare.png`

18. [x] 段落 27：頁面縮圖（`site/thumb.jpg`，`<link rel="artifact-thumbnail">`）＋**競技場移動**：
    選「走路／跑步」時整組角色沿競技場繞圈（`viewer._startLoco()`／`_updateLoco()`）
    - 速度：每個角色的自然速度 = 步幅（走 1.75、跑 2.48 倍腿長／循環）÷ 動作長度；全員共用中位數速度與同一角速度（不會互相超車），
      各自的動畫 timeScale 補償步頻（Q版腿短 → 踏得更快，腳不打滑）；腿長從 thighL／shinL／footL 骨骼量
    - 繞圈半徑 = clamp(0.25n + 1.0, 1.4, 2.2) m；進出圈 0.8 秒平滑過渡；切換其他動作時走回原位
    - 實際移動讓 spring bones 的拖曳更明顯；截圖 `assets/renders/stage_locomotion.png`

19. [x] 段落 28：**對打**（競技場動作「對打（輪流出招＋受擊）」）— `viewer._startSpar()`／`_updateSpar()`
    - 依腿長排序兩兩配對（八人時正好同風格互打），一組時置中、多組時兩欄網格（大組後排）；面對面側向鏡頭，距離 = 0.9×兩人腿長和＋0.35 m
    - 攻擊方播自己的招式（LoopOnce），受擊方在招式 45% 時播 Hit；結束 0.5 秒後攻守交換；各組錯開起始時間
    - `_castPlay(i, clip, once)` 共用交叉淡入；截圖 `assets/renders/stage_spar.png`

使用者（2026-11-27）：「看 agent.md 和 task.md 繼續完成待辦」（repo 裡沒有這兩個檔 → 以 CLAUDE.md＋本檔為準）

20. [x] 段落 29：**對打手感** — 每個招式各自標註命中時間＋hit-stop＋閃白＋擊退
    - Blender：招式函式加 `@bc.hit(影格)`（`build_character.hit()`）→ 建置後 `set_clip_extras()` 直接改寫 GLB 的 JSON chunk，
      寫入 `animations[].extras.hit`（秒 = 影格 / 24，glTF 時間從第 1 格 = 0.042 秒起算）；`make_lod.py` 用 `get_clip_extras()` 從原模型複製
      - 不用 Blender 的 `export_extras`：它會連所有自訂屬性一起輸出，而 glTF 匯入器會丟掉動作的 extras → LOD 會遺失
    - 命中影格用 filmstrip 逐格（每 2 格）判讀，見 README 表格。教訓：看關鍵影格數字會猜錯
      （鐵砧 18→26 是下揮，但錘子在 21 已掃過正前方、25 已到身後）；舊版統一 45% 時鐵砧還在舉錘、ソラ 還沒放箭
    - 鐵鷹 Aim 原本只有舉槍、沒有開槍 → 加一次後座力（23 格開槍、27 格回穩），對手的受擊才有理由
    - viewer：`loadGLTF()` → `withClipExtras()` 把 extras 放進 `clip.userData`（GLTFLoader 不處理動畫 extras）；
      對打狀態機改用**動作時間**判定（hit-stop 暫停時不會提早觸發），沒有標註的動作仍退回 45%
    - 命中特效（`SPAR` 常數）：hit-stop 0.08 秒（雙方 mixer.timeScale = 0）；受擊者閃白（`withFlash()` 在打光後混白，
      PBR／卡通／水墨材質都有效、描邊保持深色）；沿攻擊方向擊退 0.1＋0.18×腿長 m（0.14 秒推出 → 停 0.3 秒 → 0.55 秒回位）
    - 陷阱：混白是在 tone mapping 前的**線性**空間 → 0.55 看起來已是全白剪影；改成命中當格 0.5、0.22 秒內二次衰減
    - 全部程序化角色＋LOD 重建：位元組差異 < 1%、烘焙貼圖 PNG 完全相同（Cycles 烘焙是決定性的）→ git 增量小
    - `site/scene.html` 新增 `cast=`／`clip=`／`t=`／`shading=`，可截任一角色組任一動作的畫面；截圖 `assets/renders/stage_spar_impact.png`

21. [x] 段落 30：**體素魔女斗篷＋長髮物理**（`build_voxel.py`）
    - `Grid.group`：0 = 剛性（每個體素綁一根骨，照舊）、1 = 掛在 `Grid.springs[1]` 的鏈上。魔女：背後（y ≥ 0.105）、斗篷根部以下（z ≤ 0.94）、
      斗篷／長髮／髮帶顏色的體素 → 5 條 `cape0..4` 鏈（父骨 chest，沿斗篷 A 字外擴）
    - 不裂開的關鍵：可變形體素用 `bc.spring_weights(obj, chains, verts=...)` **依頂點位置**算權重 → 相鄰體素重合的角點權重相同；
      這些面**不做 greedy 合併**（合併的大面只有四個角，無法彎曲，還會在 T 形接點裂開）
    - 不同 group 之間的面不剔除 → 每組都是封閉殼，斗篷掀起或頭髮分開時看到的是另一組的表面，不是空心的破洞
    - 長髮貼在斗篷上 → 兩者共用同一組鏈（各自用一組會互相穿插）
    - 新 viewer 預設 `cape`（stiffness 3.0、gravity 0.45）：`cloth`（1.0／1.1）會讓外側鏈從 16° 垂到 ~7°，A 字下襬變窄；
      `cape` 平衡在 ~14°，待機輪廓與原設計幾乎相同
    - 碰撞體：`CHARS["witch"]["radii"]` → 軀幹三顆球＋腿部膠囊（`build_armature(J, R)`）
    - 驗證（`crackcheck`：所有鏈骨各彎 35°）：可變形區內 1,828 組重合頂點最大間隙 0.0000 mm；與剛性身體交界 382 組會分開（預期，靠封閉殼遮住）
    - 面數 17,776 → 21,184（+19%，可變形面保持單格）；遊俠輸出位元組完全不變；對照圖 `assets/renders/voxel_witch_springs.png`

待辦（下一步建議）：
- 重新發布 artifact：依 git 紀錄最後一次是段落 21 的第 9 版 → 段落 22–30（spring bones、LOD、臉部陰影、移動、對打、魔女物理）可能都還沒上線


## 決策紀錄
- 使用者無 Tripo 會員 → 全部改免費工具（2026-11-18）
- 預覽渲染用 three.js（接近遊戲引擎即時效果），Cycles 只用於烘焙
