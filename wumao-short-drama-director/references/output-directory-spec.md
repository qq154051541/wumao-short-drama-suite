# 输出目录规范（每个生成文件都必须落位）

> **定位**：P0 立项时先建目录，之后**所有产出按类入位**。生产层保持约定英文路径，工具层和新增审阅数据使用中文直述用途；⛔ 禁止散落在项目根目录、禁止随意改动外部程序依赖的目录名、禁止临时文件混进交付目录。
> **唯一事实源**：`project_state.json` 放根目录，记录目录映射、素材形态（默认 M1）、当前阶段与版本；各文件只引用它，不各存一份状态。

---

## 一、标准目录树

```
<project_root>/
├── 00_source/              用户自备原文 / 大纲 / 参考素材（⛔ 不打包、不上传）
│   └── README.md           来源登记（题材 / 授权状态 / 字数 / 时点）
├── 01_script/              剧本层
│   ├── development/        开发圣经、人物表、关系图谱、三张账
│   ├── episodes/           E01.md / E02.md …（两位补齐）
│   ├── beats/              爽点表 PAY-N、每集钩子矩阵、因果桥检查表
│   └── dialogue/           台词本（按角色聚合，接 TTS）
├── 02_assets/              资产层
│   ├── characters/         角色档案 + 四格板提示词 + 参考图索引
│   ├── scenes/             场景九宫格 + 一致性锚点 + 光照变体
│   ├── props/              道具四格 + 单实例锁台账
│   ├── audio/              音色提示词 / 音轨说明 / 参考音频索引
│   └── IMAGE_PROMPTS.json  ★导演台资产面板数据源（见下方"资产落盘铁律"）
├── 03_storyboard/          分镜层
│   ├── shots/              分镜表（每段一份）
│   └── boards/             故事板图（CLEAN_GRID 干净版 / 技术标注版）
├── 04_feed/                投喂层（★ 每段一个目录）
│   ├── segments/
│   │   └── S01/prompt.md   + refs.json + S01.srt + audio_note.md
│   └── compiled/           compile_feed.py 产物（整稿 / 分段稿）
├── 05_qc/                  质检层
│   ├── machine/            validate_prompt / gate_check 报告
│   ├── quality/            八维体检报告
│   └── consistency/        跨集一致性台账（脸/服/景/道/光/声）
├── 06_delivery/            交付层
│   ├── listing/            剧名 / 简介 / 标签 / 集数
│   ├── cover/              封面图索引与提示词
│   ├── subtitles/          烧录用 SRT 汇总
│   └── manifest.md         上架前 12 项自检 + 成片清单
├── 07_reports/             看板 / HTML 报告（build_asset_board.py 产物）
├── 导演台/                 导演台程序（技能安装：后端 + 两个前端 + 连续性校验 + H3 剧本转换）
├── 导演台数据/             导演台数据（本项目独有，升级不清空）
│   ├── jobs.json           后台任务
│   ├── shot_status.json    逐镜状态 ok / rewrite / hold
│   ├── progress.json       段 → 成片登记
│   ├── history.json        修改历史索引
│   ├── 审阅记录.json        逐镜批注、待办与当前输入版本签审（运行时创建）
│   ├── 历史快照/           改前快照（可反复回退）
│   ├── 生成剧本spec/       提交给本地 H3 的 Director spec（调试用）
│   └── 临时文件/           导演台临时产物（可清空）
├── 启动导演台.bat           一键启动（双击开 http://127.0.0.1:8770/board）
├── project_state.json      唯一事实源
└── README.md               项目说明（自动生成目录索引）
```

> `导演台/` 与 `启动导演台.bat` 由 `install_director_console.py` 生成（`/建目录` 自动执行），
> ⛔ 不手改；`导演台/安装清单.json` 记录安装版本与文件哈希，`--check` 可验是否落后。

---

## 一·补、根目录归置总则（★ 程序 / 数据 / 临时 三分）

**每个根条目只做一件事，且只有一个归属方**。禁止把状态文件、临时产物、配置散落到别的目录：

