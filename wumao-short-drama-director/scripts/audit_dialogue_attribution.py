#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台词归属审计（只读）：剧本分镜表 ↔ 提示词逐句比对。

用法：
    python audit_dialogue_attribution.py --root <项目目录>

比对 01_script/episodes/E*.md 的分镜表「角色：「台词」」与 04_feed/segments/*/prompt.txt
的 <d> 块。输出三类问题：
    text_mismatch         确认级：文本/顺序/镜次不一致
    speaker_not_in_shot   风险级：该镜只出现一个 Subject 但说话人是别人（可能画外音）
    unresolved_speaker    风险级：说话人无对应 Subject

解析假阳性已排除：系统音/旁白、同人连续第二句无署名、无署名拟声词。
默认写 <root>/07_reports/台词归属审计.json；--out 可改。不修改任何提示词。
"""
import argparse
import json
import re
from pathlib import Path

NAME_TO_SUBJECT = {
    "夏阳": "X", "李慕荷": "L", "舒雨歆": "Y", "戴薇": "D",
    "方昊": "FH", "武山": "WS", "柳玥": "LY", "一号": "J", "小伙": "J",
}
VOICE_ONLY = ("系统音", "系统", "旁白", "画外音", "画外")  # 后期合成，不进提示词
NON_SUBJECT_SPEAKERS = {"众人", "所有人"}
SECTION = re.compile(r"^##\s+(S\d{2,})\b.*$", re.M)
ROW = re.compile(r"^\|\s*(\d+)\s*\|", re.M)
SPLIT = re.compile(r"[／/]")
NAME_PREFIX = re.compile(r"^\s*([^：:]+?)\s*(?:（[^）]*）|\([^)]*\))?\s*[：:]")
TIME = re.compile(r"^\[(\d{2}):(\d{2})\.(\d{3})\]", re.M)
QUOTED = re.compile(r"「([^「」]*)」")
SUBJ = re.compile(r"<Subject\s+([A-Za-z0-9_-]+)>")
DIALOGUE = re.compile(r"<d(?:\s+[^<>]*?)?>(.*?)</d>", re.DOTALL)


def parse_cell(cell):
    out, current = [], None
    for part in SPLIT.split(cell):
        quotes = QUOTED.findall(part)
        if not quotes:
            continue
        match = NAME_PREFIX.match(part.split("「")[0])
        if match:
            current = match.group(1).strip()
        for quote in quotes:
            out.append({"speaker": current or "", "text": quote.strip()})
    return out


def script_pairs(ep_dir):
    out = {}
    for md in sorted(Path(ep_dir).glob("E*.md")):
        text = Path(md).read_text(encoding="utf-8")
        heads = list(SECTION.finditer(text))
        for i, head in enumerate(heads):
            seg = head.group(1)
            body = text[head.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            rows = []
            for line in body.splitlines():
                match = ROW.match(line.strip())
                if not match:
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 4:
                    continue
                for item in parse_cell(cells[-1]):
                    if not item["speaker"]:
                        continue  # 无署名引号多为拟声
                    rows.append({"shot": int(match.group(1)), **item})
            if rows:
                out.setdefault(seg, []).extend(rows)
    return out


def prompt_shots(seg_dir):
    out = {}
    for d in sorted(Path(seg_dir).iterdir()):
        prompt = d / "prompt.txt"
        if not d.is_dir() or not prompt.is_file():
            continue
        text = prompt.read_text(encoding="utf-8")
        marks = list(TIME.finditer(text))
        shots = []
        for i, mark in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[mark.end():end]
            utes = []
            for block in DIALOGUE.findall(body):
                clean = re.sub(r"^\[Chinese\]", "", block.strip())
                quoted = QUOTED.findall(clean)
                utes.extend(quoted if quoted else [clean.strip()])
            shots.append({"index": i + 1,
                          "subjects": sorted(set(SUBJ.findall(body))),
                          "utterances": [u.strip() for u in utes if u.strip()]})
        out[d.name] = shots
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    script, prompts = script_pairs(root / "01_script" / "episodes"), prompt_shots(root / "04_feed" / "segments")
    totals = {"text_mismatch": 0, "speaker_not_in_shot": 0, "unresolved_speaker": 0}
    rows = []
    for seg in sorted(prompts):
        shots, srows = prompts[seg], script.get(seg, [])
        issues = []
        if srows:
            for idx, shot in enumerate(shots, 1):
                want_all = [r for r in srows if r["shot"] == idx]
                want = [r for r in want_all
                        if not any(k in r["speaker"] for k in VOICE_ONLY)
                        and r["text"] not in ("……", "…", "...")]
                got = shot["utterances"]
                if [w["text"] for w in want] != got:
                    issues.append({"code": "text_mismatch", "shot": idx,
                                   "script": [w["text"] for w in want], "prompt": got})
                    totals["text_mismatch"] += 1
                for item in want_all:
                    if any(k in item["speaker"] for k in VOICE_ONLY):
                        continue
                    sid = NAME_TO_SUBJECT.get(item["speaker"])
                    if sid is None:
                        if shot["subjects"]:
                            issues.append({"code": "unresolved_speaker", "shot": idx,
                                           "speaker": item["speaker"], "subjects": shot["subjects"],
                                           "text": item["text"]})
                            totals["unresolved_speaker"] += 1
                        continue
                    if len(shot["subjects"]) == 1 and shot["subjects"][0] != sid:
                        issues.append({"code": "speaker_not_in_shot", "shot": idx,
                                       "speaker": item["speaker"], "expected": sid,
                                       "only_subject_in_shot": shot["subjects"][0], "text": item["text"]})
                        totals["speaker_not_in_shot"] += 1
        rows.append({"segment": seg, "issues": issues})
    report = {"schema": "wumao-dialogue-attribution/1.0", "project": root.name,
              "read_only": True, "prompt_modified": False,
              "method": "剧本分镜表「角色：「台词」」↔ 提示词 <d> 逐句对齐；"
                        "speaker_not_in_shot 为风险标记（可能画外音/过肩镜），非错配确诊。",
              "totals": totals,
              "segments_with_issues": [r["segment"] for r in rows if r["issues"]], "rows": rows}
    out = Path(args.out) if args.out else root / "07_reports" / "台词归属审计.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False))
    print("报告:", out)


if __name__ == "__main__":
    main()
