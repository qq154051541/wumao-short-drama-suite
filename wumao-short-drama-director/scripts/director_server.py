#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""director_server.py · 导演台动态控制台（本地服务 · 纯标准库）

端口策略（2026-11-23 · 用户实测多项目并行撞端口后修订）：
    --port N            固定端口；被占用时自动顺延 N+1、N+2 …（最多 100 个），
                        并在启动横幅里打印实际占用情况，不再崩、不再误开别人的台。
    --port auto         从 BASE 起找第一个空闲端口（多项目并行默认用这个）
    --port 缺省         等价 auto
    ⚠ 端口 ≠ 项目：同一端口只认先启动的那个实例；第二个项目若被误指到
      已占端口，打开的是别人的导演台（数据各写各的项目目录，不会串，
      但界面看的不是自己项目）。启动横幅会打印实际 root，开台前先核对。

把"看板"从静态资产浏览器升级为可编辑、可重新生成的动态导演台：
    分集点播 / 资产浏览 / 剧本站段编辑 / 分镜画格墙 / 提示词编辑 /
    单段重新生成 / 版本对比 / 图片重生成与回滚

用法：
    python director_server.py --root <项目目录> [--port 8770] [--title 项目名]
    python director_server.py --root <项目目录> --check      # 只做自检不启服务
浏览器打开 http://127.0.0.1:PORT/board

设计依据（2026-11 · 参考 Boords / StudioBinder / Storyboarder / Toon Boom）：
    ① 分镜画格墙：每镜抽帧成画格，一屏看完整段视觉节奏
    ② 状态色标：ok / rewrite / hold 三态，逐帧审阅语义
    ③ 时间占比条：按镜时长占比可视化节奏
    ④ 版本对比：重新生成版与正式版并排 + 同步播放
    ⑤ 脚本↔分镜同源：段详情内剧本与分镜并列，改完即可重生成
    ⑥ 资产按剧情名展示：slug/hash 映射为剧中具体名称，不再是英文文件名

约定（与 output-directory-spec 一致）：
    01_script/episodes/E0N.md      剧本（首行 # E0N · 标题）
    04_feed/segments/SNN/          prompt.txt / prompt.md / refs.json
    clips/raw/local-runner/        生成原片（sNN-040mp*.mp4）
    06_delivery/                   成片
    05_qc/machine/                 机检图
    02_assets/IMAGE_PROMPTS.json   锚图生成提示词库（可选，供图片重生成）
    02_assets/ASSET_NAMES.json     资产中文名映射（可选）

