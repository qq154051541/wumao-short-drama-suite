# 导演台动态控制台 · director-console

> 2026-11-17 新增。把「看板」从**静态资产浏览器**升级为**可编辑、可重新生成的动态导演台**。
> 脚本：`scripts/director_server.py`（后端，纯标准库）+ `scripts/director_ui.html`（前端，单文件）。
> 与 `build_asset_board.py` 的关系：**互补，不替代**。静态看板可离线双击打开；导演台需要本地服务，但能改能重生成。

> **页面状态保持（2026-11-20）**：`/board` 刷新默认回到总览/空白、丢掉当前段——已修。`director_ui.html` 在 `showView/selectSeg/selectEp/tab` 时把 `{view,cur,curtype,tab}` 写入 URL（`history.replaceState`）+ `localStorage['director_ui_state']`；刷新后按 URL→localStorage→默认 `tree`（编辑工作区）恢复，不再回总览。顶部栏新增「↻ 刷新本页」`refreshCurrent()`：只重拉当前页数据并留在当前视图/段落/tab；侧栏「刷新全部数据」`refresh()` 才是全局重载。深链接 `?view=tree` 现已入白名单，可分享"直接进编辑工作区某段"。动态取数另依赖后端 `no-store` 头 + 前端 `api()` 的 `cache:no-store` 与时间戳。**图片替换可见性（2026-11-20）**：所有展示图统一走 `imgUrl(path)`（`?t=Date.now()`）绕开浏览器缓存；图片替换/回滚/后台生成完成的回调必须调 `refreshImageViews()` 重渲染人物/资产/分集卡片，否则 DOM 仍是旧图——替换成功只调 `refresh()` 不够（它不重渲染这些页）。

---

## 〇、为什么要有它

静态看板只能"看文件名 + 缩略图"，看不到剧本正文、分镜细节，更不能改。而实际生产里 80% 的时间花在**逐段返工**上：改一句台词、换一个景别、某段重抽。

所以导演台的核心不是"展示"，是**「看 → 改 → 重生成」的闭环**：
```
点开某段 → 看分镜画格墙 → 改分镜字段/提示词 → 保存写回 prompt.txt → 一键重生成 → 版本对比 → 采用或回滚
```

---

## 一、启动

```bash
# 基本启动（默认 auto：8770 空闲就用，被占自动顺延 8771/8772 …）
python scripts/director_server.py --root <项目目录>

# 指定端口与剧名（剧名影响成片命名与标题栏）；固定 N 被占时同样自动顺延
python scripts/director_server.py --root <项目目录> --port 8770 --title "我不是神豪"

# 只做环境自检（不启服务，CI 友好）
python scripts/director_server.py --root <项目目录> --check

# 离线核心函数自测（不读项目、不写文件）
python scripts/director_server.py --root <任意目录> --self-test
```

启动横幅会打印实际地址 `http://127.0.0.1:<实际端口>/board` + 数据根目录；**服务端绑定成功后会自己打开这个实际地址**，并把端口写进 `导演台数据/port.json`。浏览器打开的必是本项目台。

### 多项目并行撞口（2026-11-23 二次修订 · v4）

病根链（两次实测）：
1. **v2**：所有台写死 8770。A 占着，B 探测到占用直接开浏览器 → 打开 A 的台。
2. **v3（半修）**：bat 预探测 8770~8869 取空闲口 → **先开浏览器** → 几秒后 server 才绑定；这段窗口里端口被别的进程抢走，server 顺延到下一个口 → **浏览器停在 8770（别人的台），本项目跑在 8771**。用户实测：横幅说「顺延到 8771」，浏览器却仍开 `8770/?view=characters&tab=script`。根因 = 两个组件各自探测端口的 TOCTOU 竞态。

**v4 现行策略（端口真相源唯一）**：
- **服务端权威**：`director_server.py` 用 `_resolve_port()` 绑定成功后，① 自己 `webbrowser.open(实际URL)`，② 写 `导演台数据/port.json`（含 port/url/root/title/pid）。浏览器只认服务实际监听的口，竞态消失。
- **bat 只启动**：`启动导演台.bat` v4 只探测 Python + `--port auto` 启动服务，**不预探测端口、不提前开浏览器**（旧行为已作为 bug 在自检中拦截）。
- **脚本/CI**：加 `--no-browser` 关掉自动开浏览器；从 `导演台数据/port.json` 读实际地址即可。
- 端口 ≠ 项目：同端口只认先启动的实例；本台数据只写本项目 `导演台数据/`，互不串。
- **占用 8770 的不一定是本包项目**：2026-11-23 实测占口者是另一 AI 工具（TRAE SOLO）自带的台（标题「长夜之火」）。不 kill 它，本包项目自动顺延，浏览器由服务端指向顺延后的实际口。

**排查占口进程**（确认 8770 到底是谁）：
```powershell
Get-NetTCPConnection -LocalPort 8770 -State Listen | ForEach-Object {
  Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)" | Select ProcessId,Name,CommandLine
}
```
命令行里的 `--root`/`--title` 能直接判定它属于哪个项目/工具。

> ⚠ 老 bat（v2/v3）已废弃：v2 被占直接开别人的台；v3 预探测与实际绑定竞态。重跑 `python scripts/install_director_console.py --root .` 升级到 v4。判断法：bat 里若还有 `for /L %%P in (8770,1,8869)` 或 `start "" http://127.0.0.1:` 就是旧版。

**自检输出示例**：
```
[episodes] 7 集: E01(S01-S06), E02(S07-S12), ... E07(S37-S42)
[segments] 42/42 个投产包目录存在
[clips]    41/42 段有成片
[assets]   12 张图配置了生成提示词
[ui]       OK
[check] PASS
```

> **Windows 一键启动**：项目根放一个 bat（双击启动并自动开浏览器），模板见 §七。

---

## 二、六个工作视图

主导航围绕导演的审阅顺序组织；编辑工作区保留原有段级工具：

| 视图 | 内容 |
|---|---|
| **总览** | 项目信息、画风/集数/单集时长、每集标题/简介/封面入口与生成进度。用户可在 `00_source/PROJECT_INFO.json` 登记项目字段；未登记时显示待补，不推断已确认信息。 |
| **剧本概览** | 阅读原著 Markdown 章节，逐章呈现；`01_script/adaptation_map.json` 保存原著章节 → 改编剧本/集/段的显式映射。无映射时显示未登记，不猜关系。 |
| **人物角色** | 从 `02_assets/characters` 分类浏览；提示词、参考图编辑沿用资产编辑器。主/配角、性格、造型与多视图（4 View 资产参考图，旧称三视图）展示依赖 `CHARACTERS.json` 与锚图，缺失时显示待补。 |
| **道具场景** | 按场景、道具分类查看；提示词与参考图沿用图片编辑器。 |
| **分集信息** | 每集列出分镜、参考图、状态、视频与资产更新提醒；点击进入段级编辑，可改分镜后保存，再经门禁明确触发重生成。 |
| **历史数据** | 文本/提示词修改记录与历史文件，按时间、类别、资源路径展示；恢复前确认，并为恢复动作再留一条记录。媒体生成文件仍按项目文件夹归档。 |

