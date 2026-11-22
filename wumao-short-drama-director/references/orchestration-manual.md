# 编排手册（Orchestration Manual）

> 从 `SKILL.md` §五 拆出的三块**执行编排细则**（按已确认的中文短剧画幅、导演台与先审后拍约定执行）：强制读取清单 / 按需规则文件·触发条件台账 / 极速直出模式。
> **触发即必读**：进入 P1 之前先读 §1；任一按需文件的触发条件成立时，立即读 §2 对应行并打开该文件。

### ★ 强制读取清单（每个阶段动手前必读 · 治「子技能只挂名不执行」）

> **病根**：**「自动路由」并不会真的自动发生**——SKILL.md 是被读到才生效的文档，不是运行时代码。不显式读子技能文件 = 该层规则不存在。
> **铁律**：下表列出的文件，**动手写该阶段产物前必须实际读取**（不是凭记忆、不是凭总控摘要）。读完再写，缺一即视为该阶段未执行。
> **预算现实性（必读）**：P3 文戏路径若按全量列读合计约 **12 万 token**，而 §预算铁律 自定「单批 ≤8000 token」——**必读量比预算大 15 倍，物理上读不完**。故各阶段只列**最小必读集**，其余走《按需规则文件 · 触发条件台账》现查。**打戏段仍须按档全量读本档核心库**（不可切片）；非打戏段不要求通读打戏库。
>
> ⛔ **不设摘要层（2026-10-13 用户裁定 · 原「运行态微核」已整环移除）**：本包曾编译过一份 `agent-system-core.md`（运行态微核）作为压缩入口，**已删除**。原因：它的速查表部分是**手写副本**、不随全库自动同步——2026-10-13 改锁后它仍输出旧口径（C「不阻塞」/ I「可默认」），**而它排在原文之前、又被指定为「先读」→ 成了执行者读到的第一口径，直接导致锁被跳过**。
> **现行铁律：一律读原文。** 下表文件**必须实际打开读到**；⛔ 不接受任何形式的摘要 / 压缩稿 / 编译产物替代原文——**摘要的位置越靠前，它漂移时的害处越大**。