| 根条目 | 归属 | 放什么 | 谁写 | 可删？ |
|---|---|---|---|---|
| `00_source/`~`06_delivery/` | 生产层 | 原著 / 剧本 / 资产 / 分镜 / 投喂 / 质检 / 交付 | 各阶段脚本与人工 | ⛔ 交付内容 |
| `07_reports/` | 报告层 | 看板、HTML 报告、机检汇总 | 报告类脚本 | ⛔ |
| `导演台/` | **程序** | 导演台代码（可被技能覆盖） | `install_director_console.py` | ⛔ |
| `导演台数据/` | **数据** | 任务 / 镜状态 / 历史快照 / 提交剧本 / 临时产物 | 导演台运行时 | 仅 `临时文件/` 可清 |
| `jobs/local-runner/` | **外部程序** | `comfyui-h3-local-runner` 的模板与队列状态 | h3_runner.py | ⛔ |
| `clips/raw/local-runner/` | 生成层 | 分段原片与 regen 版 | 生成通道 | ⛔（版本对比依赖） |
| `_tmp/` | **临时** | 流水线中转、`seg_map.json` 等人工配置 | 各脚本 | 交付前清空 |
| `project_state.json` | 状态 | 唯一事实源 | 编排层 | ⛔ |
| `启动导演台.bat` / `README.md` | 入口 | 一键启动与目录说明 | 安装器 / 建树脚本 | ⛔ |

**三条硬约束**：

1. **程序与数据分离**：升级导演台只覆盖 `导演台/`，`导演台数据/` 一律不动；反之清数据不能删程序。
2. **状态文件不许外溢**：导演台的任务、镜状态、历史只写 `导演台数据/`；`_tmp/` 只留给流水线中转。（旧版把状态写在 `_tmp/*.json` 与 `07_reports/director_history.json`，安装器会**复制**迁入 `导演台数据/` 并保留旧文件。）
3. **外部程序目录不接管**：`jobs/local-runner/` 归 H3 runner，`clips/` 归生成通道；不要为了"整齐"把它们挪走或改名——一挪就断链。

### 导演台数据落盘避错清单（2026-11-20 · 四视图速查 · ★交付前必读）

> **背景**：实测四轮连续踩坑——「/board 没数据」「资产页空」「人物角色页空」「H3 提示词不合官方格式」。根因高度同源：**同一份内容在交付 md 里写得很全，但没落到对应工具真正读取的文件/目录**。本清单把这些坑一次收口，后续照此自检，⛔ 不要重复试错。
>
> **元规则**：**「写在交付 md 里」≠「导演台能看到」**。导演台每个视图读**各自独立的数据源**，互不通用；M1 形态（图未生成）下自动发现大面积失效，必须**显式登记**。

#### ① 四视图 × 数据源对照（唯一对照表）

| 导演台视图 / API | 真正读的文件 | 缺了会怎样 | 落盘责任阶段 |
|---|---|---|---|
| 剧本/分集树 · `/api/manifest` | `01_script/episodes/E0N.md`（首行 `# E0N · 标题`） | 集数 0、无集可选 | P1 |
| 段/投产包 · `/api/production` `/api/segment/SNN` | `04_feed/segments/SNN/{prompt.txt, prompt.md, refs.json}` + `E0N.md` 定段号 | 段数 0 | P4 |
| **资产页** · `/api/assets` | `02_assets/IMAGE_PROMPTS.json`（+ 真实图片可选） | 角色/场景/道具三页全空 | P2 |
| **人物角色页** · `/api/characters` | `02_assets/CHARACTERS.json`（**不是** IMAGE_PROMPTS.json） | 人物卡全空、`registered:false` | P2 |
| 改图需复核标记 | `02_assets/ASSET_LINKS.json` | 只显示出场段，不标「需复核」 | P2 |