数据归置（程序与数据分离）：
    director/                      程序（由技能安装，覆盖不影响数据）
    director_data/                 本项目导演台数据（升级不清空）
        jobs.json                  后台任务
        shot_status.json           逐镜状态 ok/rewrite/hold
        progress.json              段→成片登记
        history.json + history/    改前快照与索引
        specs/                     H3 Director spec
        tmp/                       临时产物（提示词文件 / concat 清单）
    jobs/local-runner/             H3 runner 自有（模板与状态，勿手改）
    旧位置（_tmp/*.json、07_reports/history）仍可读取，写入一律落到 director_data/
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import continuity
import h3_spec

# ---------- 运行期配置（由 main 注入） ----------
ROOT: Path = Path(".")
TITLE: str = ""
UI_FILE: Path = Path(__file__).resolve().parent / "director_ui.html"
STUDIO_FILE: Path = Path(__file__).resolve().parent / "director_studio.html"
PY = sys.executable

# 可选外部配置（缺省不报错）
IMAGE_PROMPTS_NAME = "02_assets/IMAGE_PROMPTS.json"
ASSET_NAMES_NAME = "02_assets/ASSET_NAMES.json"
ASSET_LINKS_NAME = "02_assets/ASSET_LINKS.json"

# 导演台自有数据目录（程序在 导演台/，数据在 导演台数据/，升级程序不动数据）
DATA_DIR = "导演台数据"
HISTORY_DIR = f"{DATA_DIR}/历史快照"
SPECS_DIR = f"{DATA_DIR}/生成剧本spec"
WORK_TMP_DIR = f"{DATA_DIR}/临时文件"
PROGRESS_NAME = f"{DATA_DIR}/progress.json"
JOBS_NAME = f"{DATA_DIR}/jobs.json"
STATUS_NAME = f"{DATA_DIR}/shot_status.json"
HISTORY_NAME = f"{DATA_DIR}/history.json"

# 历史版本会迁到 导演台数据/，这里保留旧位置以便老项目无缝读取
LEGACY_PATHS = {
    PROGRESS_NAME: ("_tmp/batch_progress.json", "director_data/progress.json"),
    JOBS_NAME: ("_tmp/director_jobs.json", "director_data/jobs.json"),
    STATUS_NAME: ("_tmp/shot_status.json", "director_data/shot_status.json"),
    HISTORY_NAME: ("07_reports/director_history.json", "director_data/history.json"),
}

# ---------- 本地生成通道（优先本机 ComfyUI Desktop 8188） ----------
SKILL_ROOT = Path(os.environ.get("WUMAO_SKILL_ROOT", "")) if os.environ.get("WUMAO_SKILL_ROOT") else None
DEFAULT_IMG_ENGINE = os.environ.get("SD_IMAGE_ENGINE") or "h3image"
DEFAULT_IMAGE_GEN = Path("D:/WorkBuddyProject/AI生图/start.py")
DEFAULT_H3_RUNNER = Path.home() / ".workbuddy" / "skills" / "comfyui-h3-local-runner" / "scripts" / "h3_runner.py"
COMFYUI_PYTHONS = (
    Path("D:/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/Scripts/python.exe"),
    Path("D:/Comfy-Desktop/ComfyUI-Installs/ComfyUI/.venv/Scripts/python.exe"),
)
H3_STATE = Path("jobs/local-runner/state.json")
H3_TEMPLATE = Path("jobs/local-runner/verified-template.api.json")


def _first_file(*candidates) -> Path | None:
    for item in candidates:
        if item and Path(item).is_file():
            return Path(item)
    return None


def image_gen_path() -> Path | None:
    """生图器入口：环境变量优先，其次本机 Image Forge，再回落技能侧脚本。"""
    return _first_file(
        os.environ.get("SD_IMAGE_GEN"),
        DEFAULT_IMAGE_GEN,
        SKILL_ROOT / "AI生图" / "start.py" if SKILL_ROOT else None,
    )


def h3_runner_path() -> Path | None:
    return _first_file(os.environ.get("H3_RUNNER"), DEFAULT_H3_RUNNER)


def h3_python() -> Path:
    """H3 runner 需要 Pillow（参考图审计）；ComfyUI 自带 venv 已装，优先用它。"""
    found = _first_file(os.environ.get("H3_PYTHON"), *COMFYUI_PYTHONS)
    return found or Path(sys.executable)


def h3_status() -> dict:
    runner, template = h3_runner_path(), ROOT / H3_TEMPLATE
    state = ROOT / H3_STATE
    if not runner:
        return {"ready": False, "runner": "", "template": False,
                "reason": "未找到 comfyui-h3-local-runner（可设 H3_RUNNER 指向 h3_runner.py）"}
    if not template.is_file():
        return {"ready": False, "runner": str(runner), "template": False,
                "reason": "缺 jobs/local-runner/verified-template.api.json：需先在 ComfyUI 跑通一条并 capture"}
    if not state.is_file():
        return {"ready": False, "runner": str(runner), "template": True,
                "reason": "缺 jobs/local-runner/state.json：与模板一起由 capture 生成"}
    return {"ready": True, "runner": str(runner), "template": True, "reason": "",
            "python": str(h3_python())}

ASSET_GROUPS = [
    ("source", "00_source", "来源"),
    ("script", "01_script", "剧本"),
    ("characters", "02_assets/characters", "角色"),
    ("scenes", "02_assets/scenes", "场景"),
    ("props", "02_assets/props", "道具"),
    ("audio", "02_assets/audio", "音色/音轨"),
    ("storyboard", "03_storyboard", "分镜"),
    ("feed", "04_feed", "投喂包"),
    ("qc", "05_qc", "质检"),
    ("delivery", "06_delivery", "交付"),
    ("reports", "07_reports", "报告"),
]
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VID_EXT = {".mp4", ".mov", ".webm"}
TEXT_EXT = {".md", ".txt", ".json", ".srt", ".py", ".html"}
SKIP_DIRS = {"_tmp", ".git", "__pycache__", "node_modules",
             "director", "director_data"}  # 程序与运行数据不进资产浏览
BAK_RE = re.compile(r"_bak(\.[A-Za-z0-9]+)?$")  # 重生备份图，如 图1_李洛_bak.png

_jobs_lock = threading.Lock()
_review_lock = threading.RLock()
REVIEW_NAME = f"{DATA_DIR}/审阅记录.json"


# ---------- 路径与配置 ----------
def p_root() -> Path:
    return ROOT


def load_json(rel: str, default):
    """读导演台数据：优先 导演台数据/，缺失时回退旧位置（老项目无缝）。"""
    candidates = [rel, *LEGACY_PATHS.get(rel, ())]
    for item in candidates:
        try:
            return json.loads((ROOT / item).read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def save_json(rel: str, obj):
    f = ROOT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _atomic_save_json(rel: str, obj):
    """原子替换 JSON，供审阅记录等并发写入数据使用。"""
    target = ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False)
    tmp = Path(stream.name)
    try:
        with stream:
            json.dump(obj, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def data_dir() -> Path:
    d = ROOT / DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def work_tmp(name: str) -> Path:
    """导演台自己的临时产物（提示词临时文件 / concat 清单），不污染项目 _tmp。"""
    p = ROOT / WORK_TMP_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_progress():
    return load_json(PROGRESS_NAME, {"done": {}, "failed": {}})


def load_jobs():
    return load_json(JOBS_NAME, [])


def save_jobs(jobs):
    save_json(JOBS_NAME, jobs[-40:])


def load_status():
    return load_json(STATUS_NAME, {})


def save_status(st):
    save_json(STATUS_NAME, st)


def load_image_prompts():
    return load_json(IMAGE_PROMPTS_NAME, {})


def save_image_prompts(lib):
    save_json(IMAGE_PROMPTS_NAME, lib)


def _history():
    rows = load_json(HISTORY_NAME, [])
    return rows if isinstance(rows, list) else []


def _snapshot(source: Path, suffix_hint: str) -> str:
    """把文件当前内容复制进历史快照目录，返回相对路径。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    uniq = f"{int(time.time() * 1000) % 100000}"
    archive = ROOT / HISTORY_DIR / f"{source.stem}-{stamp}-{uniq}{source.suffix or suffix_hint}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, archive)
    return archive.relative_to(ROOT).as_posix()


def _snapshot_text(label: str, content: str, suffix: str = ".txt") -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    uniq = f"{int(time.time() * 1000) % 100000}"
    archive = ROOT / HISTORY_DIR / f"{label}-{stamp}-{uniq}{suffix}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(content, encoding="utf-8", newline="\n")
    return archive.relative_to(ROOT).as_posix()


def _record_history(kind: str, label: str, path: str, before_snapshot: str,
                    after_snapshot: str, affected_segments=None):
    """历史行只存快照路径；正文按需从快照读取，避免索引文件膨胀。"""
    if before_snapshot and before_snapshot == after_snapshot:
        return None
    if before_snapshot and after_snapshot:
        before_file, after_file = ROOT / before_snapshot, ROOT / after_snapshot
        if before_file.is_file() and after_file.is_file():
            try:
                same = before_file.read_bytes() == after_file.read_bytes()
                if not same and before_file.suffix.lower() == ".json":
                    # JSON 只看语义：仅缩进/键序重排不算一次修改
                    same = json.loads(before_file.read_text(encoding="utf-8")) == \
                        json.loads(after_file.read_text(encoding="utf-8"))
                if same:
                    after_file.unlink(missing_ok=True)
                    return None
            except (OSError, ValueError):
                pass
    rows = _history()
    row = {
        "id": f"H{int(time.time() * 1000)}-{len(rows) + 1}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind, "label": label, "path": path,
        "before": before_snapshot, "after": after_snapshot,
        "affected_segments": sorted(set(affected_segments or [])),
    }
    rows.append(row)
    save_json(HISTORY_NAME, rows[-1000:])
    return row


def history_row_detail(row, limit: int = 20000):
    """给前端返回可读的前后内容；图片只给路径。"""
    def read(rel):
        if not rel:
            return ""
        target = ROOT / rel
        if not target.is_file():
            return ""
        if target.suffix.lower() in IMG_EXT:
            return ""
        try:
            return target.read_text(encoding="utf-8")[:limit]
        except (OSError, UnicodeDecodeError):
            return ""

    out = dict(row)
    out["before_text"] = read(row.get("before", ""))
    out["after_text"] = read(row.get("after", ""))
    out["before_is_image"] = Path(row.get("before", "")).suffix.lower() in IMG_EXT
    return out


def asset_links():
    links = load_json(ASSET_LINKS_NAME, {})
    return links if isinstance(links, dict) else {}


def mark_asset_dependents(path: str):
    affected = asset_links().get(path, [])
    if isinstance(affected, str):
        affected = [affected]
    status = load_status()
    for seg in affected:
        if isinstance(seg, str) and SEGMENT_ID_RE.fullmatch(seg):
            status.setdefault(seg, {})["asset_update"] = {
                "path": path, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "needs_review": True
            }
    valid = [s for s in affected if isinstance(s, str) and SEGMENT_ID_RE.fullmatch(s)]
    if valid:
        save_status(status)
    return valid


# ---------- 集 / 段 推断 ----------
def scan_episodes():
    """扫描 01_script/episodes/E0N.md，按集号排序。返回 {E01: (lo,hi)} 段号区间。

    段号规则：段号 = (集序-1)*6 + 1 .. 集序*6。若项目自定义，可提供 _tmp/seg_map.json。
    """
    custom = load_json("_tmp/seg_map.json", None)
    if isinstance(custom, dict) and custom:
        out = {}
        for ep, nums in custom.items():
            out[ep] = (min(nums), max(nums))
        return out
    eps = {}
    for f in sorted((ROOT / "01_script" / "episodes").glob("E*.md")):
        m = re.match(r"E(\d+)", f.stem)
        if m:
            eps[f.stem] = int(m.group(1))
    out = {}
    for ep, idx in sorted(eps.items(), key=lambda kv: kv[1]):
        out[ep] = ((idx - 1) * 6 + 1, idx * 6)
    return out


def build_seg_index():
    """SEG_EP: {S07: E02}"""
    d = {}
    for ep, (lo, hi) in scan_episodes().items():
        for n in range(lo, hi + 1):
            d[f"S{n:02d}"] = ep
    return d


def episode_title(ep: str) -> str:
    f = ROOT / "01_script" / "episodes" / f"{ep}.md"
    if not f.is_file():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines()[:3]:
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def episode_synopsis(path: Path) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines[:20]):
        if re.match(r"^>\s*(简介|梗概|内容简介)\s*[:：]", line):
            return re.sub(r"^>\s*(简介|梗概|内容简介)\s*[:：]\s*", "", line).strip()
    body = [re.sub(r"^>\s*", "", line).strip() for line in lines if line.strip() and not line.startswith(("#", "> 原著", "<!--"))]
    return " ".join(body[:2])[:220]


def episode_cover(ep: str) -> str:
    """封面优先级：PROJECT_INFO 指定 → 交付封面 → 资产内带集号的图片。"""
    info = load_json("00_source/PROJECT_INFO.json", {})
    meta = ((info.get("episodes") or {}) if isinstance(info, dict) else {}).get(ep) or {}
    declared = meta.get("cover") if isinstance(meta, dict) else ""
    if declared and (ROOT / declared).is_file():
        return declared
    for ext in (".jpg", ".png", ".webp"):
        for cand in (f"06_delivery/covers/{ep}{ext}", f"02_assets/covers/{ep}{ext}"):
            if (ROOT / cand).is_file():
                return cand
    assets = ROOT / "02_assets"
    if assets.exists():
        for p in sorted(assets.rglob(f"*{ep}*")):
            if p.suffix.lower() in IMG_EXT:
                return p.relative_to(ROOT).as_posix()
    return ""


def episode_chapters(ep: str) -> str:
    """从剧本 md 元信息行解析原著章节：> 原著 CH15–CH16 ｜ ...（冒号可有可无，全/半角均可）"""
    f = ROOT / "01_script" / "episodes" / f"{ep}.md"
    if not f.is_file():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines()[:8]:
        m = re.search(r"原著\s*[:：]?\s*(CH[\dA-Za-z–\-—~]+(?:\s*[–\-—~]\s*(?:CH)?[\dA-Za-z]+)?)", line)
        if m:
            return m.group(1).strip()
    return ""


def seg_episode(seg: str) -> str:
    """段号所属集；SEG_EP 未初始化（如被 import 而非 main 启动）时回退实时推断。"""
    ep = SEG_EP.get(seg)
    if ep:
        return ep
    try:
        num = int(seg[1:])
    except ValueError:
        return ""
    for ep_id, (lo, hi) in scan_episodes().items():
        if lo <= num <= hi:
            return ep_id
    return ""


def seg_title(seg: str) -> str:
    ep = seg_episode(seg)
    if not ep:
        return ""
    f = ROOT / "01_script" / "episodes" / f"{ep}.md"
    if not f.is_file():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if re.match(rf"^##\s+{seg}\b", line):
            return line.lstrip("# ").strip()
    return ""


# ---------- 片段查找 ----------
CLIP_DIRS = ("06_delivery/clips_hd", "06_delivery/clips",
             "clips/final", "clips/raw", "clips")


def _stem_tokens(stem: str):
    return [t.lower() for t in re.split(r"[^0-9A-Za-z]+", stem) if t]


def _clip_in_dir(seg: str, d: Path):
    """目录内该段的成片：文件名任意位置出现独立 token S01（不分大小写）。"""
    if not d.is_dir():
        return None
    want = seg.lower()
    hits = []
    for f in d.glob("*.mp4"):
        if "无HUD" in f.name or "存档" in f.name:
            continue
        if want in _stem_tokens(f.stem):
            hits.append(f)
    if not hits:
        return None
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0]


def clip_for_seg(seg: str):
    """段落成片查找。

    2026-11-20 修：旧实现只认 progress.done 与 clips/raw/local-runner/S01-040mp*.mp4，
    而实际出片落在 06_delivery/clips_hd/E01_S01.mp4 → 导演台「该段未生成」、
    分集点播 0/N，用户已出片却看不到。现在按目录优先级 + 文件名 token 匹配，
    同目录取最新；progress 登记仍最高优先。
    """
    p = load_progress().get("done", {}).get(seg)
    if p and Path(p).is_file():
        return Path(p)
    for rel in CLIP_DIRS:
        hit = _clip_in_dir(seg, ROOT / rel)
        if hit:
            return hit
    cands = sorted(glob.glob(str(ROOT / "clips" / "raw" / "local-runner" /
                                 (seg.lower() + "-040mp*.mp4"))))
    return Path(cands[-1]) if cands else None


def latest_regen(seg: str):
    pats = sorted(glob.glob(str(ROOT / "clips" / "raw" / "local-runner" /
                              (seg.lower() + "-040mp-regen_*.mp4"))))
    return Path(pats[-1]) if pats else None


def find_film(ep: str, variants=None):
    """在 06_delivery 里找该集成片：优先 progress 登记，再按常见命名匹配。

    2026-11-20 修：ep 是内部 ID（E01），而交付文件用中文命名（神豪-第01集-成片-HD.mp4），
    旧 pattern 只拼 `*E01*` → 明明有片也判"未成片"、分集点播空白。
    现在同时尝试数字变体（第01集 / 01集 / E01）。
    """
    deliv = ROOT / "06_delivery"
    if not deliv.is_dir():
        return None
    num = ep[1:] if ep[:1].isalpha() and ep[1:].isdigit() else ep
    if variants:
        pats = variants
    else:
        pats = [f"*{ep}*成片*.mp4", f"*第{num}集*成片*.mp4", f"*{num}集*成片*.mp4",
                f"*{ep}*.mp4", f"*第{num}集*.mp4", f"*{num}集*.mp4"]
    for pat in pats:
        hits = [p for p in deliv.glob(pat)
                if "无HUD" not in p.name and "存档" not in p.name and "-raw" not in p.name]
        if hits:
            # HD 优先（同名不同分辨率并存时，观众要看清晰那份），再按时间
            hits.sort(key=lambda p: ("HD" in p.name.upper() or "高清" in p.name,
                                     p.stat().st_mtime), reverse=True)
            return hits[0]
    return None


def ffprobe_duration(path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                           capture_output=True, text=True, timeout=15)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


# ---------- 资产友好名 ----------
def load_asset_names():
    """02_assets/ASSET_NAMES.json: {"slug 或 hash 前8位": "剧中名称"}"""
    return load_json(ASSET_NAMES_NAME, {})


def friendly_name(name: str) -> str:
    names = load_asset_names()
    stem = Path(name).stem
    if stem in names:
        return names[stem]
    if stem[:8] in names:
        return names[stem[:8]] + "（原图）"
    for pfx in ("scn_", "prp_", "chr_", "char_"):
        if stem.startswith(pfx) and stem[len(pfx):] in names:
            return names[stem[len(pfx):]]
    return ""


def md_label(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:5]:
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return ""


# ---------- 分镜解析 / 回写 ----------
SHOT_RE = re.compile(r"^\[(\d\d:\d\d\.\d+|\d+:\d\d)\]\s*(.*)$")


def parse_tc(tc: str) -> float:
    try:
        m, s = tc.split(":")
        return int(m) * 60 + float(s)
    except Exception:
        return 0.0


def parse_shots(prompt_text: str):
    """从 prompt.txt 解析结构化分镜：{time, shot, action, dialogue, camera, sound}"""
    shots = []
    for line in prompt_text.split("\n"):
        m = SHOT_RE.match(line.strip())
        if not m:
            continue
        tc, rest = m.group(1), m.group(2)
        camera, sound = "", ""
        cm = re.search(r"Camera:\s*(.*?)(?:\.\s*Sound at this moment:|\.$)", rest)
        sm = re.search(r"Sound at this moment:\s*(.*?)\.?\s*$", rest)
        body = rest
        if cm:
            camera = cm.group(1).strip()
            body = rest[:cm.start()].strip()
        if sm:
            sound = sm.group(1).strip().rstrip(".")
            body = re.sub(r"\s*Camera:.*$", "", body).strip()
            body = re.sub(r"\s*Sound at this moment:.*$", "", body).strip()
        dialogue = ""
        dm = re.search(r"<d>\[[^\]]*\]\s*(「.*?」)</d>", body)
        if dm:
            dialogue = dm.group(1)
            body = (body[:dm.start()] + body[dm.end():]).strip()
        shot, action = "", body
        am = re.match(r"^(.*?(?:shot|view|close-up|close up).*?)\s+"
                      r"(?:frames the scene|frames it|frames)\s*\.?\s+(.*)$", body, re.I)
        if am:
            shot = am.group(1).strip().rstrip(".")
            action = am.group(2).strip()
        else:
            shot = re.sub(r"\s*frames the scene\.?\s*$", "", body).strip()
        metadata = re.search(r"\[Continuity\](.*?)\[/Continuity\]", body)
        speaker = ""
        focus = ""
        if metadata:
            block = metadata.group(1)
            fm = re.search(r"Visual focus:\s*<([^>]+)>\.", block)
            smeta = re.search(r"Dialogue speaker:\s*<([^>]+)>\.", block)
            focus = fm.group(1) if fm else ""
            speaker = smeta.group(1) if smeta else ""
            body = (body[:metadata.start()] + body[metadata.end():]).strip()
            action = body
        shots.append({"time": tc, "shot": shot, "action": action,
                      "dialogue": dialogue, "camera": camera, "sound": sound,
                      "speaker": speaker, "focus": focus})
    return shots


def _safe_project_file(rel: str) -> Path | None:
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        return None
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return path


def _review_inputs(seg: str):
    base = f"04_feed/segments/{seg}"
    directory = _safe_project_file(base)
    if directory is None or not directory.is_dir():
        return None, []
    parts = {}
    sources = {}
    for name in ("prompt.txt", "continuity.json", "refs.json"):
        path = _safe_project_file(f"{base}/{name}")
        raw = path.read_bytes() if path and path.is_file() else None
        parts[name] = hashlib.sha256(raw).hexdigest() if raw is not None else None
        sources[name] = raw
    try:
        refs = json.loads(sources["refs.json"] or b"{}")
    except (ValueError, UnicodeError):
        refs = {}
    pictures = refs.get("pictures") if isinstance(refs, dict) else None
    image_hashes = {}
    if isinstance(pictures, dict):
        for slot, entry in pictures.items():
            rel = entry.get("file") if isinstance(entry, dict) else None
            path = _safe_project_file(rel)
            image_hashes[slot] = None
            if path and path.suffix.lower() in IMG_EXT and path.is_file():
                with path.open("rb") as image:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: image.read(1024 * 1024), b""):
                        digest.update(chunk)
                    image_hashes[slot] = digest.hexdigest()
    parts["images"] = image_hashes
    prompt = (sources["prompt.txt"] or b"").decode("utf-8-sig", errors="replace")
    shots = parse_shots(prompt)
    if shots:
        # 使用原始镜行作锚点，保留解析器未展示的台词或行内标记。
        contents = [m.group(2) for line in prompt.splitlines() if (m := SHOT_RE.match(line.strip()))]
    else:
        path = _safe_project_file(f"{base}/prompt.md")
        raw = path.read_bytes() if path and path.is_file() else None
        parts["prompt.md"] = hashlib.sha256(raw).hexdigest() if raw is not None else None
        shots = parse_shots_table((raw or b"").decode("utf-8-sig", errors="replace"))
        contents = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in shots]
    result, counts = [], {}
    for index, (item, content) in enumerate(zip(shots, contents), 1):
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        counts[digest] = counts.get(digest, 0) + 1
        result.append({"id": f"{digest}:{counts[digest]}", "index": index,
                       "time": item["time"], "shot": item["shot"]})
    fingerprint = hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()
    return fingerprint, result


def _load_reviews():
    data = load_json(REVIEW_NAME, {})
    return data if isinstance(data, dict) else {}


def _review_view(fingerprint, shots, record):
    ids = {s["id"] for s in shots}
    notes = [dict(n, orphaned=n["shot_id"] not in ids, stale=n["fingerprint"] != fingerprint)
             for n in record.get("notes", [])]
    decision = record.get("decision")
    if decision:
        state = decision["state"] if decision["fingerprint"] == fingerprint else "stale"
        if state == "approved" and any(n["status"] == "open" for n in notes):
            state = "pending"
    else:
        state = "stale" if any(n["stale"] or n["orphaned"] for n in notes) else "pending"
    return {"fingerprint": fingerprint, "state": state, "notes": notes, "shots": shots}


def get_review(seg: str):
    with _review_lock:
        fingerprint, shots = _review_inputs(seg)
        if fingerprint is None:
            return None
        return _review_view(fingerprint, shots, _load_reviews().get(seg, {}))


def update_review(seg: str, body: dict):
    if not isinstance(body, dict):
        return {"error": "审阅请求必须为 JSON 对象"}, 400
    action = body.get("action")
    with _review_lock:
        fingerprint, shots = _review_inputs(seg)
        if fingerprint is None:
            return {"error": "segment not found"}, 404
        all_reviews = _load_reviews()
        record = all_reviews.setdefault(seg, {"notes": [], "history": []})
        current = _review_view(fingerprint, shots, record)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        event = {"action": action, "at": now, "fingerprint": fingerprint}
        if action in ("comment", "approve", "request_changes") and (
                action != "comment" or "fingerprint" in body) and body.get("fingerprint") != fingerprint:
            return {"error": "版本已变更，请刷新后重试", "review": current}, 409
        if action == "comment":
            shot_id, text = body.get("shot_id"), body.get("text")
            if not isinstance(shot_id, str) or shot_id not in {s["id"] for s in shots}:
                return {"error": "镜头已变化，请刷新后重试", "review": current}, 409
            if not isinstance(text, str) or not text.strip():
                return {"error": "批注不能为空"}, 400
            note = {"id": f"N{len(record['history']) + 1}", "shot_id": shot_id,
                    "text": text.strip(), "status": "open", "fingerprint": fingerprint,
                    "created_at": now}
            record["notes"].append(note)
            event["note_id"] = note["id"]
            if current["state"] == "approved":
                record.pop("decision")
        elif action == "resolve":
            note = next((n for n in record["notes"] if n["id"] == body.get("id")), None)
            if note is None:
                return {"error": "未找到批注"}, 404
            if note["status"] == "resolved":
                return current, 200
            note["status"] = "resolved"
            event["note_id"] = note["id"]
        elif action in ("approve", "request_changes"):
            if action == "approve" and any(n["status"] == "open" for n in record["notes"]):
                return {"error": "请先解决所有开放批注", "review": current}, 409
            record["decision"] = {"state": "approved" if action == "approve" else "changes_requested",
                                  "fingerprint": fingerprint, "created_at": now}
        else:
            return {"error": "不支持的审阅操作"}, 400
        record["history"].append(event)
        _atomic_save_json(REVIEW_NAME, all_reviews)
        return _review_view(fingerprint, shots, record), 200


def build_production():
    rows = []
    for episode in build_manifest().get("episodes", []):
        for item in episode.get("segs", []):
            review = get_review(item["id"])
            notes = review.get("notes", []) if review else []
            rows.append({"segment": item["id"], "episode": episode["id"],
                         "review_state": review["state"] if review else "pending",
                         "open_notes": sum(n["status"] == "open" for n in notes),
                         "has_clip": item["has_clip"], "shot_count": len(review.get("shots", [])) if review else 0})
    counts = dict.fromkeys(("pending", "approved", "stale", "changes_requested"), 0)
    for row in rows:
        counts[row["review_state"]] += 1
    return {"segments": rows, "summary": {"total": len(rows), **counts,
            "with_clip": sum(1 for r in rows if r["has_clip"]),
            "open_notes": sum(r["open_notes"] for r in rows)}}


def parse_shots_table(md_text: str):
    """H3 线兜底：从 prompt.md 的「段落卡」表格解析分镜。

    2026-11-18 新增。病根：SHOT_RE 只认 `^[mm:ss] ...`，而 MiniMax-H3 的提示词是一段
    连续字段文本、镜内用 `[Shot N]` 推进 —— 于是一份完全合规的 H3 稿在导演台里
    「镜头 0 个、分镜卡空白」，看起来像没数据。这里从同目录 prompt.md 的分镜卡表格兜底，
    不动 prompt.txt（投喂原文必须保持纯净）。
    """
    shots = []
    in_table = False
    for line in md_text.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            if in_table and s:
                in_table = False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if not in_table:
            if any("镜" in c for c in cells) and any("秒" in c for c in cells):
                in_table = True
            continue
        m = re.match(r"(\d+(?:\.\d+)?)\s*[–—\-~]\s*(\d+(?:\.\d+)?)",
                     cells[1] if len(cells) > 1 else "")
        start, end = (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
        shots.append({
            "time": f"{start:g}-{end:g}s",
            "shot": cells[2] if len(cells) > 2 else "",
            "action": cells[4] if len(cells) > 4 else "",
            "dialogue": cells[5] if len(cells) > 5 else "",
            "camera": cells[3] if len(cells) > 3 else "",
            "sound": "", "speaker": "", "focus": "",
        })
    return shots


def rebuild_prompt(prompt_text: str, shots) -> str:
    """把编辑后的分镜写回 prompt.txt；只替换镜头行，其余段落原样保留。"""
    # 2026-11-18 保护：H3 稿没有 [mm:ss] 镜行，写回会把 Seedance 格式的行插进字段中间，
    # 直接污染投喂原文 → 一律原样返回。
    if not any(SHOT_RE.match(l.strip()) for l in prompt_text.split("\n")):
        return prompt_text
    new_lines = []
    for s in shots:
        shot = (s.get("shot") or "").strip()
        action = (s.get("action") or "").strip()
        line = "[%s] %s frames the scene. %s" % (
            s.get("time", "00:00.000"), shot, action) if action else \
            "[%s] %s frames the scene." % (s.get("time", "00:00.000"), shot)
        if (s.get("dialogue") or "").strip():
            line += " <d>[Chinese]%s</d>" % s["dialogue"].strip()
        if (s.get("camera") or "").strip():
            line += " Camera: %s." % s["camera"].strip().rstrip(".")
        if (s.get("sound") or "").strip():
            line += " Sound at this moment: %s." % s["sound"].strip().rstrip(".")
        new_lines.append(line)
    out, idx = [], 0
    for line in prompt_text.split("\n"):
        if SHOT_RE.match(line.strip()):
            if idx < len(new_lines):
                out.append(new_lines[idx])
                idx += 1
        else:
            out.append(line)
    if idx < len(new_lines):
        extra = new_lines[idx:]
        res, inserted = [], False
        for line in out:
            if not inserted and re.match(r"^\s*(overall_soundscape|non_diegetic_music)", line):
                res.extend(extra)
                inserted = True
            res.append(line)
        if not inserted:
            res.extend(extra)
        out = res
    return "\n".join(out)


FRAME_DIR_NAME = "05_qc/machine/storyboard"


def ensure_shot_frames(seg, shots):
    """按每镜时间码从成片抽一帧（镜头中部），缓存。返回相对路径列表。"""
    d = ROOT / FRAME_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    clip = clip_for_seg(seg)
    frames = []
    if not clip:
        return [""] * len(shots)
    for i, s in enumerate(shots):
        out = d / f"{seg}_shot{i + 1}.png"
        if not out.is_file():
            t = parse_tc(s.get("time", "00:00.000")) + 1.0
            subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}",
                            "-i", str(clip), "-frames:v", "1", "-y", str(out)],
                           capture_output=True, timeout=30)
        frames.append(out.relative_to(ROOT).as_posix() if out.is_file() else "")
    return frames


# ---------- Manifest / 详情 ----------
def build_manifest():
    eps = []
    for ep, (lo, hi) in scan_episodes().items():
        film = find_film(ep)
        segs = []
        for n in range(lo, hi + 1):
            seg = f"S{n:02d}"
            sd = ROOT / "04_feed" / "segments" / seg
            clip = clip_for_seg(seg)
            qc = ROOT / "05_qc" / "machine" / "batch" / f"qc-{seg}.png"
            segs.append({
                "id": seg, "title": seg_title(seg),
                "has_prompt": (sd / "prompt.txt").is_file(),
                "has_clip": bool(clip),
                "clip": clip.relative_to(ROOT).as_posix() if clip else "",
                "has_qc": qc.is_file(),
                "has_regen": bool(latest_regen(seg)),
                "asset_update": load_status().get(seg, {}).get("asset_update"),
            })
        script_path = ROOT / "01_script" / "episodes" / f"{ep}.md"
        eps.append({
            "id": ep, "title": episode_title(ep),
            "chapters": episode_chapters(ep),
            "cover": episode_cover(ep),
            "synopsis": episode_synopsis(script_path),
            "runtime_minutes": round(ffprobe_duration(film) / 60, 2) if film else 0,
            "has_script": (ROOT / "01_script" / "episodes" / f"{ep}.md").is_file(),
            "film": film.relative_to(ROOT).as_posix() if film else "",
            "duration": round(ffprobe_duration(film), 3) if film else 0,
            "segs": segs,
        })
    full = find_film("全集", ["*连播*.mp4", "*全集*.mp4"])
    return {"root": str(ROOT), "title": TITLE, "episodes": eps,
            "jobs": load_jobs(),
            "fullfilm": full.relative_to(ROOT).as_posix() if full else ""}


def read_episode(ep: str):
    f = ROOT / "01_script" / "episodes" / f"{ep}.md"
    return f.read_text(encoding="utf-8") if f.is_file() else None


def project_scope() -> dict:
    """范围限制（硬门）：本包只服务中文短剧。

    PROJECT_INFO 里 language 缺省视为 zh-CN（历史项目不受影响）；
    一旦显式写成非中文，出片与提示词编译一律拒绝，避免"改个字段就绕过"。
    """
    info = load_json("00_source/PROJECT_INFO.json", {})
    info = info if isinstance(info, dict) else {}
    lang = str(info.get("language") or "zh-CN").strip()
    form = str(info.get("form") or "中文短剧").strip()
    chinese = lang.lower().startswith(("zh", "cn", "chinese")) or lang in ("中文", "简体中文")
    return {
        "language": lang,
        "form": form,
        "ok": chinese,
        "allowed": ["zh-CN", "中文短剧"],
        "reason": "" if chinese else f"language={lang} 不在范围：本技能只做中文短剧（普通话对白 + 简体字幕）",
    }


def scope_gate() -> None:
    """任何实际生成动作前调用；不在范围就抛错。"""
    scope = project_scope()
    if not scope["ok"]:
        raise RuntimeError("范围限制：" + scope["reason"])


def console_info() -> dict:
    """读取安装清单（由 install_director_console.py 写入），用于显示当前副本版本。"""
    here = Path(__file__).resolve().parent
    for name in ("安装清单.json", ".console.json"):
        manifest = here / name
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return {"version": data.get("console_version", ""),
                "installed_at": data.get("installed_at", "")}
    return {}


def build_overview():
    """总览聚合：项目设定 + 每集发布元数据 + 进度。缺项返回空串，由前端显示待补。"""
    info = load_json("00_source/PROJECT_INFO.json", {})
    info = info if isinstance(info, dict) else {}
    eps = build_manifest()["episodes"]
    ep_info = info.get("episodes") if isinstance(info.get("episodes"), dict) else {}
    total_segs = sum(len(e["segs"]) for e in eps)
    ready_segs = sum(1 for e in eps for s in e["segs"] if s["has_clip"])
    rows = []
    for e in eps:
        meta = ep_info.get(e["id"]) if isinstance(ep_info.get(e["id"]), dict) else {}
        rows.append({
            **e,
            "hongguo_title": meta.get("hongguo_title") or meta.get("title") or "",
            "publish_synopsis": meta.get("synopsis") or e["synopsis"],
            "publish_cover": meta.get("cover") or e["cover"],
            "tags": meta.get("tags") or [],
            "publish_note": meta.get("note") or "",
        })
    return {
        "title": info.get("title") or TITLE,
        "style": info.get("style") or "",
        "genre": info.get("genre") or "",
        "model": info.get("model") or "",
        "aspect": info.get("aspect") or "",
        "episode_seconds": info.get("episode_seconds") or 0,
        "episodes_total": info.get("episodes_total") or len(eps),
        "audience": info.get("audience") or "",
        "logline": info.get("logline") or "",
        "has_project_info": bool(info),
        "generator_ready": bool(image_gen_path()),
        "image_generator_ready": bool(image_gen_path()),
        "image_engine": {
            "ready": bool(image_gen_path()),
            "path": str(image_gen_path() or ""),
            "default": info.get("image_engine") or DEFAULT_IMG_ENGINE,
            "local_comfyui": "http://127.0.0.1:8188",
        },
        "submit_ready": h3_status()["ready"] or (ROOT / "tools" / "submit_seg.py").is_file(),
        "video_engine": {"local_h3": h3_status(),
                         "fallback_submit": (ROOT / "tools" / "submit_seg.py").is_file()},
        "segments_total": total_segs,
        "segments_ready": ready_segs,
        "console": console_info(),
        "scope": project_scope(),
        "episodes": rows,
        "missing_fields": [k for k in ("style", "episode_seconds", "episodes_total") if not info.get(k)],
    }


def _segment_refs_index():
    """({资产相对路径: [段号]}, {文件名: [段号]})。

    优先用 refs.json；缺失时回退扫描 prompt.txt 的 `<Picture N> (文件名)`，
    两种来源都只是“引用关系”，不据此推断画面是否一致。
    """
    index, by_name = {}, {}
    seg_dir = ROOT / "04_feed" / "segments"
    if not seg_dir.is_dir():
        return index, by_name
    for d in sorted(seg_dir.glob("S*")):
        if not d.is_dir():
            continue
        found = False
        try:
            refs = json.loads((d / "refs.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            refs = {}
        for entry in (refs.get("pictures") or {}).values():
            rel = entry.get("file") if isinstance(entry, dict) else ""
            if rel:
                index.setdefault(rel, []).append(d.name)
                by_name.setdefault(Path(rel).name, []).append(d.name)
                found = True
        if found:
            continue
        prompt = d / "prompt.txt"
        if not prompt.is_file():
            continue
        try:
            text = prompt.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in re.finditer(r"<Picture\s+\d+>\s*\(([^)]+)\)", text):
            name = Path(match.group(1).strip()).name
            if name:
                by_name.setdefault(name, []).append(d.name)
    return index, by_name


def build_characters():
    """人物卡 + 关系图谱数据。未登记但有图的角色也会列出，不隐藏素材。"""
    raw = load_json("02_assets/CHARACTERS.json", {})
    raw = raw if isinstance(raw, dict) else {}
    chars = raw.get("characters") if isinstance(raw.get("characters"), list) else []
    relations = raw.get("relations") if isinstance(raw.get("relations"), list) else []
    prompts = load_image_prompts()
    refs_index, refs_by_name = _segment_refs_index()

    def enrich(rel):
        entry = prompts.get(rel) or {}
        segs = refs_index.get(rel) or refs_by_name.get(Path(rel).name) or []
        return {
            "path": rel,
            "exists": (ROOT / rel).is_file(),
            "prompt": entry.get("prompt", ""),
            "regenerable": bool(entry),
            "segments": sorted(set(segs)),
            "name": entry.get("name", ""),
        }

    out = []
    declared = set()
    for c in chars:
        if not isinstance(c, dict):
            continue
        anchors = c.get("anchors") if isinstance(c.get("anchors"), dict) else {}
        files = []
        for key, rel in anchors.items():
            if isinstance(rel, str) and rel:
                declared.add(rel)
                files.append({"slot": key, **enrich(rel)})
        out.append({
            "id": c.get("id") or c.get("name", ""),
            "name": c.get("name", ""),
            "role": c.get("role", ""),
            "rank": c.get("rank", ""),
            "personality": c.get("personality", ""),
            "identity": c.get("identity", ""),
            "appearance": c.get("appearance", ""),
            "outfit": c.get("outfit", ""),
            "voice": c.get("voice", ""),
            "note": c.get("note", ""),
            "registered": True,
            "anchors": files,
        })

    char_dir = ROOT / "02_assets" / "characters"
    if char_dir.is_dir():
        for p in sorted(char_dir.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in IMG_EXT:
                continue
            if BAK_RE.search(p.name):   # 备份图不算角色
                continue
            rel = p.relative_to(ROOT).as_posix()
            base = p.stem
            if any(rel == d or base in d for d in declared):
                continue
            entry = enrich(rel)
            out.append({
                "id": f"auto_{base}", "name": entry["name"] or base,
                "role": "", "rank": "", "personality": "", "identity": "",
                "appearance": "", "outfit": "", "voice": "", "note": "",
                "registered": False, "anchors": [{"slot": "image", **entry}],
            })

    known_ids = {c["id"] for c in out}
    valid_relations = [r for r in relations if isinstance(r, dict)
                       and r.get("from") in known_ids and r.get("to") in known_ids]
    return {
        "registered": bool(chars),
        "characters": out,
        "relations": valid_relations,
        "dropped_relations": len(relations) - len(valid_relations),
    }


def build_chapters():
    """按章节切分原著；支持 md 标题与纯文本“第N章”两种写法。"""
    src = ROOT / "00_source"
    path = src / "novel.md"
    if not path.is_file():
        candidates = sorted(src.glob("*.md")) if src.exists() else []
        path = next((p for p in candidates if "小说" in p.name or "原著" in p.name), candidates[0] if candidates else None)
    mappings = load_json("01_script/adaptation_map.json", [])
    if not path or not path.is_file():
        return {"source": "", "chapters": [], "mappings": mappings}
    text = path.read_text(encoding="utf-8")

    patterns = [
        r"(?m)^#{1,4}[ \t]*(第[^\n]{1,24}?章[^\n]*)$",
        r"(?m)^(第[0-9一二三四五六七八九十百千零〇两]{1,8}章[^\n]*)$",
    ]
    matches = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text))
        if len(matches) >= 2:
            break
    chapters = []
    if len(matches) >= 1:
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[match.end():end].strip()
            chapters.append({
                "title": match.group(1).strip(),
                "content": body,
                "words": len(re.sub(r"\s+", "", body)),
            })
    else:
        body = text.strip()
        chapters = [{"title": path.stem, "content": body, "words": len(re.sub(r"\s+", "", body))}]
    return {"source": path.relative_to(ROOT).as_posix(), "chapters": chapters, "mappings": mappings}


SEGMENT_ID_RE = re.compile(r"^S\d{2,}$")


def continuity_previous(ledger):
    if "previous_segment" not in ledger:
        return None
    previous_id = ledger["previous_segment"]
    if not isinstance(previous_id, str) or not SEGMENT_ID_RE.fullmatch(previous_id):
        return {"scene": None, "_load_error": "previous_segment 格式非法"}
    try:
        previous = continuity.load_ledger(ROOT, previous_id)
        if continuity.validate_ledger(previous)["status"] != "pass":
            return {"scene": None, "_load_error": f"前段 {previous_id} 台账未通过验证"}
        return previous
    except (ValueError, OSError) as exc:
        return {"scene": None, "_load_error": f"前段 {previous_id} 台账无法读取: {exc}"}


def reference_gate(seg, prompt_text, refs):
    """校验提示词 Picture 槽位、refs.json 文件映射和本地文件存在性。"""
    pictures = refs.get("pictures") if isinstance(refs, dict) else None
    if not isinstance(pictures, dict) or not pictures:
        return [{"code": "MISSING_REFERENCE_SLOTS", "message": f"{seg} refs.json 没有 pictures"}]
    errors = []
    slot_files = {}
    for slot, entry in pictures.items():
        if not re.fullmatch(r"Picture \d+", str(slot)) or not isinstance(entry, dict):
            errors.append({"code": "INVALID_REFERENCE_SLOT", "field": str(slot), "message": "参考图槽位格式或内容非法"})
            continue
        file_name = str(entry.get("file", ""))
        slot_files[slot] = Path(file_name).name
        if not file_name or not (ROOT / file_name).is_file():
            errors.append({"code": "MISSING_REFERENCE_FILE", "field": slot, "message": f"参考图文件不存在: {file_name}"})
    seen = set()
    for match in re.finditer(r"<Picture\s+(\d+)>\s*\(([^)]+)\)", prompt_text or ""):
        slot = f"Picture {match.group(1)}"
        filename = Path(match.group(2)).name
        seen.add(slot)
        if slot not in slot_files:
            errors.append({"code": "DANGLING_REFERENCE_SLOT", "field": slot, "message": f"提示词引用了 refs.json 不存在的 {slot}"})
        elif slot_files[slot] != filename:
            errors.append({"code": "REFERENCE_FILENAME_MISMATCH", "field": slot, "message": f"提示词文件名 {filename} 与 refs.json 文件名 {slot_files[slot]} 不一致"})
    for slot in slot_files:
        if slot not in seen:
            errors.append({"code": "UNUSED_REFERENCE_SLOT", "field": slot, "message": f"refs.json 的 {slot} 未在提示词中引用"})
    return errors


def continuity_details(seg):
    prompt_path = ROOT / "04_feed" / "segments" / seg / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    try:
        ledger = continuity.load_ledger(ROOT, seg)
        shots = continuity._markers(continuity.BLOCK.sub("", prompt), ledger.get("shots", []))
        ledger["_expected_shots"] = [{"start": start, "end": end} for _, (start, end) in shots]
    except Exception as exc:
        return {"ledger": None, "prompt": prompt, "report": {
            "status": "blocked", "errors": [{"code": "INVALID_LEDGER", "message": str(exc)}],
            "warnings": [], "evidence": {"text_only": True, "film_verified": False}}}
    previous = continuity_previous(ledger)
    report = continuity.validate_ledger(ledger, prompt, previous)
    if isinstance(previous, dict) and previous.get("_load_error"):
        report.setdefault("errors", []).append({
            "code": "INVALID_PREVIOUS",
            "field": "previous_segment",
            "message": previous["_load_error"],
        })
        report["status"] = "blocked"
    report.setdefault("reference_errors", reference_gate(seg, prompt, _read_refs(seg)))
    if report["reference_errors"]:
        report["status"] = "blocked"
    return {"ledger": ledger, "prompt": prompt, "report": report}


def _read_refs(seg):
    path = ROOT / "04_feed" / "segments" / seg / "refs.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_segment(seg: str):
    sd = ROOT / "04_feed" / "segments" / seg
    if not sd.is_dir():
        return None

    def rd(name):
        f = sd / name
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    refs = {}
    try:
        refs = json.loads(rd("refs.json") or "{}")
    except Exception:
        pass
    pictures = []
    for k, v in (refs.get("pictures") or {}).items():
        fp = v.get("file", "")
        pictures.append({"slot": k, "role": v.get("role", ""),
                         "file": fp if (ROOT / fp).is_file() else ""})
    prompt_txt = rd("prompt.txt")
    shots = parse_shots(prompt_txt)
    if not shots:
        # H3 线：提示词无 [mm:ss] 镜行 → 从 prompt.md 的分镜卡表格兜底
        shots = parse_shots_table(rd("prompt.md"))
    frames = ensure_shot_frames(seg, shots)
    st = load_status().get(seg, {})
    for i, fr in enumerate(frames):
        shots[i]["frame"] = fr
        shots[i]["status"] = st.get(str(i + 1), "ok")
    clip = clip_for_seg(seg)
    regen = latest_regen(seg)
    qc = ROOT / "05_qc" / "machine" / "batch" / f"qc-{seg}.png"
    return {
        "id": seg, "episode": seg_episode(seg), "title": seg_title(seg),
        "duration": ffprobe_duration(clip) if clip else 0,
        "prompt_txt": prompt_txt, "prompt_md": rd("prompt.md"),
        "shots": shots, "refs": refs, "pictures": pictures,
        "continuity": continuity_details(seg),
        "asset_update": load_status().get(seg, {}).get("asset_update"),
        "clip": clip.relative_to(ROOT).as_posix() if clip else "",
        "regen": regen.relative_to(ROOT).as_posix() if regen else "",
        "qc": qc.relative_to(ROOT).as_posix() if qc.is_file() else "",
    }


def build_assets():
    lib = load_image_prompts()
    regen_set = set(lib.keys())
    out = {g[0]: [] for g in ASSET_GROUPS}
    out["other"] = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            # 2026-11-18 修：_bak 是重生图留下的备份（do_regen_image 自己这么起名），
            # 不排除会把每张备份都列成一张新资产、每个角色都多出一张卡。
            if f.startswith(".") or f == "board.html" or BAK_RE.search(f):
                continue
            p = Path(dp) / f
            rel = p.relative_to(ROOT).as_posix()
            key = "other"
            for k, pref, _ in ASSET_GROUPS:
                if rel.startswith(pref + "/") or rel == pref:
                    key = k
                    break
            try:
                stt = p.stat()
            except OSError:
                continue
            ext = p.suffix.lower()
            kind = ("video" if ext in VID_EXT else "image" if ext in IMG_EXT
                    else "text" if ext in TEXT_EXT else "file")
            label = md_label(p) if kind == "text" and ext == ".md" else ""
            entry = lib.get(rel) or {}
            out.setdefault(key, []).append({
                "name": f, "path": rel, "size": stt.st_size,
                "ext": ext.lstrip(".") or "file", "kind": kind,
                "label": label, "fname": friendly_name(f),
                "regenerable": rel in regen_set,
                "prompt": entry.get("prompt", "") if rel in regen_set else "",
                "asset_kind": entry.get("kind", "") if rel in regen_set else "",
                "last_generated": entry.get("last_generated", "") if rel in regen_set else "",
                "mtime": time.strftime("%m-%d %H:%M", time.localtime(stt.st_mtime)),
                "exists": True,
            })
    # 2026-11-18 修：已配置提示词但图还没生成的资产也要列出来。
    # 病根：本函数只扫真实文件，IMG 提示词写了但一张图都没出时，「道具/场景」页是全空的，
    # 用户看到的是"不能编辑、也没提示词"——其实提示词在 IMAGE_PROMPTS.json 里，只是没入口。
    # 现在把 lib 里尚未落盘的条目作为 exists=False 的"待出图"卡片补进来，可点开改词/直接生成。
    listed = {e["path"] for v in out.values() for e in v}
    for rel, entry in lib.items():
        if not isinstance(entry, dict) or rel in listed:
            continue
        key = "other"
        for k, pref, _ in ASSET_GROUPS:
            if rel.startswith(pref + "/") or rel == pref:
                key = k
                break
        nm = Path(rel).name
        out.setdefault(key, []).append({
            "name": nm, "path": rel, "size": 0,
            "ext": Path(rel).suffix.lstrip(".") or "file", "kind": "image",
            "label": entry.get("name", ""), "fname": friendly_name(nm),
            "regenerable": True,
            "prompt": entry.get("prompt", ""),
            "asset_kind": entry.get("kind", ""),
            "last_generated": entry.get("last_generated", ""),
            "mtime": "", "exists": False,
        })
    for v in out.values():
        v.sort(key=lambda x: (not x.get("exists", True), x["path"]))
    return {"groups": [{"key": k, "label": lab} for k, _, lab in ASSET_GROUPS]
                      + [{"key": "other", "label": "其他"}],
            "data": out}


# ---------- 任务 ----------
def new_job(kind, label):
    job_id = f"{kind}-{label}-{int(time.time())}"
    jobs = load_jobs()
    jobs.append({"id": job_id, "kind": kind, "label": label,
                 "status": "queued", "submitted_at": time.strftime("%H:%M:%S")})
    save_jobs(jobs)
    return job_id


def _set_job(job_id, **kw):
    jobs = load_jobs()
    for j in jobs:
        if j["id"] == job_id:
            j.update(kw)
    save_jobs(jobs)


def do_regen(seg):
    scope_gate()
    sd = ROOT / "04_feed" / "segments" / seg
    prompt = sd / "prompt.txt"
    if not prompt.is_file() or not prompt.read_text(encoding="utf-8").strip():
        raise RuntimeError("提示词为空")
    verdict = continuity_details(seg)["report"]
    if verdict["status"] != "pass" or verdict.get("evidence", {}).get("speaker_binding_verified") is not True:
        raise RuntimeError("连续性复核未通过，禁止生成: " + json.dumps(verdict, ensure_ascii=False))
    details = read_segment(seg)
    reference_errors = verdict.get("reference_errors") or reference_gate(
        seg, prompt.read_text(encoding="utf-8"), _read_refs(seg))
    if reference_errors:
        raise RuntimeError("参考图接线未通过，禁止生成: " + json.dumps(reference_errors, ensure_ascii=False))
    refs = [str(ROOT / p["file"]) for p in details["pictures"] if p["file"]]
    if not refs:
        raise RuntimeError("refs.json 中没有可用参考图")

    local = h3_status()
    if local["ready"]:
        return _regen_local_h3(seg, details)
    submit = _first_file(ROOT / "tools" / "submit_seg.py", Path(__file__).resolve().parent / "submit_seg.py")
    if submit:
        label = f"{seg.lower()}-040mp-regen"
        job_id = new_job("regen", seg)
        cmd = [PY, str(submit), "--label", label, "--prompt", str(prompt), "--refs"] + refs + \
              ["--seconds", "10", "--aspect", "9:16 (Portrait Widescreen)", "--mp", "0.4"]
        threading.Thread(target=_run_cmd, args=(job_id, cmd), daemon=True).start()
        return job_id
    raise RuntimeError("本地 H3 未就绪：" + local["reason"] +
                       "；也没有项目侧 tools/submit_seg.py。请先按 comfyui-h3-local-runner 跑通一条并 capture 模板。")


# ---------- 本地 H3 出片（comfyui-h3-local-runner） ----------
def _h3_settings():
    info = load_json("00_source/PROJECT_INFO.json", {})
    h3 = info.get("h3") if isinstance(info.get("h3"), dict) else {}
    return {
        "fps": int(h3.get("fps") or 24),
        "width": int(h3.get("width") or 720),
        "height": int(h3.get("height") or 1280),
        "scale": float(h3.get("scale") or 0.4),
        "timeout": int(h3.get("timeout_seconds") or 1800),
    }


def _h3_call(args, timeout=120):
    runner, py = h3_runner_path(), h3_python()
    if not runner:
        raise RuntimeError("未找到 h3_runner.py")
    cmd = [str(py), str(runner)] + args
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    text = (proc.stdout or "").strip()
    payload = {}
    if text:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start:end + 1])
            except ValueError:
                payload = {}
    if proc.returncode != 0 and not payload:
        raise RuntimeError((proc.stderr or text or "h3_runner 失败")[-600:])
    return payload, proc


def _regen_local_h3(seg, details):
    cfg = _h3_settings()
    try:
        spec = h3_spec.build_spec(ROOT, seg, cfg["fps"], cfg["width"], cfg["height"])
    except ValueError as exc:
        raise RuntimeError(f"无法生成 H3 spec：{exc}")
    spec_path = ROOT / SPECS_DIR / f"{seg}.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    label = f"{seg.lower()}-040mp-regen"
    job_id = new_job("regen", seg)
    threading.Thread(target=_run_local_h3_job,
                     args=(job_id, seg, spec_path, label, cfg), daemon=True).start()
    return job_id


def _run_local_h3_job(job_id, seg, spec_path, label, cfg):
    _set_job(job_id, status="running", started_at=time.strftime("%H:%M:%S"),
             note="本地 H3 提交中")
    try:
        payload, proc = _h3_call(["submit", "--project", str(ROOT), "--director-spec", str(spec_path),
                                  "--scale", str(cfg["scale"]), "--label", label])
        if not payload.get("submitted"):
            raise RuntimeError((proc.stderr or proc.stdout or "提交失败")[-600:])
        prompt_id = payload.get("prompt_id", "")
        _set_job(job_id, note=f"ComfyUI 排队中 · {prompt_id[:8]}", prompt_id=prompt_id)
        deadline = time.time() + cfg["timeout"]
        downloaded, status = [], "unknown"
        while time.time() < deadline:
            time.sleep(5)
            state, _ = _h3_call(["status", "--project", str(ROOT), "--download"])
            status = state.get("status", "unknown")
            if state.get("completed") and status == "success":
                downloaded = state.get("downloaded") or []
                break
            if status in ("error", "failed"):
                raise RuntimeError("ComfyUI 任务失败：" + json.dumps(state, ensure_ascii=False)[:400])
        if not downloaded:
            raise RuntimeError(f"等待超时或没有产出（status={status}）")
        src = Path(downloaded[-1])
        if not src.is_file():
            raise RuntimeError(f"下载文件不存在：{src}")
        out_dir = ROOT / "clips" / "raw" / "local-runner"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dst = out_dir / f"{seg.lower()}-040mp-regen_{stamp}{src.suffix or '.mp4'}"
        shutil.copy2(src, dst)
        _set_job(job_id, status="success", finished_at=time.strftime("%H:%M:%S"),
                 output=dst.relative_to(ROOT).as_posix(), note="已下载并登记为新版本")
    except Exception as e:
        _set_job(job_id, status="error", finished_at=time.strftime("%H:%M:%S"), error=str(e)[:900])


def _run_cmd(job_id, cmd):
    _set_job(job_id, status="running", started_at=time.strftime("%H:%M:%S"))
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=7200)
        ok = p.returncode == 0
        _set_job(job_id, status="success" if ok else "error",
                 finished_at=time.strftime("%H:%M:%S"),
                 output=(p.stdout or "")[-3000:],
                 **({"error": (p.stderr or "")[-1500:]} if not ok else {}))
    except Exception as e:
        _set_job(job_id, status="error", finished_at=time.strftime("%H:%M:%S"), error=str(e)[:600])


def do_promote(seg):
    regen = latest_regen(seg)
    if not regen:
        raise RuntimeError("没有重新生成的片段")
    prog = load_progress()
    prog.setdefault("done", {})[seg] = str(regen)
    save_json(PROGRESS_NAME, prog)
    return regen.relative_to(ROOT).as_posix()


def do_assemble(ep):
    segs = scan_episodes().get(ep)
    if not segs:
        raise RuntimeError("未知集数")
    lo, hi = segs
    prog = load_progress()["done"]
    clips = []
    for n in range(lo, hi + 1):
        seg = f"S{n:02d}"
        p = prog.get(seg)
        if not (p and Path(p).is_file()):
            raise RuntimeError(f"缺少 {seg} 成片，无法拼接")
        clips.append(str(p))
    assemble = Path(__file__).resolve().parent / "assemble_episodes.py"
    job_id = new_job("assemble", ep)
    if assemble.is_file():
        t = threading.Thread(target=_run_cmd, args=(job_id, [PY, str(assemble), ep]), daemon=True)
    else:
        t = threading.Thread(target=_assemble_inline, args=(job_id, ep, clips), daemon=True)
    t.start()
    return job_id


def _assemble_inline(job_id, ep, clips):
    """无 assemble_episodes.py 时的内置拼接（concat demuxer + 音频归一）。"""
    _set_job(job_id, status="running", started_at=time.strftime("%H:%M:%S"))
    try:
        lst = work_tmp(f"concat_{ep}.txt")
        lst.parent.mkdir(parents=True, exist_ok=True)
        lst.write_text("".join(f"file '{Path(c).as_posix()}'\n" for c in clips), encoding="utf-8")
        out = ROOT / "06_delivery" / f"{TITLE or ROOT.name}-{ep}-60s-成片.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", str(lst), "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)],
                           capture_output=True, text=True, timeout=1800)
        ok = r.returncode == 0
        _set_job(job_id, status="success" if ok else "error",
                 finished_at=time.strftime("%H:%M:%S"),
                 output=out.relative_to(ROOT).as_posix() if ok else "",
                 **({"error": (r.stderr or "")[-1200:]} if not ok else {}))
    except Exception as e:
        _set_job(job_id, status="error", finished_at=time.strftime("%H:%M:%S"), error=str(e)[:600])


# ---------- 图片重生成（本机 Image Forge · ComfyUI 8188 优先） ----------
def do_regen_image(rel, job_id):
    scope_gate()
    lib = load_image_prompts()
    entry = lib.get(rel)
    if not entry:
        raise RuntimeError("该图片没有提示词配置")
    gen = image_gen_path()
    if not gen:
        raise RuntimeError("未找到本机生图器：期望 D:/WorkBuddyProject/AI生图/start.py，"
                           "或用环境变量 SD_IMAGE_GEN 指定")
    prompt = (entry.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("提示词为空")
    engine = entry.get("engine") or DEFAULT_IMG_ENGINE
    tf = work_tmp(f"imgprompt_{job_id.replace('-', '_')}.txt")
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(prompt, encoding="utf-8", newline="\n")
    cmd = [PY, str(gen), "gen", "--engine", engine,
           "--preset", entry.get("preset", "draft"),
           "--prompt-file", str(tf), "--json"]
    if entry.get("size"):
        cmd += ["--size", str(entry["size"])]
    if entry.get("seed"):
        cmd += ["--seed", str(entry["seed"])]
    for ref in entry.get("references") or []:
        ref_path = (ROOT / ref) if not Path(ref).is_absolute() else Path(ref)
        if not Path(ref_path).is_file():
            raise RuntimeError(f"参考图不存在：{ref}")
        cmd += ["--reference", str(ref_path)]
    _set_job(job_id, status="running", started_at=time.strftime("%H:%M:%S"),
             note=f"本机 {engine} 出图中")
    r = subprocess.run(cmd, cwd=str(gen.parent), capture_output=True, text=True, timeout=1800)
    record = {}
    text = (r.stdout or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            record = json.loads(text[start:end + 1])
        except ValueError:
            record = {}
    if r.returncode != 0 or record.get("status") not in (None, "ok"):
        raise RuntimeError("生图失败: " + str(record.get("error") or (r.stderr or text))[-500:])
    images = record.get("images") or []
    if not images:
        raise RuntimeError("生图没有返回图片路径：" + (text[-300:] or "无输出"))
    src = Path(images[0])
    if not src.is_file():
        raise RuntimeError(f"生图返回的路径不存在：{src}")
    dst = ROOT / rel
    if dst.is_file():
        bak = dst.with_name(dst.stem + "_bak" + dst.suffix)
        if not bak.exists():
            shutil.copy2(dst, bak)
    dst.parent.mkdir(parents=True, exist_ok=True)
    previous_version = _snapshot(dst, "") if dst.is_file() else ""
    shutil.copy2(src, dst)
    # ★2026-11-20 修「生图任务回写旧快照覆盖别人修改」：
    #   原来直接 save_image_prompts(lib)，而 lib 是任务**提交时**加载的快照——批量重生成场景/道具时，
    #   会把这段时间里手工改过的其它条目（如角色提示词）一起冲回旧版（实测把知夏新版冲成旧版两次）。
    #   现在读最新盘、只更新本条 last_generated，其它条目一概不动。
    fresh = load_image_prompts()
    entry = dict(fresh.get(rel) or lib.get(rel) or {})
    entry["last_generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    fresh[rel] = entry
    save_image_prompts(fresh)
    lib = fresh
    affected = mark_asset_dependents(rel)
    _record_history("asset-image", lib[rel].get("name", Path(rel).stem), rel,
                    previous_version, _snapshot(dst, ""), affected)
    return dst.relative_to(ROOT).as_posix()


def _run_image_job(job_id, rel):
    try:
        out = do_regen_image(rel, job_id)
        _set_job(job_id, status="success", finished_at=time.strftime("%H:%M:%S"), output=out)
    except Exception as e:
        _set_job(job_id, status="error", finished_at=time.strftime("%H:%M:%S"), error=str(e)[:600])


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        # ★动态实时（2026-11-20）：确保所有 API/页面响应不被浏览器或中间层缓存，
        #   改完 01_script/04_feed 的稿子后刷新 /board 立刻读到最新数据。
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _safe(self, rel):
        f = (ROOT / rel).resolve()
        try:
            f.relative_to(ROOT.resolve())
            return f
        except ValueError:
            return None

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        q = urllib.parse.parse_qs(u.query)
        if path in ("/studio", "/studio.html"):
            if STUDIO_FILE.is_file():
                return self._send(200, STUDIO_FILE.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return self._send(200, "<h3>director_studio.html 缺失</h3>", "text/html; charset=utf-8")
        if path in ("/", "/index.html", "/board", "/board.html"):
            if UI_FILE.is_file():
                return self._send(200, UI_FILE.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return self._send(200, "<h3>director_ui.html 缺失</h3>", "text/html; charset=utf-8")
        if path == "/api/manifest":
            return self._json(build_manifest())
        if path == "/api/assets":
            return self._json(build_assets())
        if path == "/api/jobs":
            return self._json({"jobs": load_jobs()})
        if path == "/api/history":
            return self._json({"history": [history_row_detail(r) for r in reversed(_history())]})
        if path == "/api/project":
            return self._json(load_json("00_source/PROJECT_INFO.json", {}))
        if path == "/api/overview":
            return self._json(build_overview())
        if path == "/api/production":
            return self._json(build_production())
        if path.startswith("/api/review/"):
            seg = path.removeprefix("/api/review/")
            if not SEGMENT_ID_RE.fullmatch(seg):
                return self._json({"error": "invalid segment id"}, 400)
            review = get_review(seg)
            return self._json(review) if review is not None else self._json({"error": "not found"}, 404)
        if path == "/api/characters": 
            return self._json(build_characters())
        if path == "/api/engines":
            local = h3_status()
            if local["ready"]:
                try:
                    probe, _ = _h3_call(["inspect", "--project", str(ROOT)], timeout=15)
                    local["inspect"] = probe
                except Exception as exc:
                    local["inspect"] = {"error": str(exc)[:200]}
            return self._json({"image": {"ready": bool(image_gen_path()),
                                         "path": str(image_gen_path() or ""),
                                         "default_engine": DEFAULT_IMG_ENGINE},
                               "video": local})
        if path == "/api/chapters":
            return self._json(build_chapters())
        if path == "/api/file":
            rel = (q.get("path") or [""])[0]
            f = self._safe(rel)
            if not f or not f.is_file():
                return self._json({"error": "not found"}, 404)
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = f.read_text(encoding="utf-8", errors="replace")
            return self._json({"path": rel, "content": content,
                               "ext": f.suffix.lower().lstrip(".")})
        if path == "/api/image/prompt":
            rel = (q.get("path") or [""])[0]
            entry = load_image_prompts().get(rel)
            if not entry:
                return self._json({"error": "no prompt config", "regenerable": False}, 404)
            f = ROOT / rel
            bak = f.with_name(f.stem + "_bak" + f.suffix)
            return self._json({"path": rel, "regenerable": True,
                               "has_backup": bak.is_file(),
                               "backup": bak.relative_to(ROOT).as_posix() if bak.is_file() else "",
                               **entry})
        if path.startswith("/api/episode/"):
            ep = path.split("/")[-1]
            txt = read_episode(ep)
            return self._json({"episode": ep, "markdown": txt}) if txt is not None \
                else self._json({"error": "not found"}, 404)
        if path.startswith("/api/continuity/"):
            parts = path.split("/")
            seg = parts[3] if len(parts) == 4 else ""
            if not SEGMENT_ID_RE.fullmatch(seg):
                return self._json({"error": "invalid segment id"}, 400)
            return self._json(continuity_details(seg))
        if path.startswith("/api/segment/"):
            parts = path.split("/")
            seg = parts[3] if len(parts) == 4 else ""
            if not SEGMENT_ID_RE.fullmatch(seg):
                return self._json({"error": "invalid segment id"}, 400)
            d = read_segment(seg)
            return self._json(d) if d is not None else self._json({"error": "not found"}, 404)
        if path.startswith("/file/"):
            return self._serve_file(path[len("/file/"):])
        return self._json({"error": "not found"}, 404)

    def _serve_file(self, rel):
        f = self._safe(rel)
        if not f or not f.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        size = f.stat().st_size
        rng = self.headers.get("Range")
        if rng and f.suffix.lower() in (".mp4", ".webm", ".mov"):
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
                end = min(end, size - 1)
                data = f.read_bytes()[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except Exception:
                    pass
                return
        self._send(200, f.read_bytes(), ctype, {"Accept-Ranges": "bytes"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        n = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            body = {}
        try:
            m = re.match(r"^/api/review/([^/]+)$", path)
            if m:
                seg = m.group(1)
                if not SEGMENT_ID_RE.fullmatch(seg):
                    return self._json({"error": "invalid segment id"}, 400)
                result, code = update_review(seg, body)
                return self._json(result, code)
            m = re.match(r"^/api/continuity/([^/]+)$", path)
            if m:
                seg = m.group(1)
                if not SEGMENT_ID_RE.fullmatch(seg):
                    return self._json({"error": "invalid segment id"}, 400)
                f = ROOT / "04_feed" / "segments" / seg / "prompt.txt"
                if not f.is_file():
                    return self._json({"error": "no prompt"}, 404)
                ledger = body.get("ledger")
                if not isinstance(ledger, dict) or ledger.get("segment") != seg:
                    return self._json({"error": "ledger segment mismatch"}, 400)
                text = f.read_text(encoding="utf-8")
                if body.get("compile") is not True:
                    draft = dict(ledger)
                    draft.pop("prompt_sha256", None)
                    ledger_path = continuity._path(ROOT, seg)
                    before_snap = _snapshot(ledger_path, ".json") if ledger_path.is_file() else ""
                    _atomic_save_json(ledger_path.relative_to(ROOT).as_posix(), draft)
                    _record_history("continuity-draft", seg, ledger_path.relative_to(ROOT).as_posix(),
                                    before_snap, _snapshot(ledger_path, ".json"))
                    return self._json({"ok": True, **continuity_details(seg)})
                if body.get("compile") is True:
                    candidate = dict(ledger)
                    candidate.pop("prompt_sha256", None)
                    previous = continuity_previous(candidate)
                    preflight = continuity.validate_ledger(candidate, text, previous)
                    preflight["reference_errors"] = reference_gate(seg, text, _read_refs(seg))
                    if preflight["reference_errors"]:
                        preflight["status"] = "blocked"
                    allowed_warnings = {"MISSING_PROMPT_HASH", "UNVERIFIED_SPEAKER_BINDING"}
                    if (preflight["status"] == "blocked" or not
                            preflight.get("evidence", {}).get("dialogue_text_verified") or any(
                            warning["code"] not in allowed_warnings for warning in preflight["warnings"])):
                        return self._json({"error": "continuity blocked", "report": preflight}, 400)
                    try:
                        compiled = continuity.compile_prompt(text, candidate)
                        final_candidate = dict(candidate)
                        final_candidate.pop("prompt_sha256", None)
                        final_candidate["prompt_sha256"] = hashlib.sha256(compiled.encode("utf-8")).hexdigest()
                        final_report = continuity.validate_ledger(final_candidate, compiled, previous)
                        final_report["reference_errors"] = reference_gate(seg, compiled, _read_refs(seg))
                        if final_report["reference_errors"]:
                            final_report["status"] = "blocked"
                        if (final_report["status"] != "pass" or
                                final_report.get("evidence", {}).get("speaker_binding_verified") is not True):
                            return self._json({"error": "compiled prompt blocked", "report": final_report}, 400)
                        continuity.save_ledger(ROOT, seg, final_candidate, compiled)
                    except Exception as exc:
                        return self._json({"error": str(exc)[:800]}, 400)
                before_snap = _snapshot(f, ".txt")
                f.write_text(compiled, encoding="utf-8", newline="\n")
                _record_history("continuity-compile", seg, f.relative_to(ROOT).as_posix(),
                                before_snap, _snapshot(f, ".txt"))
                return self._json({"ok": True, **continuity_details(seg)})
            if path == "/api/history/restore":
                row_id = body.get("id", "")
                row = next((item for item in _history() if item.get("id") == row_id), None)
                if not row:
                    return self._json({"error": "history entry not found"}, 404)
                target = self._safe(row.get("path", ""))
                backup = self._safe(row.get("before", ""))
                if not target or not target.is_file():
                    return self._json({"error": "target file not found"}, 404)
                if not backup or not backup.is_file():
                    return self._json({"error": "历史快照已丢失，无法恢复"}, 404)
                is_image = target.suffix.lower() in IMG_EXT
                if is_image:
                    current_snap = _snapshot(target, "")
                    shutil.copy2(backup, target)
                    _record_history("restore", row.get("label", ""), row["path"],
                                    current_snap, _snapshot(target, ""), row.get("affected_segments", []))
                else:
                    restored = backup.read_text(encoding="utf-8")
                    if row.get("path") == IMAGE_PROMPTS_NAME:
                        try:
                            json.loads(restored)
                        except ValueError:
                            return self._json({"error": "历史配置不是有效 JSON"}, 400)
                    current_snap = _snapshot(target, "")
                    target.write_text(restored, encoding="utf-8", newline="\n")
                    _record_history("restore", row.get("label", ""), row["path"],
                                    current_snap, _snapshot(target, ""), row.get("affected_segments", []))
                mark_asset_dependents(row["path"])
                return self._json({"ok": True, "path": row["path"]})
            m = re.match(r"^/api/segment/([^/]+)/save$", path)
            if m:
                if not SEGMENT_ID_RE.fullmatch(m.group(1)):
                    return self._json({"error": "invalid segment id"}, 400)
                f = ROOT / "04_feed" / "segments" / m.group(1) / "prompt.txt"
                if not f.is_file():
                    return self._json({"error": "no prompt"}, 404)
                text = body.get("prompt_txt", "")
                before_snap = _snapshot(f, ".txt")
                f.write_text(text, encoding="utf-8", newline="\n")
                rel = f.relative_to(ROOT).as_posix()
                _record_history("segment-prompt", m.group(1), rel, before_snap, _snapshot(f, ".txt"))
                return self._json({"ok": True, "bytes": len(text)})
            m = re.match(r"^/api/segment/([^/]+)/save_shots$", path)
            if m:
                seg = m.group(1)
                if not SEGMENT_ID_RE.fullmatch(seg):
                    return self._json({"error": "invalid segment id"}, 400)
                f = ROOT / "04_feed" / "segments" / seg / "prompt.txt"
                if not f.is_file():
                    return self._json({"error": "no prompt"}, 404)
                shots = body.get("shots", [])
                if not isinstance(shots, list) or not shots:
                    return self._json({"error": "empty shots"}, 400)
                before = f.read_text(encoding="utf-8")
                if not any(SHOT_RE.match(line.strip()) for line in before.split("\n")):
                    return self._json({"error": "unsupported shot format"}, 400)
                fields = ("time", "shot", "action", "dialogue", "camera", "sound")
                if any(not isinstance(s, dict) or
                       any(not isinstance(s.get(k, ""), str) or "\n" in s.get(k, "") or "\r" in s.get(k, "")
                           for k in fields) or
                       not SHOT_RE.fullmatch(f"[{s.get('time', '')}]") for s in shots):
                    return self._json({"error": "invalid shot fields or timecode"}, 400)
                original = parse_shots(before)
                unchanged = len(original) == len(shots) and all(
                    all(old[k] == new.get(k, "") for k in fields) for old, new in zip(original, shots))
                txt = before if unchanged else rebuild_prompt(before, shots)
                if txt == before:
                    return self._json({"ok": True, "shots": len(shots), "bytes": len(txt), "unchanged": True})
                before_snap = _snapshot(f, ".txt")
                f.write_text(txt, encoding="utf-8", newline="\n")
                _record_history("shots", seg, f.relative_to(ROOT).as_posix(), before_snap, _snapshot(f, ".txt"))
                return self._json({"ok": True, "shots": len(shots), "bytes": len(txt)})
            m = re.match(r"^/api/segment/([^/]+)/status$", path)
            if m:
                seg = m.group(1)
                if not SEGMENT_ID_RE.fullmatch(seg):
                    return self._json({"error": "invalid segment id"}, 400)
                st = load_status()
                merged = dict(st.get(seg) or {})
                incoming = body.get("status", {})
                if not isinstance(incoming, dict):
                    return self._json({"error": "status must be an object"}, 400)
                for key, val in incoming.items():
                    if re.fullmatch(r"\d+", str(key)):
                        merged[str(key)] = val
                st[seg] = merged
                save_status(st)
                return self._json({"ok": True, "status": st[seg]})
            m = re.match(r"^/api/segment/([^/]+)/asset_ack$", path)
            if m:
                seg = m.group(1)
                if not SEGMENT_ID_RE.fullmatch(seg):
                    return self._json({"error": "invalid segment id"}, 400)
                st = load_status()
                entry = st.get(seg)
                if isinstance(entry, dict):
                    entry.pop("asset_update", None)
                    save_status(st)
                return self._json({"ok": True})
            m = re.match(r"^/api/segment/([^/]+)/regen$", path)
            if m:
                if not SEGMENT_ID_RE.fullmatch(m.group(1)):
                    return self._json({"error": "invalid segment id"}, 400)
                return self._json({"ok": True, "job": do_regen(m.group(1))})
            m = re.match(r"^/api/segment/([^/]+)/promote$", path)
            if m:
                if not SEGMENT_ID_RE.fullmatch(m.group(1)):
                    return self._json({"error": "invalid segment id"}, 400)
                return self._json({"ok": True, "clip": do_promote(m.group(1))})
            m = re.match(r"^/api/episode/([^/]+)/assemble$", path)
            if m:
                return self._json({"ok": True, "job": do_assemble(m.group(1))})
            if path == "/api/image/prompt":
                rel = body.get("path", "")
                lib = load_image_prompts()
                if rel not in lib:
                    return self._json({"error": "no prompt config"}, 404)
                before = lib[rel].get("prompt", "")
                cfg_path = ROOT / IMAGE_PROMPTS_NAME
                before_snap = _snapshot(cfg_path, ".json") if cfg_path.is_file() else ""
                lib[rel]["prompt"] = body.get("prompt", "")
                for extra in ("engine", "preset", "size", "seed"):
                    if body.get(extra) not in (None, ""):
                        lib[rel][extra] = body[extra]
                save_image_prompts(lib)
                affected = mark_asset_dependents(rel)
                _record_history("asset-prompt", lib[rel].get("name", Path(rel).stem), IMAGE_PROMPTS_NAME,
                                before_snap, _snapshot(cfg_path, ".json"), affected)
                return self._json({"ok": True, "bytes": len(lib[rel]["prompt"]), "affected_segments": affected})
            if path == "/api/image/regen":
                rel = body.get("path", "")
                if not self._safe(rel):
                    return self._json({"error": "forbidden"}, 403)
                job_id = new_job("image-regen", Path(rel).stem)
                threading.Thread(target=_run_image_job, args=(job_id, rel), daemon=True).start()
                return self._json({"ok": True, "job": job_id})
            if path == "/api/image/rollback":
                rel = body.get("path", "")
                f = self._safe(rel)
                if not f:
                    return self._json({"error": "forbidden"}, 403)
                bak = f.with_name(f.stem + "_bak" + f.suffix)
                if not bak.is_file():
                    return self._json({"error": "没有可回滚的备份"}, 400)
                before_snap = _snapshot(f, "")
                shutil.copy2(bak, f)
                affected = mark_asset_dependents(rel)
                _record_history("asset-image", f.stem, rel, before_snap, _snapshot(f, ""), affected)
                return self._json({"ok": True, "rolled_back_from": bak.name, "affected_segments": affected})
            if path == "/api/image/replace":
                import base64
                rel = body.get("path", "")
                data = body.get("data", "")
                if not data.startswith("data:image/"):
                    return self._json({"error": "bad image data"}, 400)
                f = self._safe(rel)
                if not f or not f.is_file():
                    return self._json({"error": "not found"}, 404)
                before_snap = _snapshot(f, "")
                affected = mark_asset_dependents(rel)
                bak = f.with_name(f.stem + "_bak" + f.suffix)
                if not bak.exists():
                    shutil.copy2(f, bak)
                f.write_bytes(base64.b64decode(data.split(",", 1)[1]))
                _record_history("asset-image", f.stem, rel, before_snap, _snapshot(f, ""), affected)
                return self._json({"ok": True, "affected_segments": affected})
        except Exception as e:
            return self._json({"error": str(e)[:400]}, 400)
        return self._json({"error": "not found"}, 404)


# ---------- 自检 ----------
def self_test():
    """离线自测（不启服务、不写项目文件）：校验解析/回写/推断逻辑。"""
    print("[self-test] director_server 核心函数")
    fails = []

    # 1. 时间码解析
    cases = [("00:00.000", 0.0), ("00:02.500", 2.5), ("01:05.250", 65.25)]
    for tc, want in cases:
        got = parse_tc(tc)
        if abs(got - want) > 1e-6:
            fails.append(f"parse_tc({tc})={got} 期望 {want}")
    print(f"  parse_tc       {'OK' if not fails else 'FAIL'}")

    # 2. 分镜解析 + 回写（重建后镜头行数不变、非镜头段落保留）
    sample = (
        "subject_definitions:\n<Subject X> is someone.\n\n"
        "detailed_description:\n"
        "[00:00.000] a close-up shot frames the scene. He smiles. "
        "<d>[Chinese]「测试台词」</d> Camera: static shot. Sound at this moment: birds.\n"
        "[00:02.500] a wide shot frames the scene. He walks away. Camera: pan left.\n\n"
        "overall_soundscape:\nambient\n\nnon_diegetic_music:\nNone.\n"
    )
    shots = parse_shots(sample)
    ok2 = (len(shots) == 2 and shots[0]["dialogue"] == "「测试台词」"
           and shots[0]["camera"] == "static shot" and shots[0]["sound"] == "birds"
           and shots[1]["camera"] == "pan left")
    rebuilt = rebuild_prompt(sample, shots)
    ok3 = (sum(1 for l in rebuilt.split("\n") if SHOT_RE.match(l.strip())) == 2
           and all(k in rebuilt for k in ("subject_definitions:", "detailed_description:",
                                          "overall_soundscape:", "non_diegetic_music:")))
    if not ok2:
        fails.append("parse_shots 字段解析不正确")
    if not ok3:
        fails.append("rebuild_prompt 结构未保持")
    print(f"  parse_shots    {'OK' if ok2 else 'FAIL'}  (2 镜字段)")
    print(f"  rebuild_prompt {'OK' if ok3 else 'FAIL'}  (镜头行数/段落保留)")

    # 3. 友好名映射（未配置时回落空串，不抛异常）
    try:
        friendly_name("unknown_thing.png")
        print("  friendly_name  OK")
    except Exception as e:
        fails.append(f"friendly_name 异常: {e}")

    if fails:
        print("[self-test] FAILED")
        for f in fails:
            print("  -", f)
        return False
    print("[self-test] PASSED")
    return True


def self_check():
    ok = True
    print(f"[root] {ROOT}")
    if not (ROOT / "project_state.json").is_file():
        print("[warn] 未见 project_state.json（是否已 /建目录 初始化？）")
    eps = scan_episodes()
    print(f"[episodes] {len(eps)} 集: " + ", ".join(f"{k}(S{v[0]:02d}-S{v[1]:02d})"
                                                   for k, v in eps.items()))
    if not eps:
        print("[FAIL] 未找到 01_script/episodes/E*.md")
        ok = False
    segs = list(SEG_EP.keys())
    have = [s for s in segs if (ROOT / "04_feed" / "segments" / s).is_dir()]
    print(f"[segments] {len(have)}/{len(segs)} 个投产包目录存在")
    clips = [s for s in segs if clip_for_seg(s)]
    print(f"[clips]    {len(clips)}/{len(segs)} 段有成片")
    print(f"[assets]   {len(load_image_prompts())} 张图配置了生成提示词")
    print(f"[data]     {DATA_DIR}/ {'OK' if (ROOT / DATA_DIR).is_dir() else '未创建（首次运行时自动建）'}")
    print(f"[ui]       {'OK' if UI_FILE.is_file() else 'MISSING: ' + str(UI_FILE)}")
    print(f"[studio]   {'OK' if STUDIO_FILE.is_file() else 'MISSING: ' + str(STUDIO_FILE)}")
    gen = image_gen_path()
    print(f"[出图]     {'OK · ' + str(gen) if gen else '未找到本机生图器'}")
    local = h3_status()
    print(f"[出片]     {'OK · 本地 H3' if local['ready'] else '未就绪 · ' + local['reason']}")
    if local["ready"]:
        print(f"[h3 py]    {h3_python()}")
    if not UI_FILE.is_file():
        ok = False
    print("[check]", "PASS" if ok else "FAIL")
    return ok


def _resolve_port(port_arg: str, base: int = 8770, cap: int = 100) -> int:
    """把 --port 解析成实际端口：固定号被占用时自动顺延，最多试 cap 个。"""
    import socket
    want = "auto" if str(port_arg).lower() in ("", "auto") else str(port_arg)
    start = base if want == "auto" else int(want)
    for offset in range(cap):
        p = start + offset
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
        except OSError:
            s.close()
            continue
        s.close()
        if offset:
            print(f"[i] 端口 {start} 被占用，顺延到 {p}", flush=True)
        return p
    raise SystemExit(f"[x] 端口 {start}~{start + cap - 1} 全被占用，换个时间段再试")


def _write_runtime_port(port: int) -> Path:
    """把本次实际绑定端口写进 导演台数据/port.json。

    这是端口的唯一真相源：启动器 / 外部脚本要打开浏览器就读这里，
    绝不能自己预探测端口（预探测与服务真实绑定之间存在竞态，会打开别人的台）。
    """
    import json as _json
    payload = {
        "port": port,
        "url": f"http://127.0.0.1:{port}/board",
        "title": TITLE,
        "root": str(ROOT),
        "pid": os.getpid(),
    }
    target = data_dir() / "port.json"
    tmp = target.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def _open_browser(url: str) -> bool:
    """服务真正绑定后才开浏览器，指向实际端口。失败只提示，不影响服务。"""
    import webbrowser
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:  # webbrowser 在部分无头环境会抛异常
        print(f"[!] 自动打开浏览器失败：{exc}", flush=True)
        print(f"[i] 请手动复制地址到浏览器：{url}", flush=True)
        return False
    if not opened:
        print(f"[!] 系统未注册可打开的默认浏览器，请手动复制：{url}", flush=True)
    return bool(opened)


def main():
    global ROOT, TITLE, SEG_EP
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--port", default="auto",
                    help="端口号或 auto（默认）：固定 N 被占用时自动顺延；auto 从 8770 起找第一个空闲")
    ap.add_argument("--title", default="")
    ap.add_argument("--no-browser", action="store_true",
                    help="不自动打开浏览器（脚本/CI 场景用）；地址仍会打印并写入 port.json")
    ap.add_argument("--check", action="store_true", help="环境自检（不启服务）")
    ap.add_argument("--self-test", action="store_true", help="离线核心函数自测")
    a = ap.parse_args()
    ROOT = Path(a.root).resolve()
    TITLE = a.title or ROOT.name
    SEG_EP = build_seg_index()
    data_dir()  # 保证 director_data/ 就位，用户一眼能看到数据落在哪
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if a.check:
        sys.exit(0 if self_check() else 1)
    port = _resolve_port(a.port)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/board"
    pf = _write_runtime_port(port)
    print(f"[+] 导演台已启动 {url}  ({TITLE})", flush=True)
    print(f"[i] 数据根：{ROOT}", flush=True)
    print(f"[i] 实际端口已写入 {pf}（启动器/外部脚本读此文件，勿自行预探测端口）", flush=True)
    print(f"[i] 同端口只认先启动的实例；本台数据只写 {ROOT}，互不串。", flush=True)
    if not a.no_browser:
        _open_browser(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


SEG_EP = {}
if __name__ == "__main__":
    main()