编辑工作区保留集树 → 段详情，包含剧本 / 分镜 / 人物连续性 / 提示词 / 参考图 / 成片·QC。

右上角：**▶ 全集连播**（有 `*连播*.mp4` 或 `*全集*.mp4` 时可用，带章节跳转）、**⟳ 重新拼接本集**（选中集时出现）。

---

## 三、五个关键能力（设计依据）

这些不是拍脑袋加的，是从成熟工具提炼的（2026-11 调研）：

### ① 分镜画格墙（参考 Boords / StudioBinder）
行业工具的主视图是**画格网格**而不是文字表。实现：
- 后端按每镜时间码 +1.0s 从成片抽帧，缓存到 `05_qc/machine/storyboard/SNN_shotN.png`
- 前端每格：抽帧画面 + 镜号 + 时间码/秒数 + 景别 + 画面 + 台词（黄色）+ 运镜标签
- 点画面放大

> 抽帧是**懒加载**：只有点开该段才抽，不预生成全部。

### ② 状态色标（参考 StudioBinder 的 approved/rewrite/hold）
每格右上角状态点，点击循环 `ok → rewrite → hold`：
- `ok` 绿 / `rewrite` 红 / `hold` 黄，卡片边框同步变色
- 存 `导演台数据/shot_status.json`，键为 `{段号: {"1": "ok", "2": "rewrite"}}`

### ③ 时间占比条（参考 animatic 的时长感）
每格底部青色条 = 该镜时长 / 全段总时长。一眼看出哪镜长哪镜短，节奏问题立刻暴露。

### ④ 版本对比（参考 Boords 的 versioning）
重新生成后，媒体 tab 自动变**左右并排**：
- 左「当前正式版」绿边 / 右「重新生成版」黄边
- 各显示实时时长 + 分辨率
- **「同步播放两版」**勾选后两个播放器进度锁死（`onplay/onpause/onseeked` 互同步）——这是判断新版好在哪的关键
- 右侧直接 **「✓ 采用这版」**（promote，写回 `导演台数据/progress.json`）

### ⑤ 剧本对照与分镜回写（参考 StudioBinder Shot Tagger 思路）
段详情的「剧本」tab 读取 `01_script/episodes/E*.md` 中的原文；「分镜」tab 从 `prompt.txt` 解析字段，编辑后写回 `prompt.txt`。剧本 md 仍是独立上游文件，不会随提示词保存自动同步。每次改台词、说话人或动作都必须对照剧本，差异回责任阶段处理；分镜与提示词的同源不代表剧本与提示词同源。

### ⑥ 资产按剧情名展示
`02_assets/ASSET_NAMES.json` 把 slug/hash 映射成剧中具体名称：
```json
{ "lmh_face": "李慕荷·面部锚图", "scn_inn_courtyard": "客栈·庭院",
  "0160e02c": "道具·名表三只" }
```
- 完整 slug 直接命中；40 位 hash 用**前 8 位**命中（原始参考图常见）
- 未命中则回落文件名（不会丢）

---

## 四、API 契约

