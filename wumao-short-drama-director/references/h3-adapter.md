# MiniMax-H3 适配层（模型线 ③ · 原生音视频一体 · 官方字段铁律）

> **定位**：A 锁选 **③ MiniMax-H3** 时，本文件是**提示词格式唯一权威**。它与 Seedance 的七段式（`model-adapters.md` §5）**互斥、不可混写**——选哪条模型线，就只用那一套字段。
> **由来**：本包 2026-11-03（P13）曾主动剥离 H3 支线；2026-11-15 用户裁定「用 H3 时要用它的原生音频和字幕，并严格按官方写法」→ 恢复为独立模型线，**判据随官方规范走，不沿用 Seedance 的 C 码**。

---

## 一、什么时候选 H3（给用户的三句话判断）

| 场景 | 建议 |
|---|---|
| 要**一条就带声音**（对白 / 环境声 / 配乐一体），不想后期配音对口型 | ✅ **H3** |
| 单镜 4~15 秒、以「一镜到底 / 连续动作」为主 | ✅ **H3** |
| 要**多段拼接成 60~120 秒短剧**、每段 15 秒以内、需要严格的中文投喂语法与 C 码机检 | ✅ **Seedance 2.5 / 2.0** |
| 需要首尾帧精准锁动作起止、且要中文七段式交付 | ✅ **Seedance 2.5** |

> ⛔ 同一集里**不许一半 H3 一半 Seedance**：两条线的音轨与镜头语法无法对齐，混用必穿帮。

---

## 二、官方字段（唯一写法 · 顺序不可调）

### 2.1 Base 模式三段（T2VA / I2VA / FL2VA / L2VA）

```text
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

| 字段 | 写什么 | 铁律 |
|---|---|---|
| `integrated_multimodal_description` | 画面 + 动作 + 分镜 + 说话人 + 对白 + 歌声 + **画内音**，按时间轴推进 | 每镜以 `[Shot N]` 起头；**画面与同期声写在同一镜里**，不许把声音单列成段 |
| `overall_soundscape` | 全片环境声 / 物理动作声 / 人声非语言声（喘息、脚步、衣料摩擦） | 写**声源与触发动作**，不写「氛围感」这类抽象词 |
| `non_diegetic_music` | 角色听不到、只有观众听到的配乐 | 写**乐器 + 情绪走向 + 进出点**；无配乐就写 `none`，不许留空 |

### 2.2 Ref2VA 六段（多参考图锁形象时用）

```text
subject_definitions: ...
summary: ...
retention_analysis: ...
detailed_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

- 参考图标签统一写 `<Picture 1>` `<Video 1>` `<Audio 1>`，**全篇一致**；
- `retention_analysis` 逐项说明「参考图的哪一部分被保留 / 哪一部分被改写」；
- 本包 M1 编号占位（`@图1`…）→ 落成 H3 时必须转成 `<Picture N>` 并在 `subject_definitions` 里一对一登记。

---

## 三、四种 Base 模式的取舍（对齐本包的素材形态）

| 模式 | 官方语义 | 本包什么时候用 |
|---|---|---|
| **T2VA** | 纯文本建整条音视频时间轴 | M0 纯提示词、无参考图 |
| **I2VA** | 给首帧，往后推演 | M1/M2 有角色立绘或场景图，**默认走这个** |
| **FL2VA** | 首尾帧之间插值 | 需要精准锁动作起止（替代 Seedance 2.5 首尾帧） |
| **L2VA** | 给末帧，反推前因 | 段缝要「末帧定格承接」时反过来用 |
| **Ref2VA** | 多图/多视频/多音频全参考 | 角色 4 View + 场景 + 道具 + 参考音色，**跨集一致性的最强档** |

**模式指令行必须有**（官方原文句式，改动即失效）：