| 阶段 | 触发时机 | **必读（最小集 · 显式读取）** | 该阶段硬产出（漏 = 未执行） |
|---|---|---|---|
| **P0·1** 素材来源 | 任务最开始（先于一切创作） | 总控 §〇·1；③④ 读 `sd-recon-engine/SKILL.md` + `source-ladder.md` + `recon-evidence.md`（成卡时加读 `intel-card.md`） | 素材来源回显 + **写入 P0A 基准表**；③④ 另出《对标情报卡》并经用户确认后才进 P1 |
| **P0A** 立项 | 〇·1 锁定后 | 总控 〇节（锁）+ `asset-first-pipeline.md` + **`asset-delivery-modes.md`（素材形态 M0/M1/M2 判定 + 接线单）** + 项目导演台既有安装/接入说明 | 锁回显（〇·1 / A/B/C/D；**中文短剧 B=9:16 已确认，回显不重复问**）+ P0A 基准表（含素材来源、素材形态）+ 每项目独立导演台接入记录及安装 check 实际结果；默认 M1，明确纯文字降 M0，实际素材可访问并登记后升 M2（授权/锁定/视觉核验另记） |
| **P0B** 决策 | 分镜前 | `sd-decision-engine/SKILL.md` + `context-mapping.md` + `emotion-anchor-table.md` + `forbidden-zone-whitelist.md`（★构图雷区 A/B 双态白名单） | 情绪锚点表（情境 ID + 80/15/5 锁定机位组合 + 构图雷区 A/B 清单） |
| **P1** 剧本 | 素材来源锁定后（③④ 须先出情报卡） | **⓪ ★改编决策环（〇·1 = ② 改编时必读）：总控 `references/novel-to-shortdrama-adaptation.md`**（剧情理解三张账 → 爽点表 → 主动取舍 → 每集钩子矩阵；6 条冲突裁决）＋ `sd-script-engine/SKILL.md` + `six-stage-pipeline.md` + **`dialogue-naturalization.md`（台词拟人化引擎：称呼表 / 书面→口语对照 / 撒碎屑四法 / 认症表 / 阶段⑤ 过站）+ 总控 `dialogue-doctor-7d.md`（台词七维诊断 · 定稿前体检）**——前者管「怎么写」、后者管「哪里不对」，缺任一即台词必机械；按需 `roundtable-review.md`；输入是成型外部剧本时先读 `external-script-polish.md` | 可追溯分集剧本 + 无爽点捧杀；外来剧本另出 `POLISHED_SCRIPT.md` + `POLISH_CONFIRM_CARD.md` + `POLISH_FINDINGS.md` |
| **P2** 资产 | 剧本就绪后 | **⓪″ ★造型锁环（小说人物转形象 / 用户要真人质感时必读）：总控 `references/character-visual-style-lock.md`**（L1~L4 档位须用户确认、男女主同档配对、九槽位逐槽填实值；✅ 公开穿搭图造型参考见 §〇、⛔ 造型全文禁进 P4）＋ **⓪′ 出图成品库：总控 `asset-image-prompt-bank.md`**（写资产出图提示词前查对应类别，执行下文「成品库优先」）＋ `sd-asset-engine/SKILL.md` + 必读 `sd-asset-engine/references/scene-grid-template.md`（九宫格）· `character-portrait-templates.md`（立绘）· `prop-template.md`（道具）+ 总控 `asset-spatial-ledger.md` §四（场景出图分工 + 空间事实五件事含**年代锚 ERA_ANCHOR**）+ 剧本层《世界锚卡》《人物锚卡》随 HANDOFF 交接 + `asset-delivery-modes.md` | 按形态产出（M0 外观档案复述块 / **M1 出图提示词 + 图号 + 接线单** / M2 实际登记并分记授权/逐批锁定/视觉核验；授权生成优先本地，沿用已有范围，不逐张重复索权）；三清单；每场景坐标系与 SET_STATE 状态变体；每角色年龄锚+体型锚+身份外观（C26c/C26d）；**九宫格提示词须含 8 字段**（内容分配/锁定模式/摄影机矩阵/摄影机参数/光照曝光/标注要求/画面纯净/风格分支）；**场景母版与九宫格两类都出、互不替代**；写完必跑 `check_asset_blocks.py` FAIL 清零 |
| **P3** 分镜 | 按形态的文字/编号/素材依据就绪后（缺图不阻断文本编排） | **⓪ ★表演环：总控 `references/acting-direction.md`**（不读＝表演层未启动）；**⓪′ ★成品短语环：总控 `references/expression-motion-prompt-bank.md`**；**⓪″ ★运镜环（按需）：总控 `references/camera-movement-prompt-bank.md`**（打戏 / 追逐 / 转场 / 特效镜头 / 反馈「画面像 PPT」时读 · 引擎 `expression_motion.py --camera`）（镜行表演位要把情绪/动作落成中文成品短语时读 · 特写·3D CG·打戏·双人戏·前 3 秒钩子·人物出场必读 · 引擎 `scripts/expression_motion.py`）；**① 调度环** 总控 `blocking-direction.md`（先建坐标系→摆位→节拍闭环→权力几何→道具账→定镜头策略）；**② 分镜环** `sd-storyboard-engine/SKILL.md` + `short-drama-camera-system.md` + `shot-economy-and-acting.md` + `scene-space-adaptation.md` + `segment-linkage.md`；**③ 图形化环** `storyboard-sheet-template.md`（★故事板图 + SHOT_TEXT 卡）+ `plot-deduction-grid.md`（★剧情分镜格 · **条件必出**）；**④ 穿帮防治环** 总控 `blooper-prevention-playbook.md`（C35/C36/C37 权威 · 写画面主体/站位声明/禁止项前必读）；**打戏按档全量读本档核心库，禁只读引擎 SKILL.md 与招式库**——R1 `sd-real-engine`：`r1-combat-core.md` + `kinetic-chain-11.md`〔11 环动力链〕+ `defense-evasion-rules.md`〔防守三态〕+ `impact-physics.md`〔受击物理〕+ `camera-action-specs.md` + `render-adapters.md`；R3 `sd-xuanhuan-engine`（**xuanhuan-combat-director V2.6.0 Ultimate 全量 9 份库强制必读**）：`core-combat-laws.md` + `camera-specs-15modes.md` + `close-quarters-engine.md` + `xuanhuan-elements-vfx.md` + `grand-scale-domains.md` + `arsenal-moves-library.md` + `arsenal-parameter-library.md` + `character-scene-presets.md` + `epic-battlefield-protocols.md`；R2 `sd-combat-engine`：`combat-iron-laws.md` + `combat-construction.md` + `eight-sentence-masters.md` + `combat-rhythm-and-load-guardrails.md` + `impact-frame-and-banlist.md` + `vfx-rendering-mandate.md`；其余按需查各引擎 SKILL.md | 《角色表演档案》（每主要角色一份 · 五支柱 + Voice 声线锁）+ 逐场节拍表 + 文字平面图与站位声明 + 分镜稿 + 故事板图提示词（CLEAN_GRID）+ 剧情分镜格/豁免理由 + 群像声明；写进 **P3 图形化交付清单**，**禁静默跳过** |
| **P4** 投喂稿文本装配（不生成） | 分镜定稿后 | **⓪‴ ★质量环（出稿后、交付前 · 按需）：总控 `references/prompt-quality-enhancement.md`**（C 码 FAIL 清零后跑 `prompt_quality_audit.py` 八维体检、看建议不凑分、⛔ 不自动改稿）＋ `sd-feed-engine/SKILL.md` + `feed-mode-and-gates.md`（投喂层闸门 · 含与 C 系的分工表）+ `asset-mapping-and-rules.md` + 总控 `model-adapters.md` §5（七段式唯一权威）+ `segment-splicing.md`（D 锁）+ `prompt-feeding-checklist.md`（§〇·补 8 项）+ `blooper-prevention-playbook.md`（投喂镜行穿帮面） | 七段式投喂稿 + 投喂层闸门与 C 系机检**合并报告**（一次 `gate_check.py` 出）+ 台词完整性对照记录 |
| **P5** 出稿质检 | 投喂稿完成后（不代表成片验收） | `sd-qc-engine/SKILL.md` + `machine-check-manual.md` + `continuity-ledger.md` + 总控 `asset-delivery-modes.md`（按形态改判一致性门）+ 跑 `validate_prompt.py`（**多段稿一律加 `--by-segment`**）+ `check_asset_blocks.py` | 连续性台账（含素材形态字段）+ 机检报告（FAIL 清零）+ 看板；M0/M1 一致性门改判为「与文字档案一致」，禁称图像级核验；M2 仅实际登记，须具备视觉能力并实际查看才记录图像核验，否则标未视觉核验 |
| **交付标配**（别名 P4.5 · 默认必出 · CT5-P45 条件门） | 每次 P4 交付后 | `sd-storyboard-engine/references/p45-previs-storyboard.md`（★唯一权威） | `{项目名}-预演故事板.md` 独立文件：一段一节 = 「本段要验什么」+ 故事板提示词 + 「看图先看这三点」；**⛔ 只出提示词、不出图**，不入册、不占槽；交付清单须列「预演故事板：段n~段m ✅ / ⛔未附（理由）」；与 P3 故事板图（生产资料）**禁互相替代** |