所有接口本地、无鉴权（仅绑 127.0.0.1）。JSON 出入。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/manifest` | 集列表（含每集 duration/film）+ 段状态 + jobs + fullfilm |
| GET | `/api/assets` | 资产分组 + 每文件 kind/label/fname/regenerable |
| GET | `/api/episode/<EP>` | 剧本 md 全文 |
| GET | `/api/segment/<SEG>` | 段详情：prompt_txt/prompt_md/**shots**/pictures/clip/regen/qc |
| GET | `/api/file?path=` | 任意文本文件正文（带路径穿越防护） |
| GET | `/api/image/prompt?path=` | 图片生成提示词 + has_backup/backup |
| GET | `/api/jobs` | 后台任务列表 |
| GET | `/api/continuity/<SEG>` | 读取连续性 `ledger` 与文本校验 `report`；缺账本为未核验 |
| POST | `/api/continuity/<SEG>` | 请求 `{ledger, compile}`；保存账本，`compile: true` 时编译同步文本；以返回 `ok/ledger/report` 为准，不代表生成媒体 |
| POST | `/api/segment/<SEG>/save` | 保存整份 `prompt.txt`（`{prompt_txt}`） |
| POST | `/api/segment/<SEG>/save_shots` | 保存结构化分镜（`{shots:[...]}`），**自动重组 prompt.txt，保留其余段落** |
| POST | `/api/segment/<SEG>/status` | 保存逐镜状态（`{status:{"1":"rewrite"}}`） |
| POST | `/api/segment/<SEG>/regen` | 重新生成该段（后台，调 submit_seg.py） |
| POST | `/api/segment/<SEG>/promote` | 把最新 regen 版设为正式 |
| POST | `/api/episode/<EP>/assemble` | 重新拼接该集（+叠 HUD，若有 composite 脚本） |
| GET | `/api/chapters` | 原著分章与 `adaptation_map.json` 显式映射 |
| GET | `/api/history` | 按时间倒序返回文本/提示词/图片版本记录 |
| GET | `/api/project` | 读取项目元信息 |
| POST | `/api/history/restore` | 确认后恢复记录的文件版本，并保留恢复前版本 |
| POST | `/api/image/prompt` | 保存图片提示词；按 `ASSET_LINKS.json` 标记受影响镜头 |
| GET | `/api/engines` | 出图/出片通道就绪情况与未就绪原因（含 h3_runner inspect） |
| POST | `/api/image/regen` | 重新生成图片（本机 Image Forge · h3image/qwen）；版本归档并标记受影响镜头 |
| POST | `/api/image/rollback` | 回滚到 `_bak` 备份 |
| POST | `/api/image/replace` | 本地图片替换（base64，自动备份） |
| GET | `/file/<相对路径>` | 静态文件（视频支持 Range 206，可拖进度条） |

### 分镜解析/回写规则（关键）
`parse_shots()` 从 `prompt.txt` 的 `detailed_description` 段识别 `[00:00.000] ...` 镜头行，拆出：
- `shot` —— `frames the scene` 之前的景别描述
- `action` —— 之后的画面动作
- `dialogue` —— `<d>[Chinese]「…」</d>` 内文
- `camera` —— `Camera: ...` 
- `sound` —— `Sound at this moment: ...`

`rebuild_prompt()` 反向重组，**只替换镜头行**，`subject_definitions / summary / retention_analysis / overall_soundscape / non_diegetic_music` 等段落原样保留。新增镜头会插到 `overall_soundscape` 之前。

---

## 四·补、人物连续性生产门（唯一权威）

**P3 调度/分镜生成、P4 投喂生成和导演台编辑/重生成前必须读本节。** 机器契约以 `scripts/continuity.py` 为准；本节规定生产与验收边界。`blocking-direction.md` 决定调度，`asset-spatial-ledger.md` 承接空间事实，其他入口只引用本节。

### 1. 身份、对白与镜头焦点分别建账

- **一人一 subject**：每个具名人物独立登记 `id / subject / name / role`，`subject` 使用唯一的 `Subject X` 形式，不允许 pair/group 合并两人。主角身份（`role` 中的 protagonist 等上游叙事定位）与可选 `rank` 固定；schema 不要求新增 `protagonist` 布尔字段。每镜 `lead_subject` 恰为一个合法人物，可由剧情指定配角、听者或反应者，不因此改变其主配角身份。
- **逐句对白分离**：`speaker` 是谁说，`text` 是逐句原文，`mode` 是 `on_screen / off_screen / voiceover`，`listener` 是听者，`reaction_subjects` 是反应人物数组。听者和反应者可为同一人，但不能填说话人。视觉主体不自动等于说话人；画外声不自动要求画内人物张嘴。无对白必须显式 `dialogue: []`。
- **参考槽位据实绑定**：`references` 的 slot 按本段实际素材顺序、用途和模型接口登记；不得把某一 slot 永久写成主角或把一个参考槽中的两人合成一个 subject。参考图锁外观不能替代逐人的身份、站位和对白登记；M0 无图时仍按文字事实建账。
- **身份已知不等于站位已知**：名字、主配角、服装和参考图存在，都不能推出坐站、位置、朝向或说话人。先查剧本、场景事实与有效前段账本；仍未知的必需事实标待补，阻断该段生成，不得猜值过门。缺图片本身不阻断文本流程。

### 2. 真实数据契约与逐人继承

账本路径：`04_feed/segments/<SEG>/continuity.json`。顶层必需 `schema: "wumao-continuity/1.0"`、`segment`、`scene`、`characters`、`objects`、`shots`；可用 `previous_segment` 显式指向需要接续的前段，调用方须加载前段并传给 `validate_ledger(..., previous=...)`，不能仅有字符串就声称已核对。

| 层级 | 实际字段与约束 |
|---|---|
| 人物 | `id, subject, name, role, opening`；`rank` 可选；`closing` 可选且须与推导末态一致 |
| `opening` / 有效状态 | `presence` 为布尔值；`anchor_object` 必须引用 `objects` 已登记的 id；`side` 为 `left/right/center`（兼容左/右/中）；`posture` 为 `standing/seated/crouching/lying`；`facing` 为八方位；`x/y` 可选有限数值 |
| 镜头 | `id, start, end, lead_subject, states, dialogue`；`start/end` 是非负、递增且不重叠的秒数，**不是 `time` 字段**；`transitions` 为变更数组 |
| `states` | 以人物 id（或唯一 subject/name）为键的部分状态；`{}` 合法，表示逐人继承，不表示清空人物 |
| `transitions` | `{character, from, to, action}`；`from/to` 必须含相同且非空的字段集合，精确匹配旧态和新态，`action` 为明确动作；无真实改变的空转不合法 |

按 `opening → 每镜 states 增量 → transitions 核对 → 有效末态` 逐人推导。在场、依托物、侧别、坐站、朝向及坐标改变均须有匹配的动作；未改变的人继续继承，不能每镜重新摆人。同锚点、同侧、同坐标的人物重叠会阻断。

**同场景承接**：`previous_segment` 指向的同 `scene` 前段必须有完整有效账本；本段 `opening` 逐人继承前段推导末态，不能把硬切当成重置坐站/身份的授权。前段人物不能无交代消失；新增人物从 `presence: false` 开始，以 transition 入场。不同场景的转换须有剧本依据；缺前段材料记录跨段未核验，不声称全链通过。`continuity.py` 本身不查找前段文件，跨段加载由调用方负责。

### 3. 导演台操作与失效规则

1. 对照独立剧本 md 和本段提示词，补齐逐人人物表、物件锚点、开场状态及镜头表；本地 JSON 导入、拖动或下载只改变工作数据，不等于服务端已保存或已核验。
2. `GET /api/continuity/<SEG>` 读取已保存账本及其报告；它不验证尚未提交的编辑草稿。`POST /api/continuity/<SEG>` 发送 `{ledger, compile}`，`compile: false` 的草稿保存成功也不能解释为生产门通过；检查后端 `report` 的具体字段与来源。
3. `compile: true` 仅按账本向提示词注入行内连续性方向，逐句绑定 speaker，保留 `<d>` 开标签、`[Chinese]` 与台词原文。它不推断缺失事实，不改剧本，不调用图片/视频生成。缺账本、非法状态、对白文本/时间码不匹配时不能编译放行。
4. `save_ledger` 将最终提示词 UTF-8 内容绑定为 `prompt_sha256`。编辑 `prompt.txt`、批量注入提示词约束或保存结构化分镜，都会使旧哈希与旧报告失效，必须重编译、重新保存与校验；不能手改哈希假装通过。同场景前段变化后也须复核后段继承。普通编辑保存、编译成功和媒体生成成功是分别发生的动作。
   - **批量改 prompt 后的正规重绑流程**（2026-11-18 实证）：① 读出旧账本；② `copy.deepcopy` 后 `pop("prompt_sha256")`；③ 用去哈希候选重新 `compile_prompt`；④ preflight 只接受 `errors=[]` 且 warning 仅含 `MISSING_PROMPT_HASH / UNVERIFIED_SPEAKER_BINDING`；⑤ 写回 prompt；⑥ `save_ledger` 绑定新哈希；⑦ 再次 `validate_ledger` 必须为 `pass` 且 `speaker_binding_verified=true`。直接拿旧账本编译会被 `STALE_PROMPT` 正确阻断，**不得靠手改哈希绕过**。
5. `report.status` 的 `pass / review / blocked` 仅表达本次文本检查。缺账本为 `missing`，报告给缺失警告，应显示“未核验”；不得将兼容旧项目的 `review` 当生产放行。必需事实 unknown/未知/待定、陈旧哈希或未解决错误均阻断该段生成。未绑定逐句 speaker 时，文本一致也只算对白文字证据，不算说话人已核实。

前端地图只绘制提供有效 `0..100` 坐标的对象/人物，缺坐标不自动布点；拖动只改变工作账本坐标，不自动修正锚点、侧别或逐镜 transition。前端提示不是权威，最终以服务端调用 `continuity.py` 的报告为准；接口不存在或请求失败显示未通过，不以本地提示替代。

**两套前端（2026-11-18 起）**：`director_ui.html`（`/board`，旧版，完整工作区）与 `director_studio.html`（`/studio`，站位印张版）。后者按外部 `novel-staging` 报告的设计语言重做：冷灰印张 + 铁锈红、页眉 KPI 带、每镜一张大卡（左 16:10 俯视图 + 右选中面板/走位句/实时检查）、开场不在场人物托盘、八方位罗盘、质量门清单、`localStorage` 草稿（按段与项目根隔离）、JSON 导入导出（导出前剥掉 `_selected` 等内部字段）、`?seg=SNN` 深链接与 `?selftest=1` 浏览器内自检。拖动落点吸附最近物件、按相对位置更新 `anchor_object/side/x/y`，朝向自动指向该物件；**不自动编造 transition**。两套前端共用同一套 API，数据层不重复。

### 4. 参考图接线门（文件名为唯一事实源）

槽号 `<Picture N>` 只是 `refs.json` 的**上传位序**，不是图片身份。角色/场景/道具身份由文件名承担。因此：

1. 生产门逐项校验：`refs.json` 是否有 `pictures`、每个槽位文件是否真实存在、提示词每个 `<Picture N> (filename)` 的槽号是否存在、槽号旁文件名与 `refs.json` 同槽文件名是否一致、是否存在未被引用的槽位。
2. 错误码：`MISSING_REFERENCE_SLOTS`（无 pictures）、`MISSING_REFERENCE_FILE`（槽位指向的文件不存在）、`DANGLING_REFERENCE_SLOT`（提示词引用了不存在的槽号）、`REFERENCE_FILENAME_MISMATCH`（槽号与文件名错接）、`UNUSED_REFERENCE_SLOT`（refs 有锚图但提示词未引用）。任一存在即 `blocked`，并阻断 `compile: true` 与 `regen`。
3. **修法顺序**：先以文件名为准重算槽号，再校验「改后引用槽位集合 == refs 槽位集合」。只做槽号重编号（文件名不动）时属于语义等价修复，可批量执行；一旦出现「某文件名在 refs 中不存在」「refs 槽位无人引用」「同名文件多槽」三类，即停止自动修复，转入人工决定锚图集合，禁止猜测补位。
4. 批量修复必须：逐段备份 `prompt.txt`、dry-run 先行、只写能完整闭合的段落、产出「已修 / 阻断」清单。修 prompt 不等于修成片：旧成片仍是用旧提示词生成的，重生成前不得声称画面已修复。
5. **适配器路径**：`do_regen` 必须先查项目侧 `<ROOT>/tools/submit_seg.py`，再回落技能目录；只查技能目录会误报"缺少适配器"并阻断合法项目。生成适配器属于项目侧资产，按约定名放在项目 `tools/` 下。

### 4·补 A、投喂文字层的四条硬军规（2026-11-18 实证）

以下四条都来自真实返工，不是风格偏好。**P4 生成投喂稿、导演台重生成前逐条自检。**

1. **背景硬约束（防灰棚污染）**：角色锚图若是影棚灰底，近景/特写会把灰墙复现进成片（S43 第 3/4 镜、S52 第 1/2 镜实证）。每段 `detailed_description` 必须显式写：背景始终是本段所述实体场景，保留其建筑、固定物、地面材质与光向；**禁止无缝影棚背景、灰墙、中性幕布或任何平涂空背景**。该句可全局批量注入，但注入后所有已绑定台账须按上节重绑流程重编译；只改 prompt 不改台账会造成全量 `STALE_PROMPT`。修前先试片一段，确认灰墙消失再放量。
2. **姿态显式化（防"站着替代跪着"）**：剧本里的跪地、被压制、扶人、瘫坐等**非常规姿态**，必须在提示词的对应镜次写出人数、姿态和依托物。只写表情/情绪（"他看着跪地五人"）不足以约束群像姿势——模型会按中立站姿输出（S52 五人站着而非跪地实证）。姿态同时要进台账 `states/transitions`，不能只在英文提示词里出现。
3. **台词归属审计（防说话人漂移）**：生成前用剧本分镜表的「角色：「台词」」逐镜逐句比对 `prompt.txt` 的 `<d>`，确认文本、顺序、镜次一致。解析时必须排除三类假阳性：系统音/旁白（按项目约定不进提示词）、同人连续第二句无署名（须继承说话人）、无署名的拟声词（咔哒/嗒/嗡嗡）。已知真实错误形态：整段 OS 前移一镜（S56）、把后镜台词塞进前镜（S48）、漏句（S43/S52）、台词提前一镜（S81）。`text_mismatch` 归零才算文本对齐；角色未建 Subject 说话人（`小伙/女老板/二三号`）须补角色或改归属，不能靠画面主体猜。
4. **一人一 Subject（防串脸/克隆）**：`a group of / a pair of` 形式的群像 Subject 会让多个人共用同一张锚图，输出同脸同发（S52 五个混混克隆、S81 两名女性共 `<Subject G>` 实证）。这类段落必须拆成单人 `Subject` 并各配单人锚图才能重生成；拆不出来时宁可标未核验，不得用合影当单人锚。群像做视觉背景可以，但不得承担台词或镜头焦点。

**自动修复边界**：上述第 1、3 条属文本层、可批量修复并复验；第 2 条须逐段核剧本；第 4 条需要新锚图，属于人工决策。修文本不等于修成片——所有修复后都要重生成并逐镜验片。

**配套脚本（只读审计 / 幂等修复，均需 `--root <项目目录>`）**：

| 脚本 | 作用 |
|---|---|
| `scripts/audit_dialogue_attribution.py` | 台词归属审计，输出 `text_mismatch / speaker_not_in_shot / unresolved_speaker`，默认只写报告不改文件 |
| `scripts/harden_background.py` | 批量注入背景硬约束；默认 dry-run，`--apply` 才写盘并逐段备份；注入后必须重绑台账哈希 |
| `scripts/fix_reference_wiring.py` | 按文件名重算 `Picture N` 槽号；默认 dry-run，只写能闭合的段，其余转人工 |

### 5. 成片验收与存量边界

`evidence.text_only: true`、`film_verified: false` 必须如实保留。还需实际播放成片，逐句听声音与说话人、核对画内口型/画外闭口、人物身份/服装、坐站/朝向/依托物和同场跨段接缝，并留下对应段/镜头/媒体版本的核验记录。图像存在、哈希一致、compile 完成或状态色标 `ok` 都不能证明成片通过。

存量缺账本只显示未核验，不自动从旧提示词或媒体补造事实；本次能力不会自动修复既有 **102 段媒体**。补账、重编译、重新生成与实际验片须按选定范围分别执行，未处理的段维持未核验。

## 五、可选配置文件（全部可缺省）

| 文件 | 作用 | 缺失时 |
|---|---|---|
| `02_assets/ASSET_NAMES.json` | slug/hash → 剧中名称 | 回落文件名 |
| `02_assets/IMAGE_PROMPTS.json` | 锚图生成提示词（图片可重生成的前提） | 图片只可浏览/替换，无 `regenerable` 标记 |
| `02_assets/ASSET_LINKS.json` | 资产路径 → 关联分镜 ID 数组 | 资产变更无法自动推断依赖，页面提示“未建立映射” |
| `00_source/PROJECT_INFO.json` | 项目风格、集数、单集时长与分集红果元数据 | 缺项显示待补，不从剧本文本推定已确认值 |
| `01_script/adaptation_map.json` | 原著章节 → 改编集/段映射 | 仅展示已登记映射 |
| `导演台数据/history.json` | 时间倒序编辑历史索引 | 首次使用时自动创建 |
| `导演台数据/历史快照/` | 修改前文本/图片版本快照 | 历史可查看并恢复 |
| `导演台数据/progress.json` | 段→成片路径登记 | 回退扫描 `clips/raw/local-runner/sNN-040mp*.mp4` |
| `_tmp/seg_map.json` | 自定义集→段号映射 `{"E01":[1,2,3,4,5,6]}`（人工配置，不属于导演台数据） | 按 `(集序-1)*6+1 .. 集序*6` 推断 |

> **归置规则**：程序在 `导演台/`，数据一律在 `导演台数据/`（`jobs.json` / `shot_status.json` / `progress.json` / `history.json`，以及 `历史快照/`、`生成剧本spec/`、`临时文件/`）。
> 旧版写在 `_tmp/*.json` 与 `07_reports/` 的状态，安装器会**复制**迁入并保留旧文件；`_tmp/` 只留给流水线中转与人工配置。

**IMAGE_PROMPTS.json 结构**：
```json
{
  "02_assets/scenes/anchors/scn_inn_courtyard.png": {
    "name": "inn_courtyard", "kind": "scene", "preset": "draft",
    "prompt": "...", "regenerable": true, "note": "可选提示"
  }
}
```

**CHARACTERS.json 结构**（人物视图与关系图谱的数据源；不写就只有裸图）：
```json
{
  "characters": [
    {
      "id": "c_li", "name": "李慕荷", "role": "protagonist", "rank": "主角",
      "identity": "外科医生", "personality": "外冷内热，护短",
      "appearance": "骨相清瘦，单人旁开双眼皮，左眉尾有浅疤",
      "outfit": "米白长风衣 + 深灰高领 + 直筒西裤",
      "voice": "偏低，语速慢",
      "anchors": {
        "face": "02_assets/characters/li_face.png",
        "three_view": "02_assets/characters/li_3v.png"
      }
    }
  ],
  "relations": [
    {"from": "c_li", "to": "c_wang", "label": "旧识", "type": "ally", "note": "十年前同一案"}
  ]
}
```
- `rank` 写「主角 / 配角 / 反派 / 群像」，前端按此分组；留空即“未标注”。
- `anchors` 的键建议用 `face / three_view / full / outfit`；每个值同时是 `IMAGE_PROMPTS.json` 的键时，卡片上会出现「✎ 提示词」。
- `relations` 指向不存在的 `id` 会被丢弃并在界面标注条数，不静默通过。

**PROJECT_INFO.json 结构**（总览与红果发布信息）：
```json
{
  "title": "我不是神豪", "style": "都市逆袭 · 冷调霓虹", "genre": "男频爽剧",
  "model": "MiniMax-H3", "aspect": "9:16", "episode_seconds": 60, "episodes_total": 7,
  "audience": "18–35 男性", "logline": "外卖员被误认神豪，一夜翻盘",
  "episodes": {
    "E01": {
      "hongguo_title": "被叫了一声老板",
      "synopsis": "送餐途中被误认集团继承人……",
      "cover": "06_delivery/covers/E01.jpg",
      "tags": ["逆袭", "爽感"],
      "note": "标题 12 字内，前 6 秒必须出冲突"
    }
  }
}
```
未填字段在总览显示“待补”并列进 `missing_fields`，**不从剧本文本推断已确认值**。

**ASSET_LINKS.json 结构**（资产 → 关联分镜；决定改图后哪些段要复核）：
```json
{
  "02_assets/characters/li_face.png": ["S01", "S02"],
  "02_assets/scenes/anchors/scn_inn.png": ["S03"]
}
```
- 未登记时回退扫描各段 `refs.json`（再退到提示词里的 `<Picture N> (文件名)`）来显示“出场段”；
- 但**“需要复核”标记只由显式 `ASSET_LINKS.json` 触发**，避免把只是同图出现的段误标为必须返工。

**出图 / 出片通道（2026-11-18 起本机优先）**：

| 能力 | 默认通道 | 前置 |
|---|---|---|
| 参考图重生成 | 本机 Image Forge `D:/WorkBuddyProject/AI生图/start.py` → ComfyUI Desktop `127.0.0.1:8188` | ComfyUI 已启动；默认 `h3image`（本地 MiniMax-H3-Image），单图可写 `"engine": "qwen"` 切到 Qwen-Image 2.1 |
| 分镜出片 | `comfyui-h3-local-runner` 的 `h3_runner.py submit` | 项目内 `jobs/local-runner/verified-template.api.json` + `state.json`（由一次成功任务 `capture` 生成） |
| 兜底 | 项目 `tools/submit_seg.py` | 存在即用，仅在本地 H3 未就绪时生效 |

```bash
SD_IMAGE_GEN=D:/path/to/AI生图/start.py   # 覆盖生图器入口
SD_IMAGE_ENGINE=h3image                   # 覆盖默认出图引擎（h3image / qwen）
H3_RUNNER=.../h3_runner.py                # 覆盖 H3 runner 路径
H3_PYTHON=...python.exe                   # 跑 h3_runner 的解释器（默认优先 ComfyUI venv，因参考图审计需 Pillow）
```

- 出图**不解析输出目录**：读 `start.py gen --json` 的 `images[0]`，取到即复制回目标路径，避免"扫最新文件"误抓别人的图。
- 出片**必须**先有 verified 模板：缺模板时 `/api/segment/<SEG>/regen` 返回可读原因，界面显示"本地 H3 未就绪"，不假装能出片。
- `scripts/h3_spec.py` 负责把单段投喂包（`prompt.txt` 时间码行 + `refs.json`）换成 runner 认的 Director spec；可独立自检不占 GPU：
  `python scripts/h3_spec.py --project <项目> --segment S01 --out 导演台数据/生成剧本spec/S01.json`
- 通道状态可查：`GET /api/engines`（图像/视频就绪情况与原因），总览页同步显示。

---

## 六、依赖与边界

**必需**：Python 3.9+（纯标准库）、ffmpeg/ffprobe（抽帧与时长）
**本机生成（默认走这条）**：ComfyUI Desktop 在 `127.0.0.1:8188` 运行；Image Forge 提供出图入口；`comfyui-h3-local-runner` 提供出片 runner。三样缺任一项，对应按钮会显示"未就绪 + 原因"，其余浏览/编辑/留痕不受影响。
**可选**（项目侧 `tools/` 适配脚本，本地 H3 未就绪时才用）：
- 单段重生成适配器（约定名 `submit_seg.py`，放项目 `tools/`）—— 缺失且本地 H3 也未就绪时 regen 报错，但浏览/编辑仍可用
- 集拼接脚本（约定名 `assemble_episodes.py`，放项目 `tools/`）—— 缺失则用内置 concat 兜底
- 叠 HUD 脚本（约定名 `composite_hud_ep.py`，放项目 `tools/`）—— 缺失则拼接后不叠

**项目内置副本**：导演台按技能约定**落到每个项目根目录**，不靠手工复制。

```bash
# 铺进项目（幂等；缺什么补什么，文件与技能不一致才覆盖并备份）
python scripts/install_director_console.py --root <项目目录>
# 只检查是否落后于技能版本（交付前必过）
python scripts/install_director_console.py --root <项目目录> --check
```

落地物：`<项目>/导演台/{director_server.py,director_ui.html,director_studio.html,continuity.py,h3_spec.py,使用说明.md}`、项目根 `启动导演台.bat`（GBK 编码的中文脚本）、`00_source/PROJECT_INFO.json`（仅缺失时创建，不覆盖已有值）、`导演台/安装清单.json`（版本 + 每文件 sha256）、`导演台数据/`（数据与快照）。

- `/建目录` 会自动调用该步，无需重复；接手已有项目时单独跑一次即可。
- 被覆盖的旧文件备份在 `导演台/旧版本备份/`，不会静默丢改动。
- ⛔ 不要手改项目里的 `导演台/*`：下次安装会覆盖；要改就改技能内同名文件再同步。
- 旧版英文目录（`director/`、`director_data/`）会在安装时自动改名为 `导演台/`、`导演台数据/`，并保留备份。

**不做的事**（明确边界，避免误期待）：
- ❌ 不做用户鉴权/多用户 —— 只绑 127.0.0.1，是单人本机工具
- ❌ 不做云端同步 —— 全部本地文件
- ❌ 不替代 `/审查` 的质检门禁 —— 导演台是生产工具，不是质量判定

---

## 七、Windows 一键启动模板

项目根放 `启动导演台.bat`（v4 服务端权威端口：**bat 不预探测、不预开浏览器**）：
```bat
@echo off
setlocal EnableExtensions
if not defined SystemRoot set "SystemRoot=C:\Windows"
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
"%SystemRoot%\System32\chcp.com" 936 >nul 2>nul
cd /d "%~dp0"

rem ---------- 探测 Python 3.9+（命令名 → 常见安装目录 → py 启动器 → 本机已知路径）----------
set "PY="
call :probe python
if not defined PY call :probe python3
if not defined PY call :probe py
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY for /d %%D in ("%ProgramFiles%\Python3*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY if exist "D:\trae-python\tools\python\python.exe" call :probe "D:\trae-python\tools\python\python.exe"
if not defined PY for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY (
  echo [x] 没找到 Python 3.9 以上。把 py -3 --version 的结果发我，或重装时勾选 Add to PATH。
  pause
  exit /b 1
)

rem ---------- 端口策略（v4）：交给服务端绑定后决定，bat 不碰端口 ----------
rem v3 曾在 bat 预探测端口后先开浏览器，服务真正绑定前端口被抢 → 浏览器停在别人的台。
rem 现在服务端 --port auto 自己找空闲口、绑定成功后自己开浏览器 + 写 port.json。

rem ---------- 定位程序目录（防代码页不对时中文目录名读不出来）----------
set "CDIR=%~dp0导演台"
if not exist "%CDIR%\director_server.py" set "CDIR=%~dp0director"
if not exist "%CDIR%\director_server.py" (
  echo [x] 找不到程序目录里的 director_server.py。回到技能目录重跑安装脚本。
  pause
  exit /b 1
)
pushd "%CDIR%"

echo ============================================================
echo  导演台 - 数据根：..
echo  服务端绑定后自己开浏览器；实际地址看下方横幅 / 导演台数据\port.json
echo  关闭本窗口即停止服务
echo ============================================================
"%PY%" director_server.py --root ".." --port auto
set "RC=%ERRORLEVEL%"
popd

echo.
if not "%RC%"=="0" echo [x] 导演台异常退出，退出码 %RC%。把上面几行报错发我。
echo [i] 服务已退出
pause
exit /b 0

rem ---------- 子程序：验证一个候选 Python ----------
:probe
if exist "%~1" (
  "%~1" -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=%~1"
  exit /b 0
)
for /f "delims=" %%P in ('where %~1 2^>nul') do (
  if not defined PY (
    "%%P" -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=%%P"
  )
)
exit /b 0
```

> ⚠ 老 v2/v3 bat 已废弃（v2 打开别人的台；v3 预探测与绑定竞态）。跑一次
> `python scripts/install_director_console.py --root .` 即升级为 v4。判断法：bat 里若还有
> `for /L %%P in (8770,1,8869)` 或 `start "" http://127.0.0.1:` 就是旧版。

---

## 八、已知限制 / 后续

| 项 | 状态 |
|---|---|
| 抽帧需 ffmpeg，Windows 路径含中文时注意编码 | 已验证可用 |
| 图片重生成强依赖生图器，未配置时降级为"只可替换" | 设计如此 |
| 状态色标是单人标记，未做多人协同/评论 | 可扩展为评论区 |
| 版本对比只比"最新 regen vs 正式"；文本/提示词/图片改前快照已进「历史数据」 | 视频多版本列表仍待做 |
| 集→段映射默认 6 段/集 | 用 `_tmp/seg_map.json` 覆盖 |
| 资产→分镜的关联提示依赖 `ASSET_LINKS.json` 或各段 `refs.json` | 无登记时显示“未建立映射”，不猜 |

---

## 九、交付节奏：先审后拍（2026-11-18 用户裁定）

导演台的定位是**生成视频之前交给导演的审阅件**，不是生成之后的看板。默认顺序：

1. **AI 跑完全部前置**：原著拆章 → 改编映射 → 分集剧本 → 人物/道具/场景锚图与提示词 → 逐镜 H3 提示词 → 参考图接线 → 连续性台账。
2. **开工导演台**：`python scripts/director_server.py --root <项目>`（端口默认 auto：8770 被占自动顺延；服务端绑定成功后自己开浏览器 + 写 `导演台数据/port.json`，开台前核对横幅项目名），把 `/board` 六视图填满真实数据。
3. **导演审阅与修改**：总览核对风格/集数/时长/红果标题封面；剧本概览核对改编取舍；人物角色核对外形与主配；道具场景核对锚图；分集信息逐镜看提示词与参考图。
4. **只有导演说“可以出片了”才生成**：`/api/segment/<SEG>/regen` 是显式动作，界面不提供自动批量跑；未接入 `tools/submit_seg.py` 时按钮如实显示“不会出片”。

**硬规则**：

- ⛔ 不得把“导演台已生成”当成“视频已生成”；两者是不同动作，进度分开显示。
- ⛔ 不得因为导演台可用就跳过五道前置锁与 I 画风锁。
- ⛔ 修改参考图后，必须让关联分镜出现“参考资产已更新·待复核”标记；该标记只能由人工核对后清除，不能自动消失。
- 审阅阶段改分镜/提示词 = 只写文件 + 留快照；不要顺带触发生成。

### 九·补、范围限制门：只做中文短剧（2026-11-18 用户裁定）

导演台不是通用生成器，它是**中文短剧**的审阅台。范围声明放在项目配置里，机器可判：

```json
// 00_source/PROJECT_INFO.json
{ "language": "zh-CN", "form": "中文短剧" }
```

| 判定 | 行为 |
|---|---|
| `language` 缺省 / `zh*` / `cn` / `中文短剧` | 放行；总览显示范围条「范围：中文短剧 · zh-CN · 普通话对白 + 简体字幕 · 竖屏连续短剧」 |
| 显式写成其它值（如 `en`、`ja`） | **锁定生成**：`/api/segment/<SEG>/regen` 与 `/api/image/regen` 直接抛「范围限制」；总览顶部变红条并说明原因 |

- 判定函数在服务端 `project_scope()` / `scope_gate()`，**不靠前端隐藏按钮**——直接打接口也拦。
- 参考图重生成同样受门（`do_regen_image` 首行 `scope_gate()`），避免「视频拦住了、图还能出」的半开门。
- ⛔ 不要为了让门通过而把 `language` 改成 `zh-CN` 却写英文提示词：门只管**声明**，文本语言仍需人看；英文对白会被 `validate_prompt.py` 与人工复核另行打回。
- 范围外的需求（英文剧、广告片、纯 PREVIS 等）在**对话层就停手说明**，不要先建项目再拒绝——空项目也会被装上导演台，白折腾一趟。

---

## 十、参考图与分镜的写法下限（配合 H3 线）

### 10.1 参考图：按当期审美重写，不照译原文

原文只提供**人物功能、辨识特征、题材线索**三样东西；视觉呈现按 `character-visual-style-lock.md` 的档位与颜型重写：

- 必写：年龄段与骨相、脸型与眼型、肤质、发型（长度/分缝/质感）、身形比例、服装（版型/材质/领口/袖型/配色）、鞋包配饰、妆容浓淡。
- 必写：镜头（如 85mm 中近景）、光线（主光方向 + 色温 + 轮廓光）、背景（实体场景或纯色影棚，二选一，写清）、输出规格（竖屏 9:16、写实质感）。
- **详细度下限**：单人锚图提示词不少于 120 字（中文），至少覆盖「脸—发—肤—形—衣—光—镜—景」八项；多视图（4 View 资产参考图；旧称三视图）另写「正面 / 侧 45° / 正侧 / 背面同一造型、同一光位」。
- ⛔ 不写「美颜/磨皮/网红脸/精修」这类滤镜词，美化落在骨相与质感上。
- ⛔ 原文写“普通路人”不等于出图要普通：按 §8.3 提档，但保留痣、疤、单眼皮等记忆点。
- ⛔ 服装年代与题材冲突时，以题材档位为准，并在 `note` 写一句改写理由，便于导演复核。

### 10.2 分镜：按 H3 官方字段写满

分镜行的解析字段（`shot / action / dialogue / camera / sound`）直接对应 `detailed_description` 的时间轴行；写的时候按 `h3-adapter.md` 的六段（Ref2VA）或三段（Base）补齐，不许只写一句动作：

| 层面 | 每镜必须能回答 |
|---|---|
| 景别与机位 | 特写/近景/中景/全景/远景，机位高度与轴线侧 |
| 主体动作 | 谁、做什么、做到什么程度（起止状态），≤2 个动作意图 |
| 表情与视线 | 看向谁/什么，情绪落点 |
| 台词 | 说话人 + 逐句原文 + 画内/画外/旁白 |
| 运镜 | 推/拉/摇/移/跟/手持/固定，速度与终点 |
| 画内音 | 该镜可听见的声源与触发动作 |
| 参考图接线 | `<Picture N> (文件名)`，与 `refs.json` 槽位一一对应 |

- **详细度下限**：每镜 `action` 中文不少于 40 字，且必须含「主体 + 动作 + 环境/光线」三要素（对应 C32）。
- 时间码必须连续，首镜 `00:00.000`，末镜结束 = 段落时长；单段时长按所选模型上限（H3 ≤15s）。
- ⛔ 群像写 `a group of / a pair of` 当 Subject 会导致同脸克隆，必须拆单人 Subject + 单人锚图。
- ⛔ 背景必须锁到本段实体场景，禁无缝影棚灰底（会污染近景）。

---

## 十一、验证记录（2026-11-18 · 六视图改造）

用临时夹具项目（1 集 / 6 段 / 2 章原著 / 2 名角色 / 1 条关系）跑接口与浏览器回归：

- 接口 34 项断言全 PASS：`/api/overview`（风格/集数/时长/红果标题/封面/进度/缺项）、`/api/chapters`（分章与正文）、`/api/characters`（角色卡、锚图被引用段、关系边过滤）、`/api/assets`（提示词透出）、`/api/history`（快照查看与恢复）、`/api/segment/<SEG>/asset_ack`（清除复核标记）。
- 状态保存改为**合并**语义：改镜次状态不再清空 `asset_update` 标记（原实现会整段覆盖）。
- 历史恢复改为**快照文件**模型：正文从 `导演台数据/历史快照/` 读，图片复制快照；恢复动作本身再留一条记录，可反复回退。
- 浏览器（Chrome headless 1600×1300）截图确认：总览 KPI 与分集卡、剧本阅读器（章节目录 + 正文 + 改编 badge）、人物卡与关系图、分集展开后的镜卡/参考图/视频/完整提示词、历史卡与前后对比，均正常渲染。
- 修复两个实际缺陷：① `showView` 隐藏六个工作视图后未重新显示当前视图（整页空白）；② 配角筛选写成 `!isLead` 未传参，恒为 0。
- 未验证：真实 H3 生图与出片（本机未配置 `SD_IMAGE_GEN` / `submit_seg.py`），故界面如实显示“未接入”，不宣称可出片。

---

## 十三、创作审阅闭环（导演台 1.4 · 2026-11-19）

本节为导演台新增审阅功能的唯一规范，来自对成熟平台通行创作方法的观察与独立实现，不引入第三方代码、提示词、界面素材和云端账户。

**观察来源与证据边界**：

- [LibTV 官网](https://www.liblib.tv/) 抓取主要为作品展示；画布、节点与主体库功能依据[南方+报道的检索摘要](https://www.nfnews.com/content/ky9ve0Oq3G.html)，未读取报道全文及登录实测。
- [小云雀官网](https://xyq.jianying.com/) 展示自由画布、短剧 Agent、剧本解析与分镜脚本编写；登录后编辑器未实测。
- [Flova 官网](https://www.flova.ai/) 展示统一资产工作区、列表/网格/画布、局部批注修订、资产复用与多时间线；独立时间线不推导为完整版本控制。
- [RooYun 官方教程](https://www.rooyun.com/learn/agent-claude-code) 说明剧本、角色、场景和分镜卡的结构化组织与局部修改；教程明确其 Agent 暂不支持 3D 摆位及多人实时协同，不推导为整个产品均无此功能。

归纳的共同方向是项目内组织内容、结构化分镜与局部迭代。批注签审、输入指纹和文字节奏预演是本导演台按现有工作流独立实现的增量，不能表述为四家均已验证具备的同名功能。

| 能力 | 使用方式 | 可验边界 |
|---|---|---|
| 生产看板 | 按集、待审/通过/过期/待修改筛选，查看未解决批注，点段进入编辑 | 只汇总项目真实段，不把旧 `ok` 色标视为签审 |
| 逐镜批注 | 选镜写意见，修复后标记解决 | 镜头内容摘要定位；改镜、插删镜后不把原意见静默挂到其他镜 |
| 按版本签审 | 当前输入版本通过或退回修改 | 批准须提交当前摘要，存在未解决批注时不能通过；修改输入后旧签审过期 |
| 分镜节奏预演 | 播放、暂停、拖动进度与跳镜，审看画面描述和对白 | 仅文字节奏预演；未知时间待补，不声称已生成视频或声音 |

**事实源**：`导演台数据/审阅记录.json` 保存意见和签审；段内容仍来自原 `prompt.txt` / 分镜数据、`continuity.json`、`refs.json` 与项目内实际参考图，不另存一套正文。摘要覆盖实际图片内容，换同名图亦使旧签审过期。批注存在过期或失去镜头锚点时须明确提示。

**状态口径**：`pending` 待审、`approved` 已通过、`stale` 已过期、`changes_requested` 待修改。签审是人工确认输入版本，不能替代连续性生产门、实际声画核验或范围门；保存、批注、签审与节奏预演均不调用媒体生成。保留用户明确指令才出片和先小样后放量。

**接口**：`GET/POST /api/review/<段ID>` 为审阅读写，`GET /api/production` 为项目生产汇总；冲突返回错误并要求刷新，数据原子写入。不是多人实时协作或权限系统。

**吸收裁决**：沿用项目资产管理、局部编辑与版本追溯；新增意见→待办→当前版本签审闭环与节奏预演；拒收与中文短剧无关的广告、外语译制、云端积分、付费模型聚合。3D渲染预演、自动语义拆剧本、云端团队协作和专业剪辑时间线均不在本次实现内，不得在交付中声称支持。

### 13.1 实际验证记录（2026-11-19）

- 审阅接口回归 6 项、连续性接口回归 7 项通过；覆盖批注/解决、重启持久性、签审冲突、同名换图过期、旧批注失锚及仍计待办、草稿保存不改提示词、不支持分镜格式拒绝且不写。
- Chrome 隔离夹具真实交互 14 项通过：生产看板→批注→阻止带待办批准→解决→批准→保存改稿→过期→重新签审；预演真实区间、播放、暂停、前后跳镜及未知终点提示；无 JavaScript 异常及网络传输失败（排除 favicon）。
- 最终 HTML 内嵌脚本经 Node 语法检查通过。修正异步函数声明、签审过期无法重签、旧批注判定不一致、跳镜错位及切段异步回写问题。
- 安装器自测、空项目端到端 21/21、既有六视图与历史接口 41/41、本地引擎/范围门 24/24、连续性基础 34 项及技能包完整性检查通过。
- 当前项目已同步导演台 1.4.0，5 个运行文件与技能源摘要一致；旧程序保存在 `导演台/旧版本备份/`。真实项目数据目录未有既存状态文件；有状态数据保留另由安装器临时夹具验证。
- 未执行真实出图/出片；文字预演不代表成片、声音或 3D 摆位通过。截图文件已生成，但本次图像查看能力不可用，视觉布局不作已人工验图声明。

---

## 十二、旧验证记录（2026-11-17）

**人物连续性增补的验证界限**：本批已完成五份文档的入口指针、真实 `start/end` 字段、旧同源口径清扫与代码围栏完整性检查，并对照 `continuity.py` 和前端 `{ledger, compile}` 请求；以下真实项目记录是原导演台历史验证，不能推导本次连续性 API、浏览器交互或成片通过。连续性后端路由、完整回归与实际媒体验收须以各自实际结果补记，不预填最终结论。

原导演台历史验证：用真实项目（7 集 / 42 段）跑通：
- `--check`：7 集自动识别、42/42 投产包、41/42 成片、12 张图提示词、UI OK → **PASS**
- `/board` 200、manifest 标题/集数/全集正确、assets 442 文件、S07 分镜 4 镜 4 抽帧
- 分镜画格墙截图：4 张真实画面 + 时间码 + 景别 + 台词 + 运镜标签 + 时间条 + 状态点，全部正常
- 分镜编辑闭环：读 4 镜 → 改台词 → save_shots → 读回确认 → 恢复原文件（数据无污染）
- 版本对比：造测试 regen 文件验证并排/元信息/按钮，验证后删除
- 图片回滚：构造替换+备份 → rollback → hash 精确恢复 → 清理 `_bak`