- **段号规则**：`SNN` 中 `NN = (集序-1)*6+1 … 集序*6`（E01→S01~S06）。可在 `_tmp/seg_map.json` 自定义。
- **M1 铁律**：图还没生成也要写 `IMAGE_PROMPTS.json` 和 `CHARACTERS.json`——资产页会显示 `exists:False` 的「待出图」卡可点开改词；人物页的 `registered` 角色**不依赖图片存在**就显示。⛔ 不要等图生成后才登记。

#### ② 症状 → 根因 → 修法速查

| 症状 | 根因（按命中概率排序） | 修法 |
|---|---|---|
| `/board` 全部空、episodes_total=0 | 稿子放在 `04_feed/compiled/` 等非约定目录 | 按①落 `01_script/episodes/` + `04_feed/segments/SNN/` |
| 资产页三分类全空 | 没写 `IMAGE_PROMPTS.json` | 写它，key=资产相对路径，值含 name/prompt/kind |
| 资产有卡但点开提示词空 | `IMAGE_PROMPTS.json` 的 key 与实际路径对不上 | key 用真实相对路径；`regenerable` 由 key 命中决定 |
| 人物角色页空、`registered:false` | 没写 `CHARACTERS.json`（误以为资产页有人物卡就够） | 按下方「人物角色页数据源铁律」显式登记 |
| 人物页只显示「自动发现」裸图、无性格造型 | 角色未登记，走了 auto 分支；且 M1 图未生成时连 auto 都不触发 | 在 `CHARACTERS.json` 显式登记，填 identity/personality/appearance/outfit/voice |
| 段有了但 `shot_count=0` / 分镜卡空 | H3 无 `[mm:ss]` 行，且 `prompt.md` 分镜卡时码列写成了 `00:05.000` | 时码列改纯数字范围 `0-5`，列序 ≥6 列（官方切点 `At MM:SS.mmm` 写进镜头描述列） |
| 同一镜号被算两次 | 官方 I2VA 指令行 `(from [Shot 1]) is fully referenced` 被当成正文镜 | 解析器按镜号分组取最长文本；`non_diegetic_music` 里的 `at [Shot N]` 引用也要排除 |
| 改完稿子 /board 仍是旧的 | 浏览器/中间层缓存 | 后端 `_send()` 发 `no-store`；前端 `api()` 带 `cache:'no-store'` + `_t=Date.now()`；空闲 8s 静默刷新 |
| **本地替换图片后人物/资产卡片仍显示原图** | ①卡片 `<img src="/file/路径">` **没带时间戳**，浏览器按 URL 缓存旧图；②替换成功回调只 `refresh()`，而 `refresh()` 不重渲染人物/资产页，DOM 还是旧的 | 前端所有展示图统一走 `imgUrl(path)` = `/file/路径?t=Date.now()`；替换/回滚/后台生成完成回调里调 `refreshImageViews()` 重渲染 characters/assets/episodes |
| **点人物图片/放大按钮完全没反应** | ★头号根因：`onclick` 里写了**模板局部变量**，如 `onclick="openLb(imgUrl(img.path),...)"`——`img/a/p/x/d` 只在 JS 模板字符串求值时存在，渲染完成后点击执行 onclick 时这些变量已不存在 → 浏览器抛 `ReferenceError`，点击静默失效。次要：灯箱 z-index 不够被盖 | 模板里必须用 `${...}` **在渲染时把 URL 算成字符串字面量**：`onclick="openLb('${imgUrl(img.path)}','名字','image')"`（注意外层单引号）。⛔ 禁止把 `img.path`/`a.path` 等变量直接写进 onclick。灯箱 `#lb` z-index 9999；图片区右下角加显式「🔍 放大」角标。验证法：Node vm 渲染卡片后检查 onclick 是否含 `openLb('/file/…','…','image')` 字面量、无未定义变量 |
| **生成的角色图"没有脸"** | 四格立绘板提示词里「②③④面部不刻画五官」重复 3 次、把「唯一清晰脸只在①格」压下去 → 模型把 4 格全画成无脸。且四格板本就是**锁一致性的工程资产板**（1清晰脸+3无脸全身），不是给人看的角色照 | 四格板：把「第①格【面部特写·全图唯一清晰脸】+五官逐项」前置写强，无脸措辞合并成一句、不重复。若用户还要单张清晰脸作 H3 参考，可另出 `图N_名_主视觉.png`，**但只作附加参考（anchor slot=`face`），绝不当角色卡主图** |
| **脸被裁掉一半 / 只有侧脸 / 人还是丑** | ①写「**头部填满该格**」→ 模型把头撑到溢出画框 → 头顶或下巴被切；②写「**侧光从右侧斜入**」「侧逆光」→ 模型理解为侧光照脸 → 直接给侧脸；③只写五官、不写朝向 → 模型自由偏头；④没有爆款颜值锚点、还过度磨皮 → 塑料网红脸 | 按 `asset-image-prompt-bank.md` **§四·五 爆款短剧颜值锚点库**：①**正面三连**（身体正对镜头＋面部朝正前方＋双眼直视镜头＋鼻尖对中线）；②**完整入画＋四缘留白**（头顶到下巴全在格内，禁「填满」）；③**主光必须正面**（左右对称、无半边阴影，禁侧光/侧逆光/斜入照脸）；④颜值锚点**只选一型**（男主 A/B/C、女主 A/B/C）取骨相+眉眼+鼻唇+皮肤发质，附「保留毛孔不过度磨皮」 |
| **角色卡上的图看不清脸 / 就是丑（提示词全对也没救）** | ★**UI 尺度才是元凶**：`.char-card` 图区原为 `120px` 宽，四格板塞进去每格仅 30px，脸只有几十像素——提示词改十版也看不出好坏。这是"丑"里比提示词更致命的一层 | ①图区 `120px→190px`、卡片 `minmax(300px)→minmax(430px)`、`min-height→380px`；②图上加 `pic-kind` 角标、锚点条按钮中文化（角色卡／四格板）；③⛔ 禁 `find(a=>a.exists)` 无差别挑第一张（"谁有图谁上位"= 形态乱源），改为按 slot 固定优先级 |
| **同排角色卡形态不一致（一个四格板、一个单张人像），用户说"图和其他两个都不一样"** | 四格板是 4 格挤一张的**工程板**（脸仅占整板 2/5 宽），单张主视觉是正常人像——两种东西并排必然割裂 | ★**定版规则（2026-11-20 用户拍板）：角色卡主图统一固定取 `anchors.full`（四格立绘板），三角色形态必须一致**。<br>①`charCard` 主图 = `(full&&full.path)?full:(face||{})`，⛔ 禁 `find(a=>a.exists)` 无条件挑图；<br>②四格板是 1:1 方图，图区宽度即显示边长（230px），卡片 `minmax(460px,1fr)`、图区 `min-height:230px`；<br>③`pic-kind` 角标按 slot 输出「四格立绘板／角色卡」；④定版后**不再自行切换形态**，要改先问用户 |
| **人物角色页多出一条空壳卡片（"待补"、无提示词、无出场、"参考图待出图"）** | ★`build_characters()` 的 **auto 分支**：扫 `02_assets/characters/**`（`rglob`，**不跳过 `_tmp`/`SKIP_DIRS`**），凡未被任何角色 `anchors` 声明引用的图片，都会被打成一个 `registered:false` 的**伪角色**。命中条件：文件名不在 declared 路径串里。典型来源：改名后的旧图、单张主视觉、裁切中间产物、新建未登记图 | ①**每张角色图必须被某个角色的 `anchors` 引用**，否则就是伪角色；②不用的图**直接删**，或移到**项目根 `_tmp/`**（`build_assets` 的 `SKIP_DIRS` 才认 `_tmp`，`characters/_tmp` 无效）；③`_bak.png` 已被 `BAK_RE` 过滤、不会成伪角色，但干净的活仍建议删；④清理后必查 `/api/characters` 的 `人物数` 是否等于真实角色数 |
| **资产库/角色页越用越乱，一堆临时文件与旧备份** | 重生备份 `_bak.png`、`IMAGE_PROMPTS.json.bak-*`、生成任务临时 `导演台数据/临时文件/imgprompt_*.txt`、裁切中间图都会堆着；`build_assets` 用 `os.walk(ROOT)` 几乎全扫（只跳 `SKIP_DIRS` 与 `_bak`） | 交付前跑一次清理：删 `02_assets/**/*_bak.png`、`02_assets/*.json.bak-*`、`导演台数据/临时文件/*`、裁切中间图；`导演台数据/历史快照/` **保留**（历史对比/回滚要用），可定期只留最近 N 份 |
| **改完提示词，过一会儿又变回旧版（改几次都没用）** | ★`do_regen_image()` 生图成功时调 `save_image_prompts(lib)`，而 `lib` 是**任务提交时**加载的快照——**每有一个生图任务完成，就用旧快照把整份库写回**，把这期间手改的其它条目一并冲掉（实测把知夏新版冲回旧版两次） | ①已修：保存改为**读最新盘 → 只更新本条 `last_generated`**，其它条目不动；②排查法：改完立刻读回校验长度/关键词，并看 `os.path.getmtime` 是否在几秒后被改写；③**批量生图任务在跑时不要手改配置**，等任务全部 success 再改；④怀疑被覆盖时重启导演台进程，排除内存态 |
| **后台任务浮层一直挂在右下角 / 操作时不停弹提示** | ①`renderJobs()` 取 `slice(-6)` **不看状态**，历史 done/failed 也一直显示；②轮询结束还 `toast('后台任务完成')`；③空闲自动刷新 8s 全量 `refresh(true)`，反复重建 DOM | ①`renderJobs` **只显示 running/queued**，全部结束立即收起浮层；②任务完成**不弹 toast**（浮层消失+图片自动更新即反馈）；③自动刷新 `8s→30s`，并加三道闸：`POLL` 在跑跳过、`document.hidden` 跳过、`DIRTY`（正在编辑未保存）跳过；④`refresh(silent)` 遇 `DIRTY` 只更新浮层、**不 renderTree/不清缓存**，护住用户正在输入的内容 |
| **角色卡一排里形态不一致（一个四格卡、一个单张人像），用户说"变来变去"** | ★根因：`charCard` 用 `anchors.find(a=>a.exists)` **动态挑第一张存在的图**——某角色生成了主视觉单图、另一角色只有四格卡，同一排就出现两种形态；叠加此前把 anchors 顺序改成 face(主视觉) 优先，更乱 | **角色卡主图固定取 `slot==='full'`（四格立绘板）**，⛔ 禁止用 `find(a=>a.exists)` 动态挑；`full` 缺图 → 显示「四格角色卡待出图」占位（带「✎ 提示词」按钮），不要把别的 slot 图顶上。**角色卡唯一标准形态 = 四格立绘板**；主视觉/单图只放锚点条供参考。⛔ 改角色卡形态前必须先告知用户确认，禁止静默切换 |
| **生成的图"太丑"（构图呆板、光线平淡、像证件照）** | ★根因两条：①**没查 `asset-image-prompt-bank.md` 成品库**，手写成"一位X岁男性…全图4格…纯白背景"的清单式短句；②**正向描述里堆否定词**（"不设独立主图、不重复视角、不出现第5格"）+ 10 余条 Negative prompt——而成品库明令"少用否定词，写『不要眼镜』反而给眼镜" | ① **P2 写角色/场景/道具出图提示词前必查成品库**（`asset-image-prompt-bank.md` §2.2 五条范式 + §3.1 十段维度），照十段骨架填：机位与透视→主体位置→五官与视线→服装材质→**光线方向/光比/高光落点**→色彩系统（主/辅/点缀）→背景几何→**前景-中景-背景三层**→情绪定调→后期质感（焦段/颗粒/肤质）。② 正向描述**只写正向**；总数声明写"全图共4格、横向并排"（正向），**不写**"不设主图/不出现第5格"；Negative prompt 独立字段、精简 3~5 条防硬伤即可。③ 成品机检：`check_asset_blocks.py` 要的指纹（全图共4格/无脸全身/五官10项/音色速览标签）保留在归档 md，纯净可投喂版落 `IMAGE_PROMPTS.json` |
| **图片编辑器里点"当前/备份"看图后整个编辑器消失** | 编辑器内容塞在 `#lbbox`，而缩略图 onclick 用了主灯箱 `openLb()`——它重写 `lbbox.innerHTML`，把编辑器 DOM 直接覆盖成一张大图，看起来像退出弹窗 | 查看大图走**独立灯箱** `#zoomlb` + `zoomLb()/closeZoomLb()`，不复用 `lbbox`；缩略图 onclick 加 `event.stopPropagation()` 防冒泡关层。点大图本身不关（zi.onclick stop），点背景才关 |
| **图片编辑器里预览图显示不全/被裁** | `.ie-preview` 写死 `height:430px`+`overflow:hidden`，宽幅四格板塞进 300px 窄框，`object-fit:contain` 显示很小像被切 | 预览框宽 300→380px、固定高→`min-height:240px;max-height:70vh;overflow:auto`，编辑器整体加宽到 `min(1200px,96vw)`；预览图 `max-height:68vh` 可点开大图细看 |
| H3 提示词模型不听台词/口型乱 | 用了自造格式（伪 `[STYLE]` 块、中文括号语气、裸引号台词） | 按官方 `h3-prompt-writing`：`(Sx)` + `<d>[Chinese] 逐字原文</d>`、`[Shot N] At MM:SS.mmm, the camera cuts to` |
| 看板一堆「未解析到时间戳 / 未声明模型版本」假 WARN | 看板编译器只认 Seedance 时码 | 已修 `build_board_lite.py` 原生支持 H3；若仍报说明稿子没走 H3 三段字段 |

