#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_director_console.py · 把导演台装进任意项目根目录（幂等）

技能每次开新项目 / 复用旧项目时都应先跑这一条，保证项目里有可双击的导演台：

    python scripts/install_director_console.py --root <项目目录>
    python scripts/install_director_console.py --root <项目目录> --check   # 只比对，不写盘

落地内容：
    <root>/导演台/{director_server.py,director_ui.html,director_studio.html,
                     continuity.py,h3_spec.py,使用说明.md}
    <root>/启动导演台.bat                  （GBK，兼容中文 Windows）
    <root>/00_source/PROJECT_INFO.json     （仅在缺失时创建，不覆盖已有值）
    <root>/导演台/安装清单.json            （版本 + 每个文件 sha256）

设计边界：
    - 幂等：文件内容一致就不动；不一致才覆盖，且先把旧文件备份成 <name>.bak-console
    - 不碰项目数据：剧本、资产、投喂包、台账一律不读不写
    - 不启动服务、不生成媒体；只铺文件
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

CONSOLE_VERSION = "1.4.0"
SKILL_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent
PAYLOAD = (
    "director_server.py",
    "director_ui.html",
    "director_studio.html",
    "continuity.py",
    "h3_spec.py",
)
TARGET_DIR = "导演台"
TARGET_DIR_LEGACY = "director"
MANIFEST = "安装清单.json"
MANIFEST_LEGACY = ".console.json"
LAUNCHER = "启动导演台.bat"
README_NAME = "使用说明.md"
PROJECT_INFO = Path("00_source/PROJECT_INFO.json")
DATA_DIR = "导演台数据"
DATA_DIR_LEGACY = "director_data"
DATA_SUBDIRS = ("历史快照", "生成剧本spec", "临时文件")
# 旧版本把状态散在 _tmp / 07_reports，安装时迁到 导演台数据/（复制，不删旧文件）
LEGACY_STATE = {
    "jobs.json": ("_tmp/director_jobs.json", "director_data/jobs.json"),
    "shot_status.json": ("_tmp/shot_status.json", "director_data/shot_status.json"),
    "progress.json": ("_tmp/batch_progress.json", "director_data/progress.json"),
    "history.json": ("07_reports/director_history.json", "director_data/history.json"),
}
DATA_README = """# 导演台数据 · 本项目专有

程序在 `../导演台/`（技能安装，升级会覆盖），**数据在这里**，升级不清空。

| 文件 / 目录 | 内容 |
|---|---|
| `jobs.json` | 后台任务记录（生成、拼接进度） |
| `shot_status.json` | 逐镜状态：ok / rewrite / hold |
| `progress.json` | 段 → 成片路径登记 |
| `history.json` | 修改历史索引（指向改前快照） |
| `审阅记录.json` | 逐镜批注、待办、按当前输入版本签审（首次审阅时创建） |
| `历史快照/` | 改前文本与图片版本，可反复回退 |
| `生成剧本spec/` | 提交给本地 H3 的 Director spec（调试用） |
| `临时文件/` | 导演台临时产物，可随时清空 |

- ⛔ 不要把这里的文件挪回 `_tmp/` 或 `07_reports/`：导演台只往这里写。
- 老项目首次安装时，会把 `_tmp/*.json`、`07_reports/director_history.json` **复制**进来；旧文件保留未删，确认无误后可自行清理。
- `jobs/local-runner/` 归 `comfyui-h3-local-runner` 所有（模板与队列状态），不要手改。
"""