#### 成品库优先（P2–P4 默认执行）

- **P2 资产与定妆**：写角色、场景、道具的出图提示词前，先查 `asset-image-prompt-bank.md` 的适用类别。角色服饰、妆发和配饰同时按 `character-visual-style-lock.md` 的九槽位确定。适配已确认的年代、身份、材质和画风，并填入对应的正式资产模板。静态出图范式只用于资产层。
- **P3 表演与运镜**：确定本镜的叙事任务后，先从 `expression-motion-prompt-bank.md` 查找符合情绪、景别和动作阶段的短语，从 `camera-movement-prompt-bank.md` 查找符合镜头动机的表达。可用 `scripts/expression_motion.py` 按需检索。匹配时优先保留库中具体、可见的画面措辞，只调整人物、道具、视线、幅度与节奏等必要取值。固定机位、留白和简短反应按剧情需要保留。找不到合适条目时按本镜需求原创，无须凑使用数量。
- **P4 模型适配**：优先继承 P3 已选定的表情、动作和运镜表达，检查是否实际写进对应镜行。Seedance 按相应版本保留合适的中文画面措辞，H3 按 `h3-adapter.md` 转述为对应字段的英文技术描述，中文对白照常保留。预检以当前人物状态、连续性、镜头时长和所选模型约束为准。
- **内部复核**：在已有资产或分镜工作记录里简记实际采用的条目编号或名称及适配点，便于返修。无匹配时可简记原因。记录留在工作底稿，成品提示词只保留模型需要的描述。

**导演台与实际生成衔接**：每项目使用独立导演台；P0 按既有安装/接入说明执行安装 check，记录实际结果，不杜撰命令或冒称已安装。P4 只装配文本，P5 只做出稿质检；随后提交导演台审阅，**保存、签审均不触发生成**。取得明确出片授权后，按已有范围优先本地生成，不重复逐张索权；调用前核查必需素材的真实文件、路径、版本与锁定状态，缺项必须阻断实际生成并列出待补项，文本编排可继续。资产生成授权不代替出片授权，M2 登记不代替任何授权或视觉核验。实际成片另做成片验收，不能沿用文本机检结果冒称成片通过。

**自检动作（AI 助手在每阶段开始时执行 · 含【外挂激活回执头】硬门）**：在内部确认「本阶段必读文件已读」，再开始产出。**上下文不足以全文读取时，必须至少读取该文件的模板/字段结构部分**——模板字段是硬约束，不可用印象替代。