#### ②·补 图片代码五查清单（改 `director_ui.html` 图片相关代码后逐条过）

> 由来：同一批图片代码连踩 5 类坑（无时间戳/变量泄漏/灯箱复用/固定高裁切/缺放大入口），逐点修会修一处漏一处。改成**五查法**，每次动前端图片代码全表过一遍。

| # | 查什么 | 合格判据 |
|---|---|---|
| 1 | **URL 时间戳** | 所有展示图 `src` 与放大 URL 一律经 `imgUrl(path)`（含 `?t=Date.now()`）；⛔ 不许手写 `src="/file/${x}"` 或 `'/file/'+p`（缓存旧图）。视频可用裸 URL 但全屏放大也走 `imgUrl()` |
| 2 | **onclick 变量泄漏** | onclick 属性里**不得出现模板局部变量**（`img.path`/`a.path`/`p.file`/`x.path`/`d.*`/`r.*`）；必须在模板求值时用 `${imgUrl(x)}` 展开成带引号字面量 `openLb('/file/…?t=1','名字','image')`。验证：`node` 渲染卡片，onclick 应为字面量、无未定义变量 |
| 3 | **灯箱不复用** | 编辑器（内容在 `#lbbox` 内）里看图一律走**独立** `#zoomlb`/`zoomLb()`；⛔ 不许在编辑器 DOM 内调主 `openLb()`（它重写 `lbbox.innerHTML` 覆盖编辑器）。缩略图 onclick 加 `event.stopPropagation()` |
| 4 | **容器不裁切** | 需要看全图的预览框（编辑器、历史对比）用 `min-height`+`max-height:70vh`+`overflow:auto`；⛔ 不要固定 `height`+`overflow:hidden`。列表缩略图（`.bwframe`/`.eposter`/`.athumb`）用 `object-fit:cover` 裁切是设计，保留 |
| 5 | **放大入口齐全** | 人物/资产/段参考图/分镜画格/封面/历史对比/编辑器预览——**每处图片都可点开放大**；卡片本身若有跳转 onclick（如封面→openEpisode），图片 onclick 必须 `event.stopPropagation()` |