- I2VA：`For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- FL2VA：`How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark; Picture 2 (from Shot N) aligns with the S.SS-second mark.`
- L2VA：`How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`

> `N` = 实际末镜序号，`S.SS` = 目标时长（保留两位小数）。**指令行必须是整份提示词的第一行。**

---

## 四、原生音频：H3 的卖点，也是它的硬约束

> ★ **2026-11-20 对齐官方**：以 `h3-prompt-writing` 技能的 `references/base-en.txt` / `ref-en.txt` 为**唯一格式权威**。本包 H3 稿一律按下列官方写法，⛔ 不再用旧口径「（女声，中低音，语速偏慢）+ 裸引号台词」——那不是官方字段，模型对 `<d>` 标签里的台词口型对齐最稳。

### 4.0 官方对白／镜头格式铁律（写 H3 投喂稿必守）

1. **说话人稳定 ID**：凡开口/唱歌/画外音的角色，首次出现给 `(S1)`、`(S2)`……全程复用；不发声的角色不给 ID。多人齐声写 `(S1,S2)`。说话人身份描述（年龄/音色/语速）写在 `<d>` **外面**。
2. **台词官方包裹**：`<d>[Chinese] 原文台词。</d>` —— 语言标签用英文方括号，台词**逐字保留原话与标点**，不翻译不改写；完整句末标点写在 `</d>` 前。
   - 正例：`The young woman with a quiet voice (S1) says, <d>[Chinese] 你先吃。</d>`
   - 反例（⛔作废）：`她说（女声，中低音）：「你先吃。」`
3. **画外音**：用固定句 `says in an off-screen voiceover`，并在该 `<d>` 后立即写对应角色 `his/her lips remain completely closed`。
4. **镜头切点**：`[Shot 1]` 开头**不带时间戳**；从 `[Shot 2]` 起用 `[Shot N] At MM:SS.mmm, the camera cuts to ...`，切点严格递增且落在总时长内。只用距离/角度变化时优先写运镜而非切镜。
5. **运镜三要素**：运动类型 + 幅度 + 速度，写成自然英文（`The camera pushes in with small amplitude at slow speed toward ...`），⛔ 不堆成句尾标签。
6. **画内文字**（招牌/手机屏/弹幕）：放英文双引号 `"原文"` 保留原字，与字幕分开；字幕仍走 SRT，不要求模型画字。
7. **音频两段**：`overall_soundscape` 1–4 句英文（环境声+物理动作声+非语言人声，不重复对白）；`non_diegetic_music` 1–3 句英文（配器/速度/动态，无配乐写 `N/A`）。

### 4.1 其余约束

1. **对白写在描述里，不做后期配音**——按 4.0 的 `(Sx)` + `<d>[Chinese]…</d>` 官方句式。
2. **对白语言保留原话**（中文台词就写中文），**其余描述用英文**；歌词、画面可见文字同样保留原语言。
3. **音效绑画面事件**：`a bank card slaps against wood` → 声源与动作同句；⛔ 不写「紧张的音效」这类无源描述。
4. **配乐进出点要对上镜头**：`non_diegetic_music: A single low cello note enters at [Shot 2] and cuts at the door click.`（用英文，不用中文）。
5. **单镜 4~15 秒**：H3 的时长约束比 Seedance 更窄，**整段描述的时间推进必须与目标时长匹配**（官方 Tips 原话：total duration must match the requested video length）。
6. **Ref2VA 六段**（多参考图锁形象时）：`subject_definitions` / `summary` / `retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music`，标签 `<Subject N>` `<Picture N>` `<Video N>` `<Audio N>` 全篇一致；`retention_analysis` 用固定英文标记 `fully_preserved / partially_preserved / attribute_transfer / weak_reference`（音频用 `fully_copy / partially_copy / reference / weak_reference`）。详见官方 `ref-en.txt`。

---

## 五、字幕：由音轨反推，不让模型画字

- **原生输出已含音轨** → 字幕按对白时间轴生成 **SRT**，由平台侧烧录，⛔ 不要求模型在画面里「生成字幕」（画面文字会被当美术元素，容易糊）。
- SRT 规则：一条 ≤ 18 字、单屏最多两行、进出时间留 0.1 秒余量、与对白起止误差 ≤ 0.2 秒。
- 需要「画面内文字」（招牌、手机屏、弹幕）时，在 `integrated_multimodal_description` 里显式写 `visible text: 「…」`，与字幕分开管。

---

## 六、与七段式的映射（从 Seedance 稿转 H3 时照这张表搬）

| Seedance 七段 | H3 落点 |
|---|---|
| 【画幅风格】 | 写进 `integrated_multimodal_description` 开头一句（`9:16 vertical, cinematic realism`） |
| 【场景资产】 | 同字段首镜的场景锚定句 |
| 【核心人物】 | 同字段的人物出场句；Ref2VA 时进 `subject_definitions` |
| 【站位声明】 | 同字段的空间关系句（左/右/前景/背景） |
| 【时间轴分镜】 | 逐 `[Shot N]` 段落 |
| 【音效】 | 环境/动作声进 `overall_soundscape`；对白进描述正文 |
| 【强制禁止项】 | ⛔ H3 不认否定块 → **改成正向锁定**（写「皮肤有毛孔质感」而不是「不要磨皮」） |

---

## 七、与 Seedance 规则的冲突裁决（6 条）

1. **时长**：H3 4~15 秒/段 > 包内 Seedance 的 2.5=30s / 2.0=15s 口径 → **H3 线只按 4~15s 判**，C1 不适用。
2. **字段语言**：H3 正文英文、对白原语言 → **C12「中文正文禁英文术语」不适用**（但英文只许出现在 H3 字段里，不许回流到 Seedance 稿）。
3. **禁止项**：H3 无「强制禁止项」栏 → 一律正向锁定；**C24 类否定块判据不适用**。
4. **首尾帧**：H3 用 `Picture 1/2` + FL2VA/L2VA 语义，**不写** `first_frame`/`last_frame`（那是 Seedance 术语）。
5. **顿挫/`[SFX:]`**：H3 不写方括号音效标记，音效进 `overall_soundscape`。
6. **段缝**：H3 段与段的接续靠 **L2VA 反推**或末帧图承接（D 锁①的等价做法），⛔ 不用 Seedance 的尾帧锚定术语。

---

## 八、机检 H1~H7（`validate_prompt.py --model h3`）

| 码 | 判据 | 处置 |
|---|---|---|
| **H1** | 三段（或六段）字段齐备且顺序正确 | FAIL |
| **H2** | 每个镜头以 `[Shot N]` 起头、序号连续 | FAIL |
| **H3** | `overall_soundscape` 与 `non_diegetic_music` 非空（无配乐须写 `N/A`） | FAIL |
| **H4** | 非官方裸「」台词缺说话人/语气（旧口径残留检查；官方 `<d>` 台词不触发） | WARN |
| **H5** | 描述时长与目标时长匹配（4~15s 区间） | FAIL |
| **H6** | 出现 Seedance 专有术语（`[SFX:]` / `first_frame` / 七段式栏位名） | FAIL |
| **H7** | 官方对白格式：出现裸「」台词提示改 `<d>[Chinese]…</d>`；有 `<d>` 时须有 `(S1)` 说话人 ID、台词块非空 | WARN |

> H 码与 C 码**分线判定**：`--model 2.5|2.0` 跑 C 码，`--model h3` 跑 H 码，互不叠加。

---

## 九、交付清单（H3 线专属）

1. 提示词正文（英文描述 + 原语言对白）；
2. 参考图标签对照表（`@图N` ↔ `<Picture N>` ↔ 用途）；
3. SRT 字幕文件（按音轨时间轴）；
4. 音轨说明（对白列表 / 环境声 / 配乐进出点）；
5. 一致性台账（人物/场景/道具/服装/光线，跨集沿用）。

---

## 十、本机实测基线（2026-11-15 实跑，不是估算）

> 环境：ComfyUI Desktop 8188 · RTX 4080 16G（`comfyui-h3-local-runner` 同源环境）。
> 本次跑通的是 **Ref2VA 权重 + 4 步 turbo LoRA**，不是云端 API 节点。

**权重**：`minimax_h3_ref2va_pruned_w6a8.safetensors`（15G）+ `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（15G，`CLIPLoader type=minimax`）+ `minimax_h3_video_vae_fp16` + `minimax_h3_audio_vae_fp32` + `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16`（LoRA，strength 1.0）。

