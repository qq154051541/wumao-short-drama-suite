#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考图接线修复器：按文件名为唯一事实源重算 <Picture N> 槽号。

用法：
    python fix_reference_wiring.py --root <项目目录>            # dry-run
    python fix_reference_wiring.py --root <项目目录> --apply    # 写盘

规则：
  - <Picture N> 是 refs.json 的上传位序，不是身份；文件名才是身份。
  - 只改槽号、不改文件名；要求「改后引用集合 == refs 槽位集合」才写入。
  - 文件名不在 refs / refs 槽位无人引用 / 同名多槽 → 阻断转人工，禁止猜。
  - 逐段备份 prompt.txt 到 _tmp/reference-fix-backups/<SEG>/，不碰 refs 与台账。
"""
import argparse
import json
import re
import shutil
from pathlib import Path

PIC_REF = re.compile(r"<Picture\s+(\d+)>\s*\(([^)]+)\)")
SEG_RE = re.compile(r"^S\d{2,}$")


def load_refs(seg_dir):
    path = seg_dir / "refs.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    pictures = data.get("pictures")
    if not isinstance(pictures, dict) or not pictures:
        return None
    by_name, duplicate, slots = {}, [], {}
    for slot, entry in pictures.items():
        if not isinstance(entry, dict):
            continue
        name = Path(str(entry.get("file", ""))).name
        if not name:
            continue
        if name in by_name:
            duplicate.append(name)
        by_name[name] = slot
        slots[slot] = name
    return {"slots": slots, "by_name": by_name, "duplicate": duplicate, "raw": data}


def plan_segment(seg_dir, root):
    refs = load_refs(seg_dir)
    prompt_path = seg_dir / "prompt.txt"
    if refs is None or not prompt_path.is_file():
        return None
    text = prompt_path.read_text(encoding="utf-8")
    moves, unresolved = [], []
    for match in PIC_REF.finditer(text):
        slot, name = f"Picture {match.group(1)}", Path(match.group(2)).name
        target = refs["by_name"].get(name)
        if target is None:
            unresolved.append({"slot": slot, "filename": name})
        elif target != slot:
            moves.append({"from": slot, "to": target, "filename": name})

    def rewrite(match):
        name = Path(match.group(2)).name
        target = refs["by_name"].get(name)
        return match.group(0) if target is None else f"<Picture {target.split()[1]}> ({match.group(2)})"

    new_text = PIC_REF.sub(rewrite, text)
    referenced = {f"Picture {n}" for n, _ in PIC_REF.findall(new_text)}
    problems = []
    if unresolved:
        problems.append("存在无法定位的文件名")
    if refs["duplicate"]:
        problems.append("refs 存在同名文件，槽位不唯一")
    if referenced != set(refs["slots"]):
        problems.append(f"改后引用集合 {sorted(referenced)} != refs {sorted(refs['slots'])}")
    for match in PIC_REF.finditer(new_text):
        slot, name = f"Picture {match.group(1)}", Path(match.group(2)).name
        if refs["slots"].get(slot) != name:
            problems.append(f"{slot} 文件名仍不符: {name}")
    for slot, entry in refs["raw"]["pictures"].items():
        rel = str(entry.get("file", "")) if isinstance(entry, dict) else ""
        if not rel or not (root / rel).is_file():
            problems.append(f"{slot} 文件不存在: {rel}")
    return {"segment": seg_dir.name, "changed": new_text != text, "moves": moves,
            "unresolved": unresolved, "problems": sorted(set(problems)),
            "rewritten": new_text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=None, help="报告路径；默认 <root>/07_reports/参考图接线修复结果.json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    backups = root / "_tmp" / "reference-fix-backups"
    rows, applied = [], []
    for d in sorted((root / "04_feed" / "segments").iterdir()):
        if not d.is_dir() or not SEG_RE.fullmatch(d.name):
            continue
        plan = plan_segment(d, root)
        if plan is None or (not plan["changed"] and not plan["unresolved"]):
            continue
        ok = not plan["problems"]
        rows.append({"segment": plan["segment"], "moves": plan["moves"],
                     "unresolved": plan["unresolved"], "problems": plan["problems"], "applicable": ok})
        if ok and args.apply:
            backup = backups / plan["segment"]
            backup.mkdir(parents=True, exist_ok=True)
            if not (backup / "prompt.txt").is_file():
                shutil.copy2(d / "prompt.txt", backup / "prompt.txt")
            (d / "prompt.txt").write_text(plan["rewritten"], encoding="utf-8", newline="\n")
            applied.append(plan["segment"])
    report = {"schema": "wumao-reference-fix-result/1.0", "project": root.name,
              "mode": "apply" if args.apply else "dry-run",
              "segments_changed": sum(1 for r in rows if r["applicable"]),
              "segments_blocked": sum(1 for r in rows if not r["applicable"]),
              "applied": applied, "rows": rows}
    out = Path(args.out) if args.out else root / "07_reports" / "参考图接线修复结果.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mode={'apply' if args.apply else 'dry-run'} 可修={report['segments_changed']} "
          f"阻断={report['segments_blocked']} 实写={len(applied)}")
    print("报告:", out)


if __name__ == "__main__":
    main()