# 2026-11-18 修（用户实测：「'chcp' 不是内部或外部命令 + 没找到 Python」）：
#   病根 = 进程 PATH 里缺 %SystemRoot%\System32。chcp / where / timeout / netstat
#   全在 System32，PATH 一丢，四个命令一起「不是内部或外部命令」；`where python`
#   也跟着失败 → 误报「没找到 Python」（机器上其实装了）。
#   改法：① 首行先把系统目录补回 PATH（不覆盖用户原有 PATH，只前置）；
#         ② chcp / timeout / netstat 一律走 %SystemRoot%\System32\ 绝对路径；
#         ③ Python 不再只靠 where，按「命令名 → 常见安装目录 → py 启动器 → 本机已知路径」逐级探测；
#         ④ 不再把项目路径当命令行参数传给 Python（改用 pushd + 相对路径），
#            避免非 936 代码页的机器上中文路径被编码打碎；
#         ⑤ 端口已被占用时不再报错退出，直接开浏览器。
LAUNCHER_TEXT = r"""@echo off
setlocal EnableExtensions
rem ============================================================
rem  导演台启动器 v2（自愈版）
rem  修 1：PATH 缺 System32 导致 chcp/where/timeout 报「不是内部或外部命令」
rem  修 2：找不到 Python（多路径探测 + 版本校验，>=3.9）
rem  修 3：端口占用时直接开浏览器，不报错
rem ============================================================
if not defined SystemRoot set "SystemRoot=C:\Windows"
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
if exist "%SystemRoot%\System32\chcp.com" "%SystemRoot%\System32\chcp.com" 936 >nul 2>nul

cd /d "%~dp0"
for %%I in ("%~dp0.") do set "PROJ=%%~nxI"

rem ---------- 探测 Python 3.9+ ----------
set "PY="
call :probe python
if not defined PY call :probe python3
if not defined PY call :probe py
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY for /d %%D in ("%ProgramFiles%\Python3*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY for /d %%D in ("C:\Python3*") do if not defined PY call :probe "%%~D\python.exe"
if not defined PY if exist "D:\trae-python\tools\python\python.exe" call :probe "D:\trae-python\tools\python\python.exe"
if not defined PY for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do if not defined PY call :probe "%%~D\python.exe"

if not defined PY (
  echo.
  echo [x] 没找到 Python 3.9 以上。请任选一种：
  echo     1^) 重装 Python 时勾选 Add python.exe to PATH，然后关掉本窗口重开
  echo     2^) 用记事本打开本文件，把 "set PY=" 那一行改成你的 python.exe 完整路径
  echo     3^) 命令行执行 py -3 --version，能用就把这一行结果发我
  echo.
  pause
  exit /b 1
)

rem ---------- 端口占用 ----------
set "BUSY="
for /f "tokens=*" %%L in ('netstat -ano ^| findstr /c:"LISTENING" ^| findstr ":8770 "') do set "BUSY=1"
if defined BUSY (
  echo [i] 8770 端口已被占用，导演台大概已经在跑了。
  echo     直接打开 http://127.0.0.1:8770/board
  start "" http://127.0.0.1:8770/board
  pause
  exit /b 0
)

echo ============================================================
echo  导演台 - %PROJ%
echo  地址：http://127.0.0.1:8770/board
echo  解释器：%PY%
echo  关闭本窗口即停止服务
echo ============================================================
start "" /min cmd /c "%SystemRoot%\System32\timeout.exe /t 3 >nul & start "" http://127.0.0.1:8770/board"

rem ---------- 定位程序目录（防代码页不对时中文目录名读不出来）----------
set "CDIR=%~dp0导演台"
if not exist "%CDIR%\director_server.py" set "CDIR=%~dp0director"
if not exist "%CDIR%\director_server.py" (
  echo.
  echo [x] 找不到程序目录里的 director_server.py。
  echo     请回到技能目录重跑一次安装：
  echo     python scripts\install_director_console.py --root .
  echo.
  pause
  exit /b 1
)
pushd "%CDIR%"
"%PY%" director_server.py --root ".." --port 8770
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
"""
LAUNCHER_ENCODING = "gbk"  # 中文 Windows 的 cmd 按 ANSI(936) 读批处理，用 GBK 才不会乱码