**图结构**（API 可复现，15 节点）：

```
UNETLoader → LoraLoaderModelOnly(4step)
CLIPLoader(type=minimax) ─┐
VAELoader(video) ─────────┼→ MiniMaxH3ReferenceToVideo(clip, vae, audio_vae, prompt, w, h, length)
VAELoader(audio) ─────────┘            │
KSamplerSelect(res_multistep) + BasicScheduler(simple, steps=4, denoise=1) + BasicGuider + RandomNoise
                                       ↓
                        SamplerCustomAdvanced → VAEDecode(video) + VAEDecodeAudio(audio)
                                       ↓
                        CreateVideo(fps=24) → SaveVideo
```

**本次参数与结果**

| 项 | 值 |
|---|---|
| 分辨率 | 384×672（9:16，最小可用档） |
| length | **124 帧 = 5.17s**（`length` 步长 17、最小 5，即 5 / 22 / … / 124，trained 124~362） |
| 采样 | 4 步 · `res_multistep` · `simple` · 无负面（BasicGuider，cfg=1） |
| 出片耗时 | **≤ 30 秒**（提交到 `/history` 可见，含模型加载） |
| 音轨 | **aac 32kHz 立体声**，与画面同长 5.17s |
| 对白验证 | ASR 转写命中原文「**你到底还是来了。**」时间轴 **3.31s–4.61s** |
| 画面文字 | **无烧录字幕** → 印证 §五「字幕由外部 SRT 烧录，不靠模型画字」 |
| 机检 | `validate_prompt.py --model h3 --dur 5.17` → **H1~H6 PASSED（0 WARN）** |

**已知限制（同一轮实测的观察，不是猜）**

1. 384×672 下**手部与栏杆有轻微畸变**（4 步 turbo 的正常代价）→ 正式出片建议 ≥540×960 或升到 8 步。
2. 本次**未挂参考图**（`ref_images` 空）跑通纯文生音视频；多图 Ref2VA（锁人物一致性）**尚未实测**。
3. 720p 以上、12 秒以上长段**未测**，耗时未知。
4. `length` 若不按 17 步长取值，ComfyUI 会报参数错——**先用官方公式 `max(5, round(秒数×24))` 再对齐到 17 的步长**。

