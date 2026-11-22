#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""h3_spec.py · 把导演台的单段投喂包转换成 comfyui-h3-local-runner 的 Director spec。

输入（项目内既有文件）：
    04_feed/segments/<SEG>/prompt.txt   Ref2VA 六段式（或 Base 三段式）
    04_feed/segments/<SEG>/refs.json    {"pictures": {"Picture 1": {"file": "...", "role": "..."}}}
输出：
    schema 2 的 director spec（h3_runner.py submit --director-spec 可直接吃）

边界（必须如实遵守）：
    - 只做格式转换，不做创作判断；镜头内容原样搬运，不补写、不改写；
    - 找不到时间码/参考图时直接失败并说明缺什么，不猜默认值蒙过门；
    - H3 单段时长受 4~15 秒限制，超出即报错而不是静默截断。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SECTION_KEYS = (
    "integrated_multimodal_description",
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
    "constraints",
)

TC_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
SHOT_RE = re.compile(r"\[Shot\s+(\d+)\](?:\s+At\s+(\d{2}):(\d{2})(?:\.(\d{3}))?,?)?", re.I)
SHOT_KIND_RE = re.compile(r"^\{(establish|dialogue|reaction|insert|action|mixed)\}\s*", re.I)
SUBJECT_LETTER_RE = re.compile(r"(?m)^<Subject\s+([A-Za-z0-9]+)>\s*(.*)$")
SUBJECT_NUM_RE = re.compile(r"(?m)^<Subject\s+(\d+)>\s*(.*)$")
PICTURE_REF_RE = re.compile(r"<Picture\s+(\d+)>\s*\(([^)]+)\)")
SECONDS_HINT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)\s*秒")
DURATION_HINT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*秒")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_json(path: Path, default=None):
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError):
        return default


def parse_sections(text: str) -> dict:
    """按 `key:` 行切段；只认已知键，其余原样保留在对应段里。"""
    sections = {key: "" for key in SECTION_KEYS}
    current, buf = None, []
    for line in text.splitlines():
        match = re.match(r"^([a-z_]+)\s*:\s*(.*)$", line.strip())
        if match and match.group(1) in SECTION_KEYS:
            if current:
                sections[current] = "\n".join(buf).strip()
            current, buf = match.group(1), ([match.group(2)] if match.group(2).strip() else [])
            continue
        if current:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


def _tc_seconds(m, s, ms) -> float:
    """导演台的时间码是「分:秒.毫秒」（00:03.500 = 3.5 秒），不是时分秒。"""
    return int(m) * 60 + int(s) + (int(ms) / 1000.0 if ms else 0.0)


def parse_shots(detail: str):
    """先认 `[00:00.000]` 时间码行（导演台格式），再认 `[Shot N] At 00:12`（编译格式）。"""
    lines = []
    for raw in detail.splitlines():
        match = TC_RE.match(raw.strip())
        if match:
            body = raw.strip()[match.end():].strip().lstrip(",").strip()
            lines.append((_tc_seconds(match.group(1), match.group(2), match.group(3)), body))
    if lines:
        return [{"start": start, "text": body} for start, body in lines], "timecode"

    marks = list(SHOT_RE.finditer(detail))
    if not marks:
        return [], "none"
    shots = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(detail)
        text = detail[mark.end():end].strip().lstrip(",").strip()
        start = 0.0
        if mark.group(2):
            start = int(mark.group(2)) * 60 + int(mark.group(3)) + (int(mark.group(4) or 0) / 1000.0)
        shots.append({"start": start, "text": text})
    return shots, "shot-marker"


def shot_kind(text: str):
    match = SHOT_KIND_RE.match(text)
    return match.group(1).lower() if match else None


def strip_kind(text: str) -> str:
    return SHOT_KIND_RE.sub("", text, count=1).strip()


def last_shot_length(text: str, default: float = 2.0) -> float:
    hint = SECONDS_HINT_RE.search(text)
    if hint:
        return max(0.4, float(hint.group(2)) - float(hint.group(1)))
    single = DURATION_HINT_RE.search(text)
    if single:
        return max(0.4, float(single.group(1)))
    return default