> 🔒 **【外挂激活回执头（Execution Receipt）】（2026-10-14 新增 · 专治 AI 偷懒跳读子技能）**：「内部确认已读」看不见＝可被静默跳过。**凡挂载子技能产出的分镜稿（P3）与投喂稿（P4），文档顶部除声明 `> 素材形态：M0/M1/M2` 外，必须紧随输出三行【外挂激活回执头】**，并从实际读取的子技能文件里摘出本次选用的具体专属条目名（未读文件绝对填不出真条目）：
> ```markdown
> > 素材形态：M1（编号占位）
> > 激活外挂：sd-real-engine（R1 写实档）+ sd-decision-engine
> > 已读子库：kinetic-chain-11.md / defense-evasion-rules.md / impact-physics.md / forbidden-zone-whitelist.md
> > 本段调用外挂指纹：【动力链：蹬地→拧胯→送肩】｜【防守态：格挡卸力+偏头闪避】｜【情绪锚点：E04 压迫对峙】
> ```
> **跨阶段卡片交接铁律**：① P0B《情绪锚点表》锁定的 80% 核心机位组合与雷区白名单必须在 P3/P4 镜行头落地；② P3《角色表演档案》的 **Voice 声线锁**必须貼入 P4【核心人物】行尾（C30c），**Business 身体任务**与「**然而当 X**」破功反应必须落入对应镜行；③ P3《故事板图》七态动作相位必须逐格对应进 P4 投喂镜行。

### 切片器加载路由核准说明（仅加载规则）

- **权威与最小集**：上述阶段表管阶段必读；本手册触发台账与各子技能索引管条件必读。`slice_context.py` 是原文路由工具，不代替规则权威。P3 补齐 `scene-space-adaptation.md`、`segment-linkage.md`、`blooper-prevention-playbook.md`；P4 补齐穿帮防治、素材形态权威和 `sd-feed-engine/references/engineering-language-cleanup.md`（子技能索引要求封装前必过 §十一）；P5 补齐素材形态权威。已有台账/开发圣经等文件保持加载，不能据此声称执行完成。
- **冲突记录与裁决**：P3 表明令 R3 九份核心库全量必读，但下方「子技能 · P3 R3 按需」将其中五份再次列为按需；`sd-xuanhuan-engine/SKILL.md` §二/§四确认九份为本档权威，§五则描述各库的使用时机。加载按本手册强制全读执行，下方索引保留为使用时机提示，不能降级为可跳读。R2 补齐强制表中的 `impact-frame-and-banlist.md`、`vfx-rendering-mandate.md`；R1 六份核心库保持。R2/R3 既有两组护栏保持参考级，不把加载升级为一票否决。
- **模型适用性**：CLI 和 Python 路由只核准 `--model 2.5|2.0`；P0/P3/P4 均加载 `references/model-adapters.md`，两版共用原文，执行时依 A 锁选择版本条款，不凭文件名杜撰版本专属库。未知模型明确报错；H3 仍由 `references/h3-adapter.md` 独立适配，本轮没有核准其跨阶段、打戏及编译器能力，不能把 Seedance 文件清单当成 H3 已支持。
- **来源与预演**：`--source 2 --stage P1` 必加小说改编权威；③④ 在 P0/P1 加采风库（含成卡模板）。P4 默认加载 `p45-previs-storyboard.md` 以判断交付要求与合法豁免；其他阶段用 `--previs` 显式加载。未传 `--previs` 不代表 P4 免交预演，加载也不代表预演已产出。
- **必读与显式触发分开**：`--trigger` 可重复，`expression/camera/crowd/voiceover` 适用于 P3/P4；`dialogue/quality/multi-segment` 适用于 P4；`external-script` 适用于 P1；`visual-style/asset-sketch` 适用于 P2。分别对应下方台账的成品短语、运镜、群像、OS/VO、语速、质量、多段时长、外来剧本、造型、资产速写条件。未传条件不自动加载这些库；打戏指定 R1/R2/R3 时仍须按台账核对是否同时触发成品短语/运镜等内容条件。其他未编码条件（如 FACS、画风锁、技巧转场、多人成战）仍须按台账打开对应权威，禁止宣称脚本已覆盖全部触发条件。
- **素材形态不扩维**：M0/M1/M2 共用 `asset-delivery-modes.md`，按原文改判，不新造各形态独立库；模式参数不构成已核验声明。
- **全量原文与分页**：上文「打戏核心库不可切片」指禁止摘要、节选或只读首页；允许用完整章节无损分页，必须逐页覆盖全文。本页 coverage 仅是本次输出行范围，不能冒充已读、已执行或历史累计覆盖。上下文不足时先读模板也不免除强制全量核心库的后续读取。
- **可追溯输出**：切片清单逐文件输出加载依据、页数、本页范围、未加载范围和缺文件；续页命令保留全部显式触发。缺失文件仍列出，不能用其他文件替代后称已通过。

### ★ 按需规则文件 · 触发条件台账

> **由来**：本包 59 份规则库中**45 个文件不在八阶段必读清单**里。此前**没有任何一处集中说明"这些文件何时读"**——于是形成静默失效通道：**一个文件可以被写进「唯一权威归属表」、标上 ★、画进文件树，却不在任何执行路径上；它照样"是权威"，只是永远没人读。**
>
> **三条铁律**：① 下表所列 = **按需读取**，**「按需」≠「可读可不读」**——**触发条件一旦成立即「必须读」，不读＝该阶段未执行**；② ⛔ **本表之外不得再存在「只标 ★ 而无触发条件」的规则文件**，新增规则文件**必须同步登记本表**（`check_package.py` `[E*30]` 断言强制）；③ **判定权在触发条件，不在「我记得有这条规则」**——凭印象代言＝跳读。**路径一律写全，禁缩写**（缩写会让"挂载"变成"看起来挂载"）。