### 10.3 Ref2VA 多图一致性实测（同日追加 · 两段跨场景）

**做法**：同一角色出 3 张参考图（**全身 / 头肩裁切 / 半身裁切**，同一张原图裁切即得）→ 挂到 `ref_images`。
⛔ **API 写法必须嵌套**：`"ref_images": {"ref_image_1": [...], "ref_image_2": [...], "ref_image_3": [...]}`；
写平铺的 `ref_image_1` 会报 `unexpected keyword argument 'ref_image_1'`。

**两段跨场景**（参数同上：384×672 / 124 帧 / 4 步）：

| 段 | 场景 | 对白 | ASR 命中 | 出片 |
|---|---|---|---|---|
| A | 便利店门口（冷白店灯 + 暖霓虹） | 「雨还没停啊。」 | 3.50–4.78s | 30s |
| B | 车内副驾（雨刷 + 路灯光扫） | 「前面路口停一下。」 | 3.60–4.83s（**逐字准确**） | 30s |

**结论**：

1. **跨场景身份稳定** —— 两段是同一张脸（黑长直 / 冷白皮 / 细眉直鼻 / 黑大衣），换场景、换光位、换景别都没换人。H3 线跨集一致性**可行**。
2. **代价**：参考图是前置条件 → H3 线要把「M2 先出 3 张同角色参考图」写成硬前置，等价于四格板的精简版。
3. **对白可控**：两段台词分别命中，时间轴各在 3.5~4.8s 落点，说明「对白写进描述」这条路可靠。
4. **画面文字不可信**：A 段便利店招牌是模型自造的，字有错 → **招牌 / 手机屏 / 文件类文字一律后期贴图，不交给模型**。

**环境坑**：输入图必须放 **`D://Comfy-Desktop//ComfyUI-Shared//input`**（Desktop 版共享输入目录），放 `ComfyUI-Installs\...\input` 会报 `No such file or directory`。

---

## 十一、三个必踩的坑（2026-11-20 复跑 6 段验证 · 出片前逐条过）

> 这三条都会**静默失败**——不报错、看着成功，但结果是错的。第一集因此白跑 3 轮。

### 坑 1 · `ref_images` 的 key 前缀必须是 `ref_image_`

`MiniMaxH3ReferenceToVideo` 的自动增长输入定义为：

```python
io.Autogrow.Input("ref_images", template=io.Autogrow.TemplatePrefix(
    input=io.Image.Input("ref_image", ...), prefix="ref_image_", min=0, max=9))
```

→ 合法槽位名是 **`ref_image_0` … `ref_image_8`**。

⛔ 写成 `image_1` / `ref_images.image_1` 都**不报错**，但会被静默丢弃 → 参考图完全无效。
**判据**：换参考图后跑两条，若抽帧**像素级完全相同**（`ffmpeg -f rawvideo | md5sum` 一致），就是参考图没进去，不是模型不听话。

```json
"ref_images": {"ref_image_0": ["12",0], "ref_image_1": ["13",0]}   ✅
"ref_images": {"image_1": ["12",0]}                                 ❌ 静默丢弃
```

### 坑 2 · `length` 必须满足 step=17

节点签名：`length: Frame count at 24 fps, (124 = ~5s, trained range is ~124-362)`，且 `step=17`。

| 目标时长 | length |
|---|---|
| 5 秒 | **124** |
| 15 秒 | **362**（= 124 + 17×14） |

⛔ 15 秒填 352（不在 124+17k 序列里）会被 clamp，实际仍出 362 帧但参数不合法。

### 坑 3 · 服装必须写进 prompt，参考图管不住

实测：参考图挂**裁切的单人像**（只有脸）→ 男主穿成红蓝运动服；换**完整四格板**（脸+正面全身+侧面+背面）→ **照样跑偏**。
根因不在参考图，在**投喂词里根本没写服装**（S02/S04/S05/S06 四段全缺），模型只能自由发挥。

**硬规则**：每段 `integrated_multimodal_description` 开头必须带一句服装锚：

```
Characters and wardrobe, keep identical in every shot:
Li Luo wears a dark grey cotton polo with a slightly pilled collar, dark khaki cargo pants,
black mesh sneakers, and a blue rideshare platform ID badge on a lanyard.
Zhi Xia wears a light purple short-sleeve top, light blue denim shorts, sheer beige stockings,
and white flat shoes, with a single-strap canvas tote bag.
```

补上后同一段立刻稳定为深灰 POLO + 工装裤 + 蓝工牌。**参考图负责「像谁」，prompt 负责「穿什么」。**