def ref_role_kind(role: str) -> tuple[str, str]:
    """refs.json 的 role 文本 → (referenceRole, kind)。"""
    raw = (role or "").lower()
    if any(word in raw for word in ("scene", "location", "场景", "环境", "地点")):
        return "location_subject", "scene"
    if any(word in raw for word in ("prop", "道具", "物件")):
        return "prop_subject", "prop"
    return "identity_subject", "person"


def collect_references(seg_dir: Path, root: Path):
    refs = load_json(seg_dir / "refs.json", {}) or {}
    pictures = refs.get("pictures") or {}
    ordered = []
    for slot in sorted(pictures, key=lambda k: int(re.sub(r"\D", "", k) or 0)):
        entry = pictures[slot] if isinstance(pictures[slot], dict) else {}
        rel = entry.get("file", "")
        path = (root / rel).resolve() if rel else None
        ordered.append({
            "slot": slot,
            "file": rel,
            "path": path,
            "role": entry.get("role", ""),
            "note": entry.get("note", ""),
        })
    return ordered


def collect_subjects(sections: dict, references):
    """subject_definitions → 与参考图按顺序一一对应；数量不符直接报错。"""
    text = sections.get("subject_definitions", "")
    definitions = SUBJECT_LETTER_RE.findall(text) or SUBJECT_NUM_RE.findall(text)
    definitions = [(sid, desc.strip()) for sid, desc in definitions if desc.strip()]
    if not definitions:
        # 没有显式 Subject 段时，用参考图角色兜底，但保留可读名称
        definitions = [(str(i + 1), ref["role"] or Path(ref["file"]).stem)
                       for i, ref in enumerate(references)]
    if references and len(definitions) != len(references):
        raise ValueError(
            f"subject_definitions 有 {len(definitions)} 个 Subject，但 refs.json 有 "
            f"{len(references)} 张参考图；H3 要求一一对应，请先对齐再提交")
    return definitions