**静态自检命令**（动完前端后跑）：
```bash
# 残留裸图片 URL（应为 0；只匹配 <img>，<video> 的 Range 请求保留裸 URL 是合理的）
grep -nE '<img[^>]*src="/file/' director_ui.html
# onclick 里的模板变量（应为 0；注意排除模板内 ${} 展开的合法写法）
grep -nE 'openLb\(imgUrl\((img|a|p|x|d|r|e|s)\.' director_ui.html
# 编辑器内误用主灯箱（应为 0）
grep -n "zoomLb\|openLb" director_ui.html | grep -E '当前|备份'
```
再用 Node vm 渲染 `charCard`/`assetCard` 等，确认输出 HTML 的 onclick 是 `openLb('/file/…','…','image')` 字面量。

#### ③ 交付前必跑自检（把规则变成机器拦截）

```bash
python scripts/check_director_data.py --root <项目目录>
```

- 逐项检查①的四类数据源是否落盘、`CHARACTERS.json` 的 relations 是否指向已登记 id、`prompt.md` 时码列是否纯数字范围、H3 稿是否用官方 `<d>` 对白。
- **FAIL 非空 = 导演台某视图会空，禁止交付**。修到全绿再交付。
- 与既有门的分工：`check_director_data.py` 管「数据有没有落到工具读的位置」；`validate_prompt.py` 管「提示词语法/模型契约」；`audit_contract.py` 管「交付件结构指纹」；三者互不替代。

