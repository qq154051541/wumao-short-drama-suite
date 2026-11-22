# Wumao Short-Drama Suite · 中文短剧导演技能套装

面向 AI 助手的中文短剧创作与生产规则套装：从创意、小说改编、剧本、角色资产和分镜，到模型投喂稿、质检与项目内置导演台。

本仓库包含 **1 个总控 + 10 个子技能**。技能版本为 **1.1.0**，内置导演台版本请以安装器与模块更新日志为准。主入口是 [`wumao-short-drama-director/SKILL.md`](wumao-short-drama-director/SKILL.md)。

## 适用范围

- 9:16 中文真人短剧或漫剧；普通话对白、简体中文字幕。
- Seedance 2.5 / 2.0 与 MiniMax-H3 的模型提示词编排。
- 优先复用内置的表情、动作、运镜及资产成品提示词，并按当前剧情适配。
- 生成媒体需要另行准备模型、运行环境及必要素材；本仓库不附带模型权重、账号或服务密钥。

## 安装

下载本仓库 ZIP 并解压，或运行：

```bash
git clone https://github.com/qq154051541/wumao-short-drama-suite.git
```

将以下 **11 个目录整体复制到 AI 助手的技能目录，保持同级**，不要只安装总控：

```text
wumao-short-drama-director/
sd-decision-engine/
sd-recon-engine/
sd-script-engine/
sd-asset-engine/
sd-storyboard-engine/
sd-combat-engine/
sd-xuanhuan-engine/
sd-real-engine/
sd-feed-engine/
sd-qc-engine/
```

WorkBuddy 的用户技能目录为 `~/.workbuddy/skills/`。其他平台需具备读取本地技能文件及执行必要脚本的能力，并按各自的技能加载方式安装。仓库根目录是套装目录；要求 ZIP 根目录直接包含 `SKILL.md` 的导入器，需要按平台要求分别导入并补齐同级依赖。

## 使用

安装后向助手提出需求，例如：

> 用中文短剧导演技能，把我的故事改成竖屏短剧，先做一集剧本和分镜。

总控按阶段读取子技能并确认创作约束。流程为：立项 → 剧本 → 资产提示词与接线 → 调度分镜 → 模型投喂稿 → 出稿质检 → 导演台审阅 → 明确授权后先生成小样 → 验片后推进授权范围内的生产。

用户无需手动切换子技能。详细能力、模板和规则见[总控说明](wumao-short-drama-director/README.md)。

## 项目内置导演台

需要 Python 3；建议使用 Python 3.11。进入仓库根目录后，可将导演台安装到自己的短剧项目：

```bash
python wumao-short-drama-director/scripts/install_director_console.py --root "你的项目目录"
python wumao-short-drama-director/scripts/install_director_console.py --root "你的项目目录" --check
```

Windows 项目根目录会生成 `启动导演台.bat`，程序放在 `导演台/`，运行数据保存在 `导演台数据/`。支持生产看板、逐镜批注、待办、按输入版本签审与文字分镜节奏预演。保存与签审不会触发媒体生成。

导演台浏览与文字审阅不要求安装本地生成模型。生图、出片依赖外部运行器，例如 `comfyui-h3-local-runner` 及相应 ComfyUI / H3 环境，**这些运行器不包含在本套装中**。源码中保留部分开发机的本地运行器默认路径；其他机器需要按[导演台说明](wumao-short-drama-director/references/director-console.md)配置路径和服务。请勿将默认路径视为已安装依赖。

## 检查套装

在仓库根目录运行：

```bash
python wumao-short-drama-director/scripts/check_package.py
```

此检查用于规则、模块结构和脚本完整性，不等同于实际生成的视频质量验收。

## 许可与内容来源

仓库包含的许可证为 [MIT](LICENSE)，保留各文件已有的版权、许可与来源说明。第三方平台、模型和素材遵循各自的许可与服务规则；本仓库不代表这些平台或模型的官方产品。成品提示词和规则的历史来源尚未完成逐条权属映射，使用或再分发时请核对相关条目原有说明；MIT 声明不替代第三方授权。

本仓库仅发布技能源码与规则，不包含创作项目数据、私人参考素材或模型权重。