README_TEXT = r"""# 导演台 · 项目内置版

双击项目根目录的 **`启动导演台.bat`** 即可用（默认 http://127.0.0.1:8770/board）。

本目录由 `wumao-short-drama-director/scripts/install_director_console.py` 生成，
**不要手改**：改过的文件会在下次安装时被备份成 `旧版本备份/` 里的副本。
要改导演台本身，改技能目录里的同名文件，再跑一次安装脚本。

```bash
# 重新同步（技能更新后）
python <技能目录>/scripts/install_director_console.py --root .
# 只检查是否落后于技能版本
python <技能目录>/scripts/install_director_console.py --root . --check
```

## 目录分工

| 目录 | 内容 | 升级时 |
|---|---|---|
| `导演台/`（本目录） | 程序：后端、两个前端、连续性校验、H3 剧本转换 | 覆盖（旧文件备份到 `旧版本备份/`） |
| `../导演台数据/` | 数据：任务、镜状态、段进度、历史快照、提交剧本、临时文件 | **不动** |

状态文件只写 `导演台数据/`，不再散到 `_tmp/` 或 `07_reports/`。详见 `../导演台数据/说明.md`。

> **命名约定**：目录、说明、清单、启动脚本一律中文；`.py` 程序文件名保留英文——Python 的模块名与 `import` 必须一致，改名只会增加断链风险。

## 审阅与制作（导演台 1.4）

- 在「生产看板」按集和审阅状态筛选，点段进入现有分镜工作区。
- 在段详情选择镜头写批注，逐项解决待办；确认当前版本后签审，需修改可退回。
- 签审只代表当前提示词、账本与参考素材的人工审阅。改提示词、账本、参考图配置，或替换同名图片后，旧签审会过期；不等于实际成片验收。
- 「分镜节奏预演」按已知镜头时长播放文字画面与台词，不调用模型，不生成视频；未知时长显示待补。
- 批注与签审存入 `../导演台数据/审阅记录.json`，升级程序保留数据。保存和签审不会自动出图出片。

## 范围限制：只做中文短剧

本项目声明 `language` / `form` 后，导演台按中文短剧放行；一旦 `language` 被改成非中文，
总览会变红条并**锁定出图与出片**（接口层直接拒绝，不是只隐藏按钮）。详见技能内 `references/director-console.md` §九·补。

## 起不来怎么办（`启动导演台.bat` 故障排查）

> 2026-11-18 实修：用户机器上出现「`'chcp' 不是内部或外部命令` + `没找到 Python`」。
> 病根不在 Python——是**进程的 PATH 里缺 `%SystemRoot%\System32`**。`chcp`（chcp.com）、`where`、`timeout`、`netstat`
> 全在 System32，PATH 一丢这四个命令一起失效；`where python` 也跟着失败，于是误报「没找到 Python」。

| 现象 | 原因 | 处理 |
|---|---|---|
| `'chcp' 不是内部或外部命令` + `没找到 Python` | PATH 缺 System32 | 现版启动器首行就会把 System32/System32\Wbem 前置补回，再逐级探测 Python，**不会再出现**。若仍报，说明 bat 是旧版：重跑一次安装脚本 |
| 反复提示找不到 Python，但机器上明明装了 | 没进 PATH，且不在探测列表里 | 探测顺序：`python` → `python3` → `py` → `%LOCALAPPDATA%\Programs\Python\Python3*` → `%ProgramFiles%\Python3*` → `C:\Python3*` → `D:\trae-python\tools\python` → `%USERPROFILE%\.workbuddy\binaries\python\versions\*`。都找不到才报错，并提示你把 `set "PY="` 改成绝对路径 |
| 提示 Python 版本不够 | 装的是 3.8 及以下 | 探测时会校验 `>=3.9`，低版本自动跳过继续找下一个 |
| 双击后窗口闪一下就关 | 程序文件缺失或路径被改 | 跑 `python 导演台/director_server.py --root . --check` 看具体缺什么 |
| 8770 端口被占用 | 上次的窗口没关干净 | 新版会直接打开浏览器并退出，不再报错；要换端口用 `--port 8771` |
| 人物面板空、原著面板 0 章 | 缺两样数据源 | 人物要 `02_assets/CHARACTERS.json`（`characters` 数组 + `relations` 数组，字段 `id/name/role/rank/identity/appearance/outfit/voice/note/anchors`）；原著要 `00_source/小说.md` 或 `00_source/原著.md`（`.txt` 不认），章标题写成 `第N章 标题` 独占一行 |
| 分镜卡空、镜头 0 个 | H3 稿没有 `[mm:ss]` 行首时间码（那是 Seedance 写法） | 2026-11-18 起服务端会从 `prompt.md` 的「段落卡」表格兜底解析，不再空。前提是该段 `prompt.md` 里有 `| 镜 | 秒 | 景别 | ...` 表 |
| 连续性显示「已拦住」 | 参考图还没配或还没出 | `refs.json` 缺 `pictures` 或图文件不存在。出图后按 `S01/refs.example.json` 填；`prompt.txt` 里写 `<Picture 1> (文件名.png)` 才算接上 |
| 页面能打开但是 0 集 / 0 段 | 文件没按约定放 | 剧本放 `01_script/episodes/E0N.md`（首行 `# E01 · 标题`）；每段投产包放 `04_feed/segments/SNN/`（`prompt.md` + `SNN.srt` + `audio_note.md`，可选 `refs.json`） |

**自检命令**（判断是环境问题还是文件问题，一跑就知道）：

```bash
python 导演台/director_server.py --root . --check
```

它会逐项打印：集数、投产包数、成片数、资产、数据目录、UI、出图通道、出片通道，最后给 `PASS` / `FAIL`。

## 出图 / 出片：本机优先

| 能力 | 通道 | 前置 |
|---|---|---|
| 参考图重生成 | 本机 Image Forge → ComfyUI Desktop `127.0.0.1:8188`，默认 `h3image`，单图可切 `qwen` | ComfyUI 已启动 |
| 分镜出片 | `comfyui-h3-local-runner` 的 `h3_runner.py submit` | 项目内 `jobs/local-runner/` 的模板与状态 |
| 兜底 | 项目 `tools/submit_seg.py` | 本地 H3 未就绪时才用 |

出片前必须先 capture 一次成功任务：

```powershell
python "$HOME/.workbuddy/skills/comfyui-h3-local-runner/scripts/h3_runner.py" capture --project . --prompt-id <成功的prompt_id>
```

未 capture 时总览页会显示「分镜出片 本地 H3 未就绪」并给出原因，不会假装能出片。

环境变量可覆盖：`SD_IMAGE_GEN` / `SD_IMAGE_ENGINE` / `H3_RUNNER` / `H3_PYTHON`。
"""