### 附：本机路径与缓存

- ComfyUI Desktop 的 `output` / `input` 都在 **`D:/Comfy-Desktop/ComfyUI-Shared/`** 下（不是 `ComfyUI/output`）。
- **LoadImage 按文件名缓存**：同名文件被覆盖后可能仍读到旧图 → 换图内容时**用新文件名**（如 `h3_liluo_full.png`）。
- `comfyui-h3-local-runner` 技能 `capture` 要求 graph 内含 `MiniMaxH3DirectorCS` 节点；本机 `custom_nodes` 为空、无任何 Director 节点 → **该技能在本机不可用**，走原生节点直连。
- 官方模板 `api_minimax_h3_r2v.json` 用的是云节点 `MinimaxHailuo03ReferenceNode`（需 API key），**不是本地跑法**，照抄会跑不起来。

### 附：段缝硬承接（D锁① 的本地实现）

`MiniMaxH3AddGuide(frame_idx=0, image=上段末帧)` 可以把首帧钉死：

```
Ref2V → (positive, latent)
AddGuide(positive, latent, frame_idx=0, vae, audio_vae, image=<上段末帧>) → positive'
ConditioningZeroOut(positive') → negative
KSampler(model, positive', negative, latent, steps=4, cfg=1.0, euler, simple)
```

抽末帧：`ffmpeg -sseof -0.1 -i 上段.mp4 -frames:v 1 -update 1 上段末帧.png`

### 附：精确文字（余额/到账/招牌）一律后期贴图

H3 生成的小字不可信（第十节实测已证）。**手机特写段落不要指望模型写对数字**，按下面三步补：

1. **量屏幕位置**：抽该段中间帧 → PIL 按候选框裁剪放大 3 倍 → 目视读出屏幕四边在裁剪框内的百分比 → 换算回原帧坐标。
2. **画 UI 覆盖图**：PIL 超采样（×4）绘制，中文用 `C:/Windows/Fonts/msyhbd.ttc`，数字用大字号（占屏高 ~10% 才读得清），存 RGBA。
3. **overlay 定时段**：
   ```bash
   ffmpeg -y -i seg.mp4 -i ui.png -filter_complex \
     "[0:v][1:v]overlay=X:Y:enable='between(t,8.6,14.6)'" -c:a copy out.mp4
   ```
   只贴手机特写的那几秒（`enable=between`），其它时间不出现；UI 用深色系可与暗调画面自然融合。

> 坐标换算：若先在小分辨率试贴，升分辨率后按 `×1.5`（320→480）同比例放大 `x/y/w/h`，再抽帧复核一次。

### 坑 4 · 高分辨率长视频的 ContextWindows —— ⚠️ 已弃用（2026-11-23 推翻，见下）

> **★ 重大修正（2026-11-23，E01 全片重做实证）**：本节下方「挂 ContextWindows + overlap-linear + 6 步」的配方**虽能消除网格伪影，但会导致台词与画面在窗口边界反复重播**（同一句台词被念 2-3 遍、同一动作重复执行）。这是比网格伪影严重得多的致命 bug，用户复核才发现。
> **现行结论：本机出片一律走「5 秒段（124 帧 / 4 步 / 不挂 ContextWindows）+ 出片后 lanczos 超分」**，彻底不用窗口。完整根因、ASR 铁证、替代方案见 `references/h3-production-pitfalls.md` 坑 A。
> 下方原文保留作**历史记录**（解释网格伪影的成因与窗口机制），**不再作为推荐配方**。

`MiniMaxH3ReferenceToVideo` 的 `length` 最大 362（15 秒），但**上下文窗口默认只有 124 帧**。超过就得挂：

```
MiniMaxH3ContextWindows(model, context_length=124, context_overlap=39,
                        fuse_method=?, freenoise=True, split_conds_to_windows=False) → KSampler
```

**不挂**（480×864 + 362 帧实测）→ 全片出现**规律横竖网格/纱窗伪影**，画面发暗发糊。
**挂了但 `fuse_method=pyramid`（默认）** → 网格消失，但仍有**局部帧伪影**：绿黄色条纹网格、横向拉丝糊、局部画面撕裂（实测 S03 的 1–4s、S04 首帧、S06 第 12s 各有一处）。

**稳定配方**：
```
fuse_method = "overlap-linear"   （选项：pyramid / relative / flat / overlap-linear）
steps       = 6                  （4 步 turbo 在窗口边界处容易不收敛）
```
换成这组后同段重跑，绿黄网格与拉丝全部消失。

**判据**：抽帧时重点看**窗口边界附近**（124 帧 ≈ 5.17s、约 8.7s、约 12.2s），伪影最先出现在那里。逐段抽 1.5 / 2.5 / 3.5 / 6 / 10 / 14 秒各一帧人工过一遍，不要只抽查中间。