| 触发类别 | 触发条件（成立即必读） | 必须读取的文件 |
|---|---|---|
| **工程 · 目录与导演台** | 每个新任务 P0 开工 / 交付前验收 | `references/output-directory-spec.md` + `init_project_tree.py --check`；另按项目导演台既有安装/接入说明执行安装 check，登记每项目独立导演台实际状态（目录检查不等于导演台安装通过） |
| **工程 · 看板** | 需要展示或盘点全部资产 | `build_asset_board.py` → 07_reports/board.html |
| **元 · 吸收** | 发现外部好点子、准备改进本包 | `references/skill-evolution-protocol.md` + `absorb_candidate.py` |
| **模型 · H3** | A 锁选 ③ MiniMax-H3 | `references/h3-adapter.md`（官方三段/六段字段 + 原生音频 + SRT；机检 `--model h3` → H1~H6） |
| **交付 · 上架** | P5 交付 / 上架前验收 / 需要 9:16 安全区与字幕规格 | `references/redfruit-delivery-spec.md`（12 项自检 + 跨集一致性台账） |
| **锁 · B** | B 锁画幅锁定 | `references/aspect-ratio-adaptation.md` |
| **锁 · D** | D 锁 ④ 技巧型转场选用 | `references/creative-transition-library.md` |
| **锁 · I（画风锁）** | 用户启用画风锁 | `references/style-bible/` 8 份全读：`style-lock-protocol.md` → `director-to-prompt-protocol.md` → `director-param-library.md` → `style-prefix-blocks.md` → `director-style-catalog-74.md` → `style-fit-and-combat-matrix.md` → `style-archetype-taxonomy.md` → `style-bible-spec.md` |
| **★ 群像行为层** | 调度环标 `群像：A/B` / 用户反馈「背景人呆滞·不动·没反应·像僵尸」/ 公共空间多人同框（教室·食堂·闹市·朝堂·客栈） | `references/crowd-behavior-direction.md` —— 唯一权威：三层闸门（A/B/C 开关 → R/P/S 三型 → C40 条件动检）+ 停顿-恢复曲线 + 投喂层三槽位。**C 类段（密闭双人/打戏/纯特写）不读**，只写 `除 @XX 外无其他人物` |
| **★ 表演层** | P1 写《角色表演档案》/ P3 每场写节拍表 | `references/acting-direction.md` —— 不读＝表演层不启动（人物变成"一副面孔念台词"） |
| **表情层** | 特写 / 微表情 / 情绪关键拍 / 表情易崩镜头 | `references/facs-micro-expression.md`（★权威）+ 按需 `references/facs-au-dictionary.md` / `references/facs-emotion-recipes.md`；文戏情绪递进另加 `references/wenxi-micro-expression.md` |
| **★ 成品短语层** | P3 写镜行表演位 / P4 投喂稿镜行正文 / 需把「情绪 / 动作」落成可直接粘的中文短语 / 特写·3D CG·打戏·双人戏·前 3 秒钩子·人物出场 | `references/expression-motion-prompt-bank.md`（★权威）—— 三条公式 + 429 条成品短语（表情动作 304 + 运镜 20 + 生图 100 + 角色范式 5）；引擎 `scripts/expression_motion.py`（检索 / 组句 / `--annotate` 补两槽）；**只在需要成品中文短语时读，不读不影响决策**（决策归 `acting-direction.md`，面部层归 `facs-*`，站位归 `blocking-direction.md`） |
| **★ 运镜层** | P3 写镜行 `spec` 运镜槽 / P4 写运镜画面描述 / 打戏·追逐·转场·特效镜头·前 3 秒钩子 / 反馈「画面像 PPT、镜头不动」 | `references/camera-movement-prompt-bank.md`（★权威）—— 15 运镜 + 5 基础机位术语桥梁 + 5 条冲突裁决；引擎 `expression_motion.py --camera` / `--formula`。**只在需要运镜成品短语时读**；转场手法归 `creative-transition-library.md`、段内六式归 `camera-transitions-6types.md`、运镜规则与机检归 `camera-specs-15rules.md` |
| **★ 资产出图层** | P2 立项试片 / P2.5 出图提示词 / 角色立绘「写不透」/ 需要风格探路 / 找场景与道具的布光质感措辞 | `references/asset-image-prompt-bank.md`（★权威）—— 六槽速写公式 + 100 条分类素材 + 5 条角色范式十段维度 + 4 条避坑；引擎 `expression_motion.py --list image\|portrait`。**⛔ 产出禁进 P4**；正式资产板三模板与 `style-bible/` 11 槽位仍为上位权威 |
| **★ 小说改编层** | 〇·1 锁 = ② 改编（有原著）/ 用户说「小说改短剧 / 网文改编 / 剧情太平 / 爽点不够」/ 需要判断留哪条线、砍哪条线、把哪个高光提前 | `references/novel-to-shortdrama-adaptation.md`（★权威）—— 三张账 + 爽点表 + 五要件 + 每集钩子矩阵 + 6 条冲突裁决。**触发即必读**；六阶段链 / 钩子账 / 12 节拍仍走各自权威 |
| **★ 角色造型层** | 小说人物转形象 / 妆发服装风格定档 / 男女主同剧风格割裂 / 妆容发型总变 / 用户要「真人质感」 | `references/character-visual-style-lock.md`（★权威）—— L1~L4 男女同档配对 + 九槽位 + 五项统一；✅ 用自备参考图采公开服装图作造型参考（该文件 §〇）；**档位须用户确认**；⛔ 造型全文禁进 P4 |
| **★ 提示词质量层** | 合规机检已过但「画面糊 / 信息薄 / 镜头堆 / 成片像 PPT」/ 长段多镜提示词 / 需要判断稿子够不够厚 / 反馈「提示词写了很多却没效果」 | `references/prompt-quality-enhancement.md`（★权威）—— 八维模型 + 反模式 + 枚举式节拍骨架 + 6 条冲突裁决；引擎 `scripts/prompt_quality_audit.py`。**⛔ 质量层不判 FAIL**；合规仍走 `validate_prompt.py`，七段式仍走 `model-adapters.md` §5 |
| **P0A** | 选运行平台（WorkBuddy / 豆包 / OpenClaw / Dify） | `references/agent-platform-adapters.md` |
| **P1** | 走五阶门控剧本路径（与六阶段链并列） | `references/screenplay-gate-engine.md`；要情绪曲线时加 `references/emotion-beat-curve.md` |
| **P2** | 建《剧组产出册》台账 / 做亲缘遗传推导 | `references/production-ledger-handbook.md` / `references/character-lineage-and-sheets.md` |
| **P3** | 段内切接 / 15 秒规格核查 / 顶视图机位图 / 视听文法核查 | `references/camera-transitions-6types.md` / `references/camera-specs-15rules.md` / `references/spatial-topview-camera.md` / `references/cinematic-dramaturgy-rules.md` |
| **P3 / P4** | 有 OS（内心独白）或 VO（旁白） | `references/vo-os-weaving.md` |
| **P4** | 台词字数 / 语速自检 | `references/dialogue-speed-check.md` |
| **P4** | 多段时长预算 / 三层解耦核查 | `references/seedance-render-engine.md` |
| **P4.5 / 交付标配** | **预演故事板（默认必出 · CT5-P45 条件门；豁免须写明理由）**：单镜过场 / 纯空镜 / 纯字幕段 · 用户明确说不用 · 尚未进入 P4 | `sd-storyboard-engine/references/p45-previs-storyboard.md`（只出提示词不出图，独立 md，不入册不占槽） |
| **P5** | P0/P1/P2 三级质检门禁 / 出看板 | `references/quality-gate-review.md` / `references/storyboard-board-lite.md` |
| **P5 / 复盘** | 用户拿成片来拉片复盘（ffmpeg 抽帧逐格对稿）/ 成片穿帮要求归因到稿 | `references/blooper-prevention-playbook.md`（★权威 · §九 拉片-改稿闭环六步 + §一~§八 归因对照；**根因必须归到「稿子哪句没写死」，不接受「模型问题」**；改稿走三明治序：画面主体→站位声明→禁止项） |
| **交付 · 打包** | 收尾交付 / 合并文档 / 判断「交几个文件」「哪些能进交付稿」 | `references/delivery-pitfalls.md`（件数上限 3 · 正文只放资产＋分镜提示词 · 自包含五条 · 角色 5 格与九宫格八字段 · 交付前五项验收） |
| **题材 · 玄幻大招** | R3 玄幻大招 / 法术特效 | `references/anime-ultimate-vfx-paradigm.md` |
| **题材 · 美学预设** | 选电影级视听美学预设（诗意/纪实/港派/赛博/水墨/国漫） | `references/audiovisual-aesthetic-presets.md` |
| **场景 · 布光** | 日景实拍 / 需防"棚拍假冷光" | `references/lighting-and-antifake.md` |
| **工具 · 工作流** | 用 ComfyUI / Canvas 工作流对接 | `references/comfyui-canvas-automation.md` |
| **工具 · 方言** | 用户点名方言配音（外挂资料） | `references/dialect-voice-control-dictionary.md` |
| **工具 · 安全合规** | 平台安全合规转译（强动作非血腥等） | `references/platform-safety-compliance-guide.md` |
| **项目打包** | 使用 JSON 事实源校验或同源导出时 | `references/project-bundle-contract.md`（先 `project_bundle.py validate`，再 export 到不存在的新目录） |
| **备查** | 超复杂群像 / 多区调度时取法（默认不用） | `references/spatial-reference-system-V3.md` |
| **子技能 · P1** | 来源登记 / 全剧开发圣经与人物锚卡 / 分集规划与场次过渡 | `sd-script-engine/references/source-registration.md` / `sd-script-engine/references/story-bible-and-ip.md` / `sd-script-engine/references/episode-planning.md` |
| **子技能 · P2** | 三清单提取规程 / 场景跨集连续性与人群调度 | `sd-asset-engine/references/three-list-extraction.md` / `sd-asset-engine/references/continuity-and-crowd.md` |
| **子技能 · P3 R1 按需** | 多人战（1vN·三拍轮转）/ 真实搏击技术 / 组合连招 / 19 门传统武学流派 | `sd-real-engine/references/multi-opponent-rules.md` / `sd-real-engine/references/real-fight-techniques.md` / `sd-real-engine/references/technique-combo-library.md` / `sd-real-engine/references/martial-styles-extended.md` |
| **子技能 · P3 R3 按需** | 神魔近身缠斗 / 史诗战场群战协议 / 法宝招式库 / 法宝双轨物理参数库 / 角色场景预设 | `sd-xuanhuan-engine/references/close-quarters-engine.md` / `sd-xuanhuan-engine/references/epic-battlefield-protocols.md` / `sd-xuanhuan-engine/references/arsenal-moves-library.md` / `sd-xuanhuan-engine/references/arsenal-parameter-library.md` / `sd-xuanhuan-engine/references/character-scene-presets.md` |
| **子技能 · P3 R2 按需** | 具名招式库 / 法术体系 / 终极法阵库 / 角色场景预设 / 27 标杆案例句法语料 / 双引擎适配 / 战场速查卡 | `sd-combat-engine/references/moves-library.md` / `sd-combat-engine/references/spell-system.md` / `sd-combat-engine/references/ultimate-array-library.md` / `sd-combat-engine/references/presets-library.md` / `sd-combat-engine/references/syntax-corpus.md` / `sd-combat-engine/references/seedance-dual-engine.md` / `sd-combat-engine/references/combat-cheatsheet.md` |
| **子技能 · P4 投喂扩展** | 工程语言清洗 / 多段连续性策略 | `sd-feed-engine/references/engineering-language-cleanup.md` / `sd-feed-engine/references/segment-continuity-strategy.md` |
| **子技能 · P5 质检扩展** | 剪辑转场与分段门 / 声音设计模板 / 后期音乐与 BGM Cue Sheet / 规则分类与放行裁决 / 阶段验收总表 | `sd-qc-engine/references/editing-transition-gate.md` / `sd-qc-engine/references/sound-design-template.md` / `sd-qc-engine/references/post-music-sound-design.md` / `sd-qc-engine/references/rule-taxonomy-and-verdict.md` / `sd-qc-engine/references/stage-acceptance-table.md` |
| **子技能 · P3 其余** | R1 其余 / R3 其余 / R2 其余 | `sd-real-engine/references/r1-combat-core.md` / `sd-real-engine/references/kinetic-chain-11.md` / `sd-real-engine/references/defense-evasion-rules.md` / `sd-real-engine/references/impact-physics.md` / `sd-real-engine/references/camera-action-specs.md` / `sd-real-engine/references/render-adapters.md`；`sd-xuanhuan-engine/references/core-combat-laws.md` / `sd-xuanhuan-engine/references/camera-specs-15modes.md` / `sd-xuanhuan-engine/references/xuanhuan-elements-vfx.md` / `sd-xuanhuan-engine/references/grand-scale-domains.md`；`sd-combat-engine/references/combat-iron-laws.md` / `sd-combat-engine/references/combat-construction.md` / `sd-combat-engine/references/eight-sentence-masters.md` / `sd-combat-engine/references/vfx-rendering-mandate.md` / `sd-combat-engine/references/impact-frame-and-banlist.md` / `sd-combat-engine/references/combat-rhythm-and-load-guardrails.md` |