---

**资产落盘铁律（2026-11-20 · 治「导演台资产页全空」）**：

> 病根：P2 产出的角色/场景/道具提示词只写进交付 md，没有落盘成导演台读的文件 → `/board` 资产页全空，用户既看不到提示词也无法点开针对性修改。

- **P2 资产提示词必须落盘 `02_assets/IMAGE_PROMPTS.json`**，格式为 `{相对路径: {name, prompt, kind, last_generated}}`，`kind` ∈ `character|scene|prop`。key 的路径前缀决定资产落在导演台哪个分组（`02_assets/characters/`→角色、`/scenes/`→场景、`/props/`→道具）。
- 图还没生成**也要写**：导演台会把 `IMAGE_PROMPTS.json` 里有提示词但磁盘无图的条目显示为 `exists:False` 的「待出图」卡片，可点开改词、直接生成。⛔ 不要等图生成后才写提示词。
- 场景 `prompt` 必须含**母版 + 3×3 九宫格 8 字段**（摄影机矩阵/参考锁定模式/标注降级条款等），角色 `prompt` 必须含**四格无脸+五官10项+Voice Description+负向词**，道具 `prompt` 含四格视角+禁手持+negative prompt。
- **分镜卡表格列契约**（导演台 `parse_shots_table`）：写进 `04_feed/segments/SNN/prompt.md` 的表格时码列须为纯数字范围 `0-5`（不是 `00:05.000`），列序 ≥6 列：镜号/时码/景别/镜头描述/动作画面/台词，否则 `shot_count=0` 看似无数据。官方 H3 切点 `At MM:SS.mmm` 写在「镜头描述」列里保留。
- `04_feed/segments/SNN/refs.json` 的 `pictures` 槽位 `file` 填 `IMAGE_PROMPTS.json` 里对应的相对路径，让参考图槽位能点到资产。

