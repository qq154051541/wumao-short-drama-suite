#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_prompt_md.py — 由 prompt.txt 生成 prompt.md（分镜卡 + 投喂原文）。

病根：prompt.txt 是投喂原文（单行字段），prompt.md 是给人看的分镜卡，
过去两份靠手写同步 → 改了一处忘另一处，导演台分镜卡与实拍对不上。

现在只维护 prompt.txt；本脚本按 `[Shot N]` 切分自动生成 markdown，台词列从
`<d>[Chinese]…</d>` 里取。可反复覆盖执行（幂等）。

用法： python sync_prompt_md.py 04_feed/segments/S01 [S02 ...]
       python sync_prompt_md.py --all <项目根>
"""
import argparse
import re
import sys
from pathlib import Path

FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
SHOT_SPLIT = re.compile(r"\[Shot (\d+)\]")
REF_ANCHOR = re.compile(r"\(from \[Shot \d+\]\)")
TC_RE = re.compile(r"At (\d\d:\d\d\.\d{3})")
DIALOG_RE = re.compile(r"<d>\[(?:Chinese|English|Japanese)\](.*?)</d>", re.S)
SIZE_HINT = re.compile(
    r"(?:A |An )?(extreme close-up|close-up|medium close-up|medium shot|medium-wide shot|wide shot|"
    r"full shot|top-down close-up|overhead shot|low-angle shot|high-angle shot|insert shot)[^,.]{0,60}",
    re.I)


def load_fields(txt: str):
    out, cur = {}, None
    for line in txt.splitlines():
        hit = False
        for k in FIELDS:
            if line.startswith(k + ":"):
                cur, out[k] = k, line.split(":", 1)[1].strip()
                hit = True
                break
        if not hit and cur and line.strip():
            out[cur] = (out[cur] + " " + line.strip()).strip()
    return out


def parse_shots(desc: str):
    # 「<Picture 1> (from [Shot 1])」里的 [Shot 1] 是锚点不是镜号，先抹掉再切
    desc = REF_ANCHOR.sub("", desc)
    parts = SHOT_SPLIT.split(desc)
    # parts = [preamble, "1", body1, "2", body2, ...]
    head = parts[0].strip()
    shots = []
    for i in range(1, len(parts) - 1, 2):
        n = int(parts[i])
        body = parts[i + 1].strip()
        tc = TC_RE.search(body)
        start = tc.group(1) if tc else ("00:00.000" if n == 1 else "")
        clean = DIALOG_RE.sub("", body)
        clean = re.sub(r"\s+", " ", clean).strip()
        size = SIZE_HINT.search(clean)
        shots.append({
            "n": n, "start": start, "body": body,
            "size": size.group(0).strip() if size else "",
            "visual": clean[:260],
            "dialogue": " / ".join(m.strip() for m in DIALOG_RE.findall(body)),
        })
    return head, shots


def tc_end(start: str, nxt: str, total: float):
    def sec(t):
        try:
            m, s = t.split(":")
            return int(m) * 60 + float(s)
        except Exception:
            return 0.0
    a = sec(start) if start else 0.0
    b = sec(nxt) if nxt else total
    return f"{a:g}-{b:g}"


def build(seg_dir: Path, total=15.0):
    txt = (seg_dir / "prompt.txt").read_text(encoding="utf-8")
    f = load_fields(txt)
    head, shots = parse_shots(f.get("integrated_multimodal_description", ""))
    seg = seg_dir.name
    ep = seg[:1].replace("S", "E") if seg.startswith("S") else ""
    lines = [f"# {seg} · 第01集 · H3官方格式", "", "## 分镜卡", "",
             "| 镜号 | 时码(秒) | 景别/机位 | 镜头描述 | 动作/画面 | 台词 |",
             "|---|---|---|---|---|---|"]
    for i, s in enumerate(shots):
        nxt = shots[i + 1]["start"] if i + 1 < len(shots) else ""
        span = tc_end(s["start"], nxt, total)
        cells = [f"Shot {s['n']}", span, s["size"] or "—",
                 s["visual"][:120], s["visual"][:200], s["dialogue"] or ""]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    lines += ["", "## 投喂原文", "", "```text"]
    lines += [f"{k}: {f[k]}" for k in FIELDS if f.get(k)]
    lines += ["```", ""]
    (seg_dir / "prompt.md").write_text("\n".join(lines), encoding="utf-8")
    return len(shots)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--all", action="store_true", help="paths 视为项目根，扫 04_feed/segments/*")
    a = ap.parse_args()
    dirs = []
    for p in a.paths:
        root = Path(p)
        if a.all:
            dirs += sorted(d for d in (root / "04_feed" / "segments").iterdir() if d.is_dir())
        elif root.is_dir():
            dirs.append(root)
    for d in dirs:
        if not (d / "prompt.txt").is_file():
            continue
        n = build(d)
        print(f"{d.name}: {n} 镜 -> prompt.md")


if __name__ == "__main__":
    main()