PROJECT_INFO_TEMPLATE = {
    "title": "",
    "language": "zh-CN",
    "form": "中文短剧",
    "style": "",
    "genre": "",
    "audience": "",
    "logline": "",
    "model": "MiniMax-H3",
    "aspect": "9:16",
    "episode_seconds": 60,
    "episodes_total": 0,
    "image_engine": "h3image",
    "h3": {"fps": 24, "width": 720, "height": 1280, "scale": 0.4, "timeout_seconds": 1800},
    "episodes": {},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(root: Path):
    """返回 (缺失, 过期, 一致) 三个文件名列表。"""
    target = root / TARGET_DIR
    missing, stale, same = [], [], []
    for name in PAYLOAD:
        src, dst = SRC_DIR / name, target / name
        if not dst.is_file():
            missing.append(name)
        elif sha256(dst) != sha256(src):
            stale.append(name)
        else:
            same.append(name)
    return missing, stale, same


def migrate_layout(root: Path) -> list:
    """把旧版英文目录/文件名改中文：director→导演台、director_data→导演台数据。"""
    moves = []
    for old, new in ((TARGET_DIR_LEGACY, TARGET_DIR), (DATA_DIR_LEGACY, DATA_DIR)):
        src, dst = root / old, root / new
        if not src.is_dir():
            continue
        if not dst.exists():
            src.rename(dst)
            moves.append(f"{old}/ → {new}/")
            continue
        # 两处都在：把旧目录里新目录没有的条目搬过去，再尽量清掉空壳
        moved = 0
        for item in list(src.iterdir()):
            target = dst / item.name
            if target.exists():
                continue
            item.rename(target)
            moved += 1
        if moved:
            moves.append(f"{old}/ 中 {moved} 项并入 {new}/")
        if not any(src.iterdir()):
            src.rmdir()
            moves.append(f"{old}/ 空目录已移除")
        else:
            moves.append(f"{old}/ 仍有差异内容，保留待人工确认")
    old_manifest = root / TARGET_DIR / MANIFEST_LEGACY
    new_manifest = root / TARGET_DIR / MANIFEST
    if old_manifest.is_file() and not new_manifest.exists():
        old_manifest.rename(new_manifest)
        moves.append(f"{TARGET_DIR}/{MANIFEST_LEGACY} → {TARGET_DIR}/{MANIFEST}")
    old_readme = root / TARGET_DIR / "README.md"
    new_readme = root / TARGET_DIR / README_NAME
    if old_readme.is_file() and not new_readme.exists():
        old_readme.unlink()  # 内容由安装器重写，旧文件不必保留
        moves.append(f"{TARGET_DIR}/README.md → {TARGET_DIR}/{README_NAME}")
    old_data_readme = root / DATA_DIR / "README.md"
    new_data_readme = root / DATA_DIR / "说明.md"
    if old_data_readme.is_file() and not new_data_readme.exists():
        old_data_readme.rename(new_data_readme)
        moves.append(f"{DATA_DIR}/README.md → {DATA_DIR}/说明.md")
    for old_sub, new_sub in (("history", "历史快照"), ("specs", "生成剧本spec"), ("tmp", "临时文件")):
        src, dst = root / DATA_DIR / old_sub, root / DATA_DIR / new_sub
        if src.is_dir() and not dst.exists():
            src.rename(dst)
            moves.append(f"{DATA_DIR}/{old_sub}/ → {DATA_DIR}/{new_sub}/")
    return moves


def ensure_data_dir(root: Path) -> list:
    """建 导演台数据/ 结构并迁移旧状态文件（复制，不删旧文件）。"""
    d = root / DATA_DIR
    created = not d.is_dir()
    d.mkdir(parents=True, exist_ok=True)
    for sub in DATA_SUBDIRS:
        (d / sub).mkdir(exist_ok=True)
    readme = d / "说明.md"
    if not readme.is_file() or readme.read_text(encoding="utf-8", errors="replace") != DATA_README:
        readme.write_text(DATA_README, encoding="utf-8", newline="\n")
    migrated = []
    for name, sources in LEGACY_STATE.items():
        dst = d / name
        if dst.exists():
            continue
        src = next((root / rel for rel in sources if (root / rel).is_file()), None)
        if src:
            shutil.copy2(src, dst)
            migrated.append(f"{src.relative_to(root).as_posix()} → {DATA_DIR}/{name}")
    return migrated, created


def install(root: Path, quiet: bool = False) -> dict:
    root = Path(root).resolve()
    moves = migrate_layout(root)
    target = root / TARGET_DIR
    missing, stale, same = plan(root)
    target.mkdir(parents=True, exist_ok=True)
    backup_dir = target / "旧版本备份"
    backups = []

    for name in missing + stale:
        src, dst = SRC_DIR / name, target / name
        if not src.is_file():
            raise FileNotFoundError(f"技能包缺文件：{src}")
        if dst.is_file():
            backup_dir.mkdir(parents=True, exist_ok=True)
            bak = backup_dir / f"{name}.{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(dst, bak)
            backups.append(bak.relative_to(root).as_posix())
        shutil.copy2(src, dst)

    readme = target / README_NAME
    readme_changed = (not readme.is_file()) or \
        readme.read_text(encoding="utf-8", errors="replace") != README_TEXT
    if readme_changed:
        readme.write_text(README_TEXT, encoding="utf-8", newline="\n")

    launcher = root / LAUNCHER
    launcher_changed = (not launcher.is_file()) or \
        launcher.read_text(encoding=LAUNCHER_ENCODING, errors="replace").replace("\r\n", "\n") != \
        LAUNCHER_TEXT.replace("\r\n", "\n")
    if launcher_changed:
        launcher.write_text(LAUNCHER_TEXT, encoding=LAUNCHER_ENCODING, newline="\r\n")

    info_path = root / PROJECT_INFO
    created_info = False
    if not info_path.is_file():
        info_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(PROJECT_INFO_TEMPLATE, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        created_info = True

    migrated, data_created = ensure_data_dir(root)

    manifest = {
        "console_version": CONSOLE_VERSION,
        "skill_dir": str(SKILL_DIR),
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": {name: sha256(target / name) for name in PAYLOAD},
        "backups": backups[-20:],
    }
    (target / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")

    result = {"root": str(root), "installed": missing, "updated": stale, "unchanged": same,
              "backups": backups, "launcher": str(launcher), "layout_moves": moves,
              "launcher_changed": launcher_changed, "readme_changed": readme_changed,
              "project_info_created": created_info, "data_created": data_created,
              "migrated": migrated}
    changed = bool(missing or stale or launcher_changed or readme_changed or created_info
                   or data_created or migrated or moves)
    if not quiet:
        for item in moves:
            print(f"[+] 目录改名：{item}")
        if missing:
            print(f"[+] 新装 {len(missing)} 个文件：{', '.join(missing)}")
        if stale:
            print(f"[+] 更新 {len(stale)} 个文件：{', '.join(stale)}")
        if not missing and not stale:
            print("[=] 代码文件已是最新")
        for label, flag in (("启动脚本", launcher_changed), ("使用说明", readme_changed)):
            if flag:
                print(f"[+] 已更新{label}")
        if backups:
            print(f"[i] 旧版本已备份到 {TARGET_DIR}/旧版本备份/")
        if data_created:
            print(f"[+] 已建数据目录：{DATA_DIR}/（历史快照 / 生成剧本spec / 临时文件）")
        for item in migrated:
            print(f"[+] 已迁移旧状态：{item}")
        print(f"[+] 启动：双击 {LAUNCHER}（或 python {TARGET_DIR}/director_server.py --root .）")
        if created_info:
            print(f"[+] 已放项目信息模板：{PROJECT_INFO.as_posix()}（填风格、单集时长等）")
    result["changed"] = changed
    return result


def check(root: Path) -> int:
    root = Path(root).resolve()
    missing, stale, same = plan(root)
    launcher = root / LAUNCHER
    problems = []
    if not (root / TARGET_DIR).is_dir() and (root / TARGET_DIR_LEGACY).is_dir():
        problems.append(f"仍是旧目录名 {TARGET_DIR_LEGACY}/，应为 {TARGET_DIR}/")
    if missing:
        problems.append("未安装：" + ", ".join(missing))
    if stale:
        problems.append("落后于技能版本：" + ", ".join(stale))
    if not launcher.is_file():
        problems.append(f"缺 {LAUNCHER}")
    else:
        try:
            text = launcher.read_text(encoding=LAUNCHER_ENCODING)
            if "导演台" not in text:
                problems.append(f"{LAUNCHER} 内容不像中文启动脚本（可能编码不对）")
            direct_target = f"{TARGET_DIR}\\director_server.py" in text
            via_directory = (f'set "CDIR=%~dp0{TARGET_DIR}"' in text and
                             'pushd "%CDIR%"' in text and
                             '"%PY%" director_server.py --root ".." --port 8770' in text)
            if not (direct_target or via_directory):
                problems.append(f"{LAUNCHER} 未指向 {TARGET_DIR}/director_server.py")
        except (UnicodeDecodeError, OSError):
            problems.append(f"{LAUNCHER} 不是 GBK 编码，中文会乱码")
    data_root = root / DATA_DIR
    if not data_root.is_dir():
        problems.append(f"缺 {DATA_DIR}/（数据目录，未归置）")
    else:
        absent = [s for s in DATA_SUBDIRS if not (data_root / s).is_dir()]
        if absent:
            problems.append(f"{DATA_DIR}/ 缺子目录：" + ", ".join(absent))
    if problems:
        print("[x] 导演台不完整 / 已过期 / 数据未归置")
        for item in problems:
            print("    - " + item)
        print("[i] 修复：python scripts/install_director_console.py --root .")
        return 1
    print(f"[+] OK 导演台已就位（{len(same)} 个文件与技能一致 · {LAUNCHER} 正常 · {DATA_DIR}/ 齐备）")
    return 0


def self_test() -> bool:
    with tempfile.TemporaryDirectory(prefix="wb-console-") as tmp:
        root = Path(tmp) / "proj"
        root.mkdir()
        # 造一份旧位置的状态文件，验证会迁到 导演台数据/ 且不删旧文件
        (root / "_tmp").mkdir()
        legacy = root / "_tmp" / "director_jobs.json"
        legacy.write_text('[{"id": "old-job"}]', encoding="utf-8")
        first = install(root, quiet=True)
        if sorted(first["installed"]) != sorted(PAYLOAD):
            print("[!] 首次安装文件数不符:", first["installed"]); return False
        if not (root / LAUNCHER).is_file():
            print("[!] 未生成启动脚本"); return False
        raw = (root / LAUNCHER).read_bytes()
        try:
            text = raw.decode(LAUNCHER_ENCODING)
        except UnicodeDecodeError:
            print("[!] 启动脚本不是 GBK，中文会乱码"); return False
        if ("set \"CDIR=%~dp0导演台\"" not in text or
                'pushd "%CDIR%"' not in text or
                '"%PY%" director_server.py --root ".." --port 8770' not in text):
            print("[!] 启动脚本中文表述或路径不对"); return False
        if not (root / PROJECT_INFO).is_file():
            print("[!] 未创建 PROJECT_INFO 模板"); return False
        if not (root / TARGET_DIR / README_NAME).is_file():
            print("[!] 未生成中文使用说明"); return False
        data_root = root / DATA_DIR
        if not data_root.is_dir() or not all((data_root / s).is_dir() for s in DATA_SUBDIRS):
            print("[!] 未建导演台数据结构"); return False
        migrated = data_root / "jobs.json"
        if not migrated.is_file() or "old-job" not in migrated.read_text(encoding="utf-8"):
            print("[!] 旧状态未迁移"); return False
        if not legacy.is_file():
            print("[!] 迁移时删掉了旧文件（应保留）"); return False
        second = install(root, quiet=True)
        if second["installed"] or second["updated"]:
            print("[!] 非幂等：第二次仍写入", second); return False
        if check(root) != 0:
            print("[!] check 未通过"); return False
        victim = root / TARGET_DIR / "director_server.py"
        victim.write_text("# drift\n", encoding="utf-8")
        if check(root) != 1:
            print("[!] 被改动后 check 未报警"); return False
        third = install(root, quiet=True)
        if third["updated"] != ["director_server.py"]:
            print("[!] 未识别过期文件:", third["updated"]); return False
        if not third["backups"]:
            print("[!] 覆盖前未备份"); return False
        if victim.read_text(encoding="utf-8").startswith("# drift"):
            print("[!] 未覆盖为技能版本"); return False
        shutil.rmtree(data_root)
        if check(root) != 1:
            print("[!] 数据目录缺失时 check 未报警"); return False
        print("[+] install_director_console self-test PASSED")
        return True


def main() -> int:
    ap = argparse.ArgumentParser(description="把导演台装进项目根目录（幂等）")
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    if not args.root:
        print("[!] 需要 --root <项目目录>")
        return 2
    root = Path(args.root)
    if not root.is_dir():
        print(f"[!] 目录不存在：{root}")
        return 2
    return check(root) if args.check else (0 if install(root) else 1)


if __name__ == "__main__":
    sys.exit(main())