**代价**：480×864 / 15s / 6 步 ≈ 220 秒/条（4 步约 170 秒）。

**720×1280 在本机（4080 16G）跑不了 15 秒**（2026-11-20 实测）：请求 `length=362`，`MiniMaxH3ContextWindows` 自动重算成 `context_length=37 / overlap=12 / 只有 107 帧`（≈4.5s），单步要跑 4 个窗口 × 25s ≈ 100s，6 步 10 分钟还只出 4.5 秒。日志特征：

```
Using context windows: Context length 37 with overlap 12 for 107 frames.
Context window 1/4: frames 0-36 of 107
```

**结论（历史，已被 2026-11-23 实测推翻）**：480×864 是这台机器的 15 秒上限档；要更高清只能拆成 5 秒段（段缝成本翻倍）或出片后超分。分辨率提升**不解决**人脸漂移——漂移是参考图与逐段 refs 的问题（见坑 5/7）。

> **2026-11-23 覆写**：上面这句「拆成 5 秒段」方向对了，但「段缝成本翻倍」的顾虑不成立——5 秒段 + 4 步反而**每段更快（60-80s）且无重复语音**，是当前唯一推荐路线。见 `references/h3-production-pitfalls.md`。

---

### 坑 5 · 不能把「设定板」直接当 ref_image 喂（人脸/空间全乱的头号原因）

2026-11-20 实拍复盘。本包看板用的三类设定板，**没有一张适合直接投喂 H3**：

| 板型 | 实际内容 | 喂进去的后果 |
|---|---|---|
| 角色板 | 左边 1 张大脸特写 + 右边 3 套**无脸人台/无头衣服** + 顶部 3 个飘浮发型 | 模型抓到"空白脸"就丢脸；抓到发型就换头；抓到无头衣就生成半截人 → **每段脸都不一样** |
| 场景板 | 3×3 九宫格，每格还压着 AI 生成的假铭牌/乱码标题条 | 模型随机吃一格 → **一会儿车里一会儿车外**；乱码被画进画面 |
| 道具板 | 2×2 四格 | 一个镜头里出现 4 部手机 / 4 个戒指盒 |

**铁律：身份设定板 ≠ 出片参考图。出片参考必须「一人一张、正面、单格」。**

配套脚本 `scripts/build_h3_refs.py` 负责从板上派生：

```bash
# 1. 生成 spec（首次，人工核对每个 scene 的格位）
python build_h3_refs.py --root <项目根> --write-spec
# 2. 生成单图参考到 02_assets/h3_refs/
python build_h3_refs.py --root <项目根>
```

- **人物**：自动找「大脸 ↔ 换装区」之间的背景竖缝（只认 0.20–0.46 宽度区间，防止把一整排无脸人台裁进来），把正脸居中贴到 9:16 画布。输出约 `864×1536`。
- **场景/道具**：按 `cell: [row, col]` 取单格，裁掉上下标题条（`trim=46`），再做 `GaussianBlur(1.6)` —— 空间结构、光影、机位都还在，乱码文字和假按钮糊掉，模型不会照着画字幕。
- **spec 挂在项目里**，看板仍显示四格板（`refs.json` 的 `file`），出片走 `h3_file` → 两套图各司其职，互不干扰。

`refs.json` 写法：

```json
{"pictures": {
  "Picture 1": {"role": "李洛（正脸·H3出片参考）",
                "file": "02_assets/characters/图1_李洛.png",
                "h3_file": "02_assets/h3_refs/h3ref_CHR-001_李洛.png"}}}
```

**自检**：喂错参考图的判据是「换参考图后抽帧人脸 md5 不变」。现在再加一条 —— 生成图里出现**无头身体、飘浮头发、四宫格排版、画面内乱码字幕条**，就是还在喂设定板。

---

### 坑 6 · 段缝 AddGuide 不能无脑全段用（这是「人一会儿车里一会儿车外」的真凶）

`AddGuide(frame_idx=0, 上段末帧)` 会把首帧钉死。过去六段全接，等于**强迫每段的第一帧复制上一段的构图**。而剧本里大多数段与段之间根本不是连续时空：

| 段缝 | 剧本关系 | 该不该接 | 全接的后果 |
|---|---|---|---|
| S01→S02 | 夜 → **次日晨**（跨夜） | ❌ 不接 | 醉趴餐桌的人被迫"瞬移"到沙发，模型折中 → 人在桌边和沙发之间 |
| S02→S03 | 客厅 → **校门口**（跨地点） | ❌ 不接 | 客厅构图被拖进校门 |
| S03→S04 | 同地点但**掉头回来**（跨时间） | ❌ 不接 | 车内后视镜构图拖进车外人行道 |
| S04→S05 | 她在车外 → **车内单人**（换机位） | ❌ 不接 | 车外双人拖进驾驶座 |
| S05→S06 | **同一机位、同一光位、连续动作** | ✅ 接 | —— |