**人物角色页数据源铁律（2026-11-20 · 治「人物角色页空」）**：

> 病根：导演台有两个不同的视图——**资产页（`/api/assets`）读 `IMAGE_PROMPTS.json`**，**人物角色页（`/api/characters`）读 `02_assets/CHARACTERS.json`**。只写前者，资产页有人物卡但人物角色页仍空。且 `build_characters()` 的「自动发现」分支只扫磁盘上**真实存在的图片**（`IMG_EXT`），M1 形态下图未生成（`exists:False`）时一个都不列 → 必须**显式登记**。

- **P2 人物必须落盘 `02_assets/CHARACTERS.json`**：`{characters:[...], relations:[...]}`。每个角色含 `id / name / role / rank（主角|配角|反派|群像）/ identity / personality / appearance / outfit / voice / note / anchors`。`anchors` 用 `face / full / outfit` 等键，值填 `IMAGE_PROMPTS.json` 的 key（相对路径）——这样人物卡的锚点才能带出提示词、显示「✎ 提示词」并可改。
- `relations` 的 `from/to` 必须是已登记角色的 `id`，否则被丢弃并在界面标注条数。任务类型填 `ally / antagonist` 等。
- 登记后的角色**不依赖图片是否存在**就会出现在人物角色页（`registered:True`），正好覆盖 M1「提示词已写、图未生成」阶段。
- 建议同时落 `02_assets/ASSET_LINKS.json`（资产相对路径 → 出场段 ID 数组）：决定改图后哪些段被标「需复核」；未登记时只回退显示出场段，不会标复核。

