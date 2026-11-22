#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向投产提示词注入「背景禁灰棚」硬约束（幂等，默认 dry-run）。

用法：
    python harden_background.py --root <项目目录>            # 演练
    python harden_background.py --root <项目目录> --apply    # 写盘

只改 detailed_description 段，逐段备份到 _tmp/background-hardening-backups/<SEG>/。
⚠️ 注入会让已有台账的 prompt_sha256 全部失效，必须按 director-console.md §四·补 3.4
的重绑流程重新编译；不得手改哈希。
"""
import argparse
import json
import shutil
from pathlib import Path

SENTENCE = (
    "The background must always be the physical location described for this segment: "
    "keep its architecture, fixed props, ground material and light direction visible "
    "behind the subject in every shot. Never place the subject against a seamless studio "
    "backdrop, a plain grey wall, a neutral cyclorama or any flat empty background."
)
MARKER = "Never place the subject against a seamless studio backdrop"


def patch(text):
    if MARKER in text:
        return text, "already"
    head = "detailed_description:\n"
    if head not in text:
        return text, "no_anchor"
    before, after = text.split(head, 1)
    return before + head + SENTENCE + "\n" + after, "injected"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=None, help="报告路径；默认 <root>/07_reports/背景硬约束结果.json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    backups = root / "_tmp" / "background-hardening-backups"
    rows, written = [], []
    for d in sorted((root / "04_feed" / "segments").iterdir()):
        prompt = d / "prompt.txt"
        if not d.is_dir() or not prompt.is_file():
            continue
        original = prompt.read_text(encoding="utf-8")
        updated, action = patch(original)
        row = {"segment": d.name, "action": action}
        rows.append(row)
        if action == "injected" and args.apply:
            backup = backups / d.name
            backup.mkdir(parents=True, exist_ok=True)
            if not (backup / "prompt.txt").is_file():
                shutil.copy2(prompt, backup / "prompt.txt")
            prompt.write_text(updated, encoding="utf-8", newline="\n")
            written.append(d.name)
    report = {"schema": "wumao-background-hardening/1.0", "mode": "apply" if args.apply else "dry-run",
              "sentence": SENTENCE,
              "injected": sum(1 for r in rows if r["action"] == "injected"),
              "already": sum(1 for r in rows if r["action"] == "already"),
              "no_anchor": sum(1 for r in rows if r["action"] == "no_anchor"),
              "written": written, "rows": rows}
    out = Path(args.out) if args.out else root / "07_reports" / "背景硬约束结果.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "written", "sentence")},
                     ensure_ascii=False))
    print("报告:", out)


if __name__ == "__main__":
    main()