**判定口诀：只有「同一机位 + 同一光位 + 动作没断」才接；跨时间、跨地点、换机位一律不接。**

不接的段，靠 prompt 里的 `Continuity lock` 写清"这是几秒/几小时后"或"开场即新机位"，比硬接干净得多。

---

### 坑 7 · 每段出现的人，都必须在自己的 refs.json 里

S03/S04 原来只给了知夏，没给李洛 —— 但李洛在这两段里又说话又露脸（后视镜、递包）。**没给参考的人物，脸就是模型现编的**，跑完六段等于六张不同的脸。

出片前逐段过这张表：

```
本段出现几个人 → 每个人是否在 refs.json 里有 h3_file → prompt 里的 <Picture N> 编号是否与之对应
```

`<Picture N>` 与 `refs.json` 的槽位是**硬绑定**：改编号必须同步改 json，反之亦然。脚本化校验（`_tmp/gen_refs.py` 那类）比肉眼靠谱。

---

### 附：站立/走位/开门的写法（空间锁三层）

H3 对"人在哪、朝哪、门怎么开"几乎没有常识，必须显式写死。每段 prompt 开头固定三层：

```
Identity lock: <Subject 1> X 的脸锁 <Picture 1> —— 骨相/眉/眼/鼻/发型/年龄 逐项写死 + "never re-cast or restyle"
Wardrobe lock: 从头到脚 + 配饰（参考图管不住衣服，见坑 3）
Geography lock: 场景朝向 + 关键参照物 + 车辆停位与车头朝向 + 门窗状态
Staging: 谁在哪个位置、面向哪边、身边什么道具
```

**车戏四条硬规则**（S03 实测踩过）：

1. **先定车头朝向，再定左右座**：`facing east / driver seat on the left / front passenger seat on the right / rear right seat`。不写这句，模型会让乘客坐到驾驶座。
2. **上下车不拍全过程**：只写"她拉门+跨进去+门在她身后关上"，并限定入画元素 `only her hand, the door panel and her legs`。写"绕到车头再开门"必然穿模。
3. **不许跨马路**：`she walks along the sidewalk ... she never steps onto the roadway`。否则人物会在马路中央出现又消失。
4. **门只朝"靠人行道那一侧"开**，不要写"右后门"，写 `the rear door on the sidewalk side` —— 左右由朝向推导容易反。

**镜序铁律**：一镜只做一件事。不要在"车外镜头"里让车内的人说话并把台词写在里面 —— H3 会把台词理解成"该镜头内发生对话"，从而把车内镜头插到车外镜头中间，**整段镜序错乱、字幕错位**。要画外音就显式写 `his voice comes from inside the car, off-screen and close`。

---

### 附：动作链必须「单步化」（S03 三连跑实测）

同一个 7.5 秒镜头里写「从校门走过来 → 拉开车门 → 坐进去 → 关门」四步，H3 的实测表现是**动作循环**：
上车 → 又下车 → 再上车，字幕跟着重念一遍。抽帧（0.2 / 1.0 / 2.5 / 4.0 / 5.5 / 6.2 / 8.0 / 10.0 / 12.0 / 14.0s）能清楚看到同一段门开了三次。

**修法：把镜头起点推到动作中段，只留最后一步。**

| ❌ 四步 | ✅ 单步 |
|---|---|
| she walks from the gate to the door, pulls it open, slides in, and the door shuts | she is **already stepping into** the rear right seat, one hand on the door edge, the door **swinging shut behind her** |

配套加三句否定护栏（H3 对"不要重复"比"要做"更敏感）：
`she does not walk around the car, does not get out again, and does not repeat the entry`

同类高危动作：**上下车 / 坐下再站起 / 递接物品 / 开门关门**。一律只拍"结果态"或"最后一格动作"，不拍全过程。

顺带两条：
- 空座位要显式写 `the front passenger seat is empty and clean, nobody sits in it for the whole segment` —— 否则模型会自己塞一个乘客进去（实测 S03 副驾冒出第三人）。
- 重出片后**必须删掉旧的分镜抽帧** `05_qc/machine/storyboard/{seg}_shot*.png`。`ensure_shot_frames()` 只在文件不存在时抽帧，不删就一直显示旧片的画面。

---

### 坑 8 · `[Shot N] At 00:0X.000` 的切点**不可靠** —— 插入镜一律单独成段

2026-11-20 同一句 prompt 反复验证（480×864 / 6 步 / overlap-linear，三个不同 seed 结果一致）：