### 极速直出模式的套装编排

> **前置：两档运行模式（先分清，再执行——治"严格锁 vs 极速直出"的口径冲突）**
>
> | 模式 | 触发 | 〇·1 素材来源 | A 模型 | B 画幅 | C 交付 | D 段缝 |
> |---|---|---|---|---|---|---|
> | **严格模式**（默认） | 普通需求 | **必须用户指定**，未指定 = 停下询问 | **必须用户指定**，未指定 = 停下询问 | **中文短剧总控成片固定 9:16，直接回显**；其他比例请求超出总控范围 | **必须用户指定**，未指定 = 停下询问 | 多段任务必问；已确认沿用 |
> | **极速模式（仅文本）** | 用户说 `跳过确认，直接出整集` | 允许按需求**软推断**（交付首行写明推断结果） | **仍必须用户指定／确认——不推断、不默认** | **中文短剧总控成片固定 9:16，直接回显**；其他比例请求超出总控范围 | **仍必须用户指定／确认——不推断、不默认** | 多段任务必问；已确认沿用 |
>
> **锁沿用纪律**：素材来源可软推断；A 模型与 C 交付形态须有用户指定或既有确认，缺失才询问。B 画幅沿用中文短剧总控固定的 9:16 并回显，不重复询问；通用工具对其他比例的兼容不构成总控画幅变更。极速只跳过文本编排的过程确认，不跳过必读、专业门禁与未定技术锁，**不授权图片或视频生成**。
>
> **口径优先级**：本表明确极速仅文本及已确认锁的沿用方式；素材来源软推断只限极速。P4 文本装配 → P5 出稿质检 → 导演台审阅 → 明确出片授权 → 实际生成 → 成片另验，极速不得越过该顺序。