---

## 二、命名规则（硬约束）

| 对象 | 规则 | 例 |
|---|---|---|
| 目录（生产层 00~07） | 两位数字前缀 + 小写英文 + 下划线 | `02_assets/characters/` |
| 目录（工具层） | **中文直述功能**：`导演台/`、`导演台数据/` | `导演台数据/历史快照/` |
| 文件（工具层） | **中文直述用途**：`启动导演台.bat`、`使用说明.md`、`安装清单.json`、`说明.md` | `导演台/安装清单.json` |
| 分集 | `E` + 两位数字 | `E01.md`、`E12.md` |
| 分段 | `S` + 两位数字，每段独立目录 | `04_feed/segments/S03/` |
| 镜号 / 爽点 | 沿用包内既有编号 | `PAY-07`、`镜 03` |
| 版本 | 文件名后缀 `_vN` | `E01_v2.md` |
| 临时文件 | 一律放 `_tmp/`，交付前清空 | `_tmp/board_draft.html` |

**为什么生产层保持英文、工具层用中文**：`00_source`~`07_reports` 与 `clips/`、`jobs/` 被 ffmpeg、ComfyUI、H3 runner 等外部程序按英文相对路径读写，改名会断链；而 `导演台/`、`导演台数据/` 只由本包脚本按相对路径解析，中文名更直观，风险可控。

**中文路径的编码约定**：`启动导演台.bat` 以 **GBK** 写入（中文 Windows 的 cmd 按 ANSI 936 读批处理，用 UTF-8 会乱码），首行 `chcp 936` 兜底；脚本内部调用一律走 Python 的相对路径，不拼中文命令行参数。

⛔ **禁止**：根目录直接放剧本、`新建文件夹`、`final_final.md`、把 SRT 丢进 `06_delivery/` 以外的散落位置；⛔ 也禁止给生产层目录起中文名（会断外部程序的路径）。

---

## 三、与包内既有机制的接线

- `04_feed/segments/SNN/` 即「每段一个文件夹」的投产包，与 H3 线（`04_feed/segments/SNN/prompt.md` + `SNN.srt` + `refs.json`）和 Seedance 线共用同一结构；
- `02_assets/` 里的图号与 `《素材接线单》` 编号**双向一致**（M1 编号占位，本包不持图）；
- `05_qc/consistency/` 与 `redfruit-delivery-spec.md` §六 台账同源，不另立一套；
- `07_reports/` 只放看板与报告，⛔ 不放交付件。

---

## 四、初始化与自检

```bash
python scripts/init_project_tree.py --root D:/short-drama/我的剧
python scripts/init_project_tree.py --self-test
# 只补/更新导演台（接手已有项目、或技能更新后）
python scripts/install_director_console.py --root D:/short-drama/我的剧
```

脚本幂等：已存在的目录与文件不覆盖；`--force` 才重建 README 与 `project_state.json` 骨架。
建树时**自动安装导演台**（`导演台/` + 启动脚本），失败只告警不中断。

**验收**：`init_project_tree.py --check <root>` 输出 `OK` 才算目录合规；任何缺目录都会点名列出，便于补建。
导演台单独验收：`install_director_console.py --root <root> --check`（文件与技能版本不一致即 FAIL）。