| 段 | 写在 prompt 里的切点 | 实际切到哪里 |
|---|---|---|
| S01 | `[Shot 1] 戒指盒特写` → `At 00:04.000, a hard cut` → 人物中景 | 15 秒几乎全是戒指盒，4.5s 处闪了 0.5 秒人物又回去 |
| S02 | 沙发中景 → `At 00:07.500, a hard cut to a top-down insert` | 手机特写被推到 **14.5s**，只占最后半秒 |
| S05/S06 | 中景 → 推近/特写 | 全程一个机位，一次没切 |
| S03 | 车外车窗 → 车内后视镜 | ✅ 切了（两个机位分属**车外/车内**两个空间） |
| S04 | 车内 → 车外窗 | ✅ 切了（同上） |

**规律**：只有两镜处在**不同空间载体**（车内↔车外）时才稳定切；同一空间内的"特写↔中景"基本不切，而且切点会漂到最后。加 `a hard cut:` / `leaves the frame completely` / `out of frame` 这些护栏只能减轻，不能保证。

**因此定规矩**：

1. **主体段一律一镜到底**（一段 = 一个机位、一件事），不再指望段内切镜。
2. **静物/手机屏/手表盘这类插入镜，单独出 3 秒小段**（`length=73` = 17×4+5），不带人脸、只拍物体，剪辑时硬切进去。它天然形成分镜节奏，而且文字/UI 可以后期贴图覆盖，完全可控。
3. 剪辑顺序自己排，例如：
   `I01 钻戒特写 3s → S01 分手 15s → S02 醒来 15s → I02 手机欠款 3s → S03 → S04 → S05 → I06 到账 3s → S06`
   总长 = 六段主体 90s + 三个插入 9s ≈ 99s。
4. 插入镜 prompt 里写死 `One continuous shot, no cuts, hold the framing for the whole clip` + `nobody touches …` / `nothing else enters the frame`，把变量降到最低。

---

### 坑 9 · 视频节点的 `ref_image` 是**弱参考**，锁脸必须走「首帧」而不是「参考图」

2026-11-20 第二轮实测，这是整条链上最反直觉的一条：

| 实验 | 做法 | 结果 |
|---|---|---|
| A | `MiniMaxH3ReferenceToVideo` 的 ref_image 从「四格板裁的正脸」换成「H3-Image 新生成的定版半身照」，其余全同 | 输出**字节数几乎不变**（556KB→556KB、837KB→837KB），抽帧人脸没有换 |
| B | 同一张定版照喂 `H3-Image`（生图），提示词换成「坐在驾驶座」 | **换场景也还是同一张脸**，服从度极高 |

结论：**Ref2VA 的参考图只能决定"大概这种人"，不能锁身份**。要在 5 秒里锁住脸，只有把身份塞进**首帧**。

**正确链路（E01 全片按此重做，跨镜脸统一）**：

```
定版照（H3-Image --reference 出，一人一张，灰背景半身）
   ↓  H3-Image：定版照 + 该镜机位描述 → 每镜首帧（480×864）
   ↓  MiniMaxH3ImageToVideo(first_frame=首帧, length=124)
5 秒视频（脸锁在首帧上，不换人）
```

节点参数（本机 `/object_info` 实查）：

```
MiniMaxH3ImageToVideo(clip, vae, prompt, width, height, length,
                      first_frame=IMAGE, last_frame=IMAGE(可选))
  → (positive CONDITIONING, LATENT)
ConditioningZeroOut → KSampler(model=ContextWindows, steps=6, cfg=1.0)
VAEDecode + VAEDecodeAudio → CreateVideo(24fps) → SaveVideo
```
`length` 同样走 17k+5（124 = 5 秒）。

**首帧提示词三条硬要求**：

1. `the same person as the reference image: <骨相/眉/眼/鼻/发型/年龄> + 服装` —— 身份描述必须逐项重述，不能只写 "same person"。
2. `Face clearly lit and readable` —— 首帧脸暗了，后面 5 秒都看不清。
3. `exactly one person in frame` / `no extra limbs` —— 生图阶段就把多肢掐掉，视频阶段不会自己长回来。

**每镜首帧必须单独出**（不要一张首帧跑多个镜头）：机位写进首帧提示词，视频只做"在这张图上动 5 秒"。

**实测代价**：定版照 40s/张；首帧 20–40s/张；I2VA 5 秒 64–80s/条。15 镜全片约 23 分钟，与直接 Ref2VA 出 15 镜持平，但脸终于统一了。

配套脚本：`scripts/build_h3_shots.py`（镜头表 → 六段投喂稿 + refs）、项目侧 `_tmp/build_frames_i2v.py`（首帧+I2VA 批跑）、`_tmp/run_i2va.py`（单镜 I2VA）。