`跳过确认，直接出整集` 时按管线顺序执行，**每阶段仍必须按上方【强制读取清单】显式读取对应子技能文件**（"跳过确认"只跳过向用户提问，不跳过读规则、也不跳过 A/B 锁）：**〇·1 定素材来源**（需求里出现"对标 / 参考某部剧 / 最近什么火"→ ③/④ 并加读 `sd-recon-engine`、先出《对标情报卡》；给的是小说/原著 → ②**；出稿后加读 `prompt-quality-enhancement.md` 跑八维体检（只建议不改稿）****并加读总控 `novel-to-shortdrama-adaptation.md`（改编决策环）；P2 人物转形象加读 `character-visual-style-lock.md`（造型锁环，档位须确认）**；否则 → ①；**素材来源推断结果须在交付首行说明**）→ **P0 接入本项目独立导演台并执行安装 check；A/C 锁沿用既有确认，缺失才询问，B=9:16 已确认直接回显**→ ⓪ 读 sd-decision-engine → 出情绪锚点表 → ① 读 sd-script-engine 六阶段编剧链（可跳过：已有剧本时）→ **素材形态默认 M1**（用户没提图：出图号 + **《素材接线单》**；说"没有图/不要图号"→ 降 M0 改文字锁；实际素材可访问并登记后→ 升 M2（仅口头说已出好不升级；授权/锁定/视觉核验另记）；**形态须在交付首行声明**，见 `asset-delivery-modes.md`）→ ② 读 sd-asset-engine → 三清单+**按形态产出**（M0 外观档案复述块 / **M1 出图提示词+编号+接线单** / M2 登记既有实际素材及待确认状态，极速不新增生成；九宫格按模板字段写全；**核心场景另交坐标系与 SET_STATE 状态变体登记**，见 `asset-spatial-ledger.md` §四）→ **②′ 调度环：读总控 `blocking-direction.md` → 建场景坐标系与文字平面图 → 摆人物初始位 → 逐拍走节拍闭环 → 定权力几何 → 记道具账 → 选唯一镜头策略模式**→ ③ 文戏读 sd-storyboard-engine；**镜行表演位需落成中文成品表情/动作短语时加读总控 `expression-motion-prompt-bank.md`（引擎 `scripts/expression_motion.py`）**；**运镜需落成 `spec` 合法词与中文画面描述时加读 `camera-movement-prompt-bank.md`；P2 试片 / 角色立绘加读 `asset-image-prompt-bank.md`（⛔ 出图词禁进 P4）**；**同段若含群像（调度环已标 `群像：A/B`）必加读 `wumao-short-drama-director/references/crowd-behavior-direction.md`**——画面里每个可见的人必须派到一件自己的事，`（在场）` 一律升级为 `（在场·事务：）`、站位声明四要素升五要素（机检 C40 只查开（A/B）门，C 类段只查一句「无其他人物」声明）；打戏按档分流——通用武侠读 sd-combat-engine / R3 玄幻读 sd-xuanhuan-engine / R1 真人写实读 sd-real-engine → **③′ 图形化环：读 `sd-storyboard-engine/references/storyboard-sheet-template.md` → 每段一张故事板图（动作相位七态拆格；文戏默认 2×2 四宫格 ≥4 格 / 打戏默认 2×3 六宫格 ≥6 格）→ 出 CLEAN_GRID 无文字版**（跨 2 镜以上叙事段/打戏段/重场戏必出）；**另读 `sd-storyboard-engine/references/plot-deduction-grid.md` 按条件必出规则出场次剧情分镜格**；**两件都逐段/逐场写进 P3 图形化交付清单，不出须写「⛔豁免 + 理由」，禁静默跳过** → ④ 读 sd-feed-engine → 过投喂层闸门并封装 → ⑤ 读 sd-qc-engine → 台账+机检 → ⑥ 总控看板输出并提交项目导演台审阅。**以上极速流程只交文本/提示词；保存、签审不生成。后续取得明确出片授权，核查必需素材齐备后才按已有授权范围优先本地执行实际生成，成片另验。**