def build_spec(root: Path, seg: str, fps: int = 24, width: int = 720, height: int = 1280,
               segment_id: int | None = None) -> dict:
    seg_dir = root / "04_feed" / "segments" / seg
    prompt_path = seg_dir / "prompt.txt"
    if not prompt_path.is_file():
        raise ValueError(f"{seg} 没有 prompt.txt：{prompt_path}")
    prompt = read_text(prompt_path)
    sections = parse_sections(prompt)
    detail = sections.get("detailed_description") or sections.get("integrated_multimodal_description")
    if not detail:
        raise ValueError(f"{seg} 的 prompt.txt 既没有 detailed_description 也没有 "
                         f"integrated_multimodal_description")

    shots, source = parse_shots(detail)
    if not shots:
        raise ValueError(f"{seg} 的分镜里找不到 `[00:00.000]` 时间码行或 `[Shot N]` 标记")
    if len(shots) == 1:
        raise ValueError(f"{seg} 只解析到 1 个镜头；H3 Ref2VA 需要逐镜切分，请先在导演台补分镜")

    starts = [item["start"] for item in shots]
    if any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError(f"{seg} 的时间码不是递增的：{starts}")

    total = starts[-1] + last_shot_length(shots[-1]["text"])
    if total < 4 or total > 15:
        raise ValueError(f"{seg} 解析出的段时长 {total:.2f}s 超出 H3 生成单元 4~15 秒范围；"
                         f"请在导演台调整时间码或拆分段落")

    references = collect_references(seg_dir, root)
    if not references:
        raise ValueError(f"{seg} 的 refs.json 没有参考图；H3 Ref2VA 至少要一张人物/场景锚图，"
                         f"请先在导演台接线后再提交")
    definitions = collect_subjects(sections, references)
    missing = [ref["file"] for ref in references if not ref["path"] or not ref["path"].is_file()]
    if missing:
        raise ValueError(f"{seg} 的参考图文件不存在：{', '.join(missing)}")

    subjects, spec_refs, used_names = [], [], set()
    for index, ((sid, desc), ref) in enumerate(zip(definitions, references), 1):
        role, kind = ref_role_kind(ref["role"])
        base = Path(ref["file"]).stem or f"subject{index}"
        name, suffix = base, 2
        while name in used_names:
            name, suffix = f"{base}-{suffix}", suffix + 1
        used_names.add(name)
        subjects.append({
            "images": [],
            "description": desc,
            "shortName": name,
            "kind": kind,
            "referenceRole": role,
            "referenceLabel": f"Subject {index}",
            "retention": "fully_preserved",
            "retentionNote": ref["note"] or "Preserve the defined reference role.",
        })
        spec_refs.append({"shortName": name, "local_path": str(ref["path"]),
                          "role": role, "label": f"Subject {index}"})

    frames_total = int(round(total * fps))
    segments = []
    for index, item in enumerate(shots):
        start_frame = int(round(item["start"] * fps))
        end_second = starts[index + 1] if index + 1 < len(starts) else total
        length = int(round(end_second * fps)) - start_frame
        if length <= 0:
            raise ValueError(f"{seg} 第 {index + 1} 镜时长为 0，检查时间码")
        body = strip_kind(item["text"])
        if not body:
            raise ValueError(f"{seg} 第 {index + 1} 镜没有画面描述")
        segments.append({"id": f"seg{index + 1}", "start": start_frame, "length": length,
                         "prompt": body, "type": "text", "isEndFrame": False,
                         "directorKind": shot_kind(item["text"])})

    global_parts = [part for part in (
        sections.get("subject_definitions", ""),
        sections.get("constraints", ""),
    ) if part.strip()]

    timeline = {
        "mainTrackEnabled": True, "audioTrackEnabled": True, "motionTrackEnabled": True,
        "propHeight": 90, "globalPropHeight": 126, "showFilenames": True, "showPromptZones": True,
        "overrideAudio": False, "inpaint_audio": True,
        "global_prompt": "\n\n".join(global_parts),
        "retake_global_prompt": "",
        "overall_soundscape": sections.get("overall_soundscape", ""),
        "non_diegetic_music": sections.get("non_diegetic_music", ""),
        "prompt_override": "", "prompt_override_on": False, "retakeMode": False,
        "retakeStart": 24, "retakeLength": 48, "retakePrompt": "", "retakeStrength": 1,
        "retakeVideo": None, "normalStartFrame": 0, "normalDurationFrames": frames_total,
        "reference_mode": "REF2VA", "prompt_format": "minimax",
        "analyzeProvider": "ollama", "analyzeBaseUrl": "", "analyzeModel": "",
        "summary": sections.get("summary", ""), "task_type_override": "",
        "subjectSlotCount": len(subjects),
        "subjects": subjects, "segments": segments,
        "motionSegments": [], "audioSegments": [],
    }

    return {
        "schema": 2,
        "segment_id": segment_id if segment_id is not None else int(re.sub(r"\D", "", seg) or 0),
        "title": seg,
        "source_prompt": str(prompt_path),
        "shot_syntax": source,
        "duration_seconds": round(total, 3),
        "references": spec_refs,
        "director_inputs": {
            "start_second": 0, "end_second": round(total, 3),
            "duration_seconds": round(total, 3),
            "start_frame": 0, "end_frame": frames_total, "duration_frames": frames_total,
            "timeline_data": timeline,
            "local_prompts": " | ".join(item["prompt"] for item in segments),
            "segment_lengths": ",".join(str(item["length"]) for item in segments),
            "guide_strength": "",
            "use_custom_audio": True, "use_custom_motion": True, "inpaint_audio": True,
            "frame_rate": fps, "display_mode": "seconds",
            "custom_width": width, "custom_height": height,
            "resize_method": "crop", "divisible_by": 32, "img_compression": 0,
            "override_audio": False, "ref_image_size": "match",
            "shift_video": 12.0, "shift_audio": 3.0,
            "ref_image_notes": " ".join(
                f"@ref{i}= {ref['shortName']}." for i, ref in enumerate(spec_refs, 1)),
            "minimax_settings_ui": "", "timeline_ui": "",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="把单段投喂包转成 H3 Director spec")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--segment", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    args = parser.parse_args()
    try:
        spec = build_spec(args.project.resolve(), args.segment, args.fps, args.width, args.height)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "segment": args.segment, "duration": spec["duration_seconds"],
                      "shots": len(spec["director_inputs"]["timeline_data"]["segments"]),
                      "subjects": len(spec["references"]),
                      "out": str(args.out) if args.out else ""}, ensure_ascii=False))


if __name__ == "__main__":
    main()
