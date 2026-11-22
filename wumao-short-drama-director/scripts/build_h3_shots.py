#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_h3_shots.py — 从「角色登记表 + 镜头表」生成 H3 Ref2VA 六段投喂稿。

为什么要有这一层（2026-11-20 复盘）：
  三段格式（integrated_multimodal_description）把身份、场景、动作、台词全塞进一段，
  `<Picture N>` 只是"被引用的图"，模型并不知道"这张图是谁"。两人同框时身份互相污染，
  同一个人在不同段落之间脸会变。
  官方 Ref2VA 六段用 `subject_definitions` 显式登记 `<Subject N>` 与 `<Picture N>` 的绑定，
  再用 `retention_analysis` 逐条声明 fully_preserved —— 这是这套模型锁身份的唯一正规入口。

输入：
  02_assets/H3_CAST.json   cast / places / props 登记表（含 speaker 编号、board、ref 路径）
  04_feed/<ep>_shots.json  镜头表（camera / casting / action / lines / guard / sound / music）

输出：
  04_feed/segments/<EP>-<ID>/prompt.txt   六段格式投喂稿
  04_feed/segments/<EP>-<ID>/refs.json    <Picture N> 槽位与图片一一对应
  04_feed/<ep>_timeline.json              拼接顺序（含复用的插入镜）

用法：
  python build_h3_shots.py --root <项目> --ep e01 [--dry-run]
"""
import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = ("subject_definitions", "summary", "retention_analysis",
          "detailed_description", "overall_soundscape", "non_diegetic_music")


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def norm_place(p: dict) -> str:
    """场景描述压成一句：the + 名词短语，便于嵌进 'The place is ...' 句。"""
    t = (p.get("text") or "").strip().rstrip(".")
    return t


def build_one(ep: str, shot: dict, cast: dict, places: dict, props: dict):
    pics = []          # [(slot, path_board, path_ref, kind, key)]
    subj_lines = []
    retention = []
    speaker_map = {}

    # ---- 人物 ----
    for cid in shot.get("cast_ids") or []:
        c = cast.get(cid)
        if not c:
            raise KeyError(f"未登记角色 {cid}")
        n = len(pics) + 1
        pics.append((f"Picture {n}", c["board"], c["ref"], "cast", cid))
        subj_lines.append(
            f"<Subject {n}> is {c['name']}, whose face, hair, build and age come from "
            f"<Picture {n}>: {c['face']}; {c['name']} wears {c['wardrobe']}.")
        retention.append(
            f"<Subject {n}> (appears in [Shot 1]): fully_preserved - the same face, hair, "
            f"age and clothes as <Picture {n}>, no restyling, no re-casting.")
        speaker_map[c.get("speaker", "")] = n

    # ---- 场景 ----
    place_key = shot["place"]
    pl = places.get(place_key)
    if not pl:
        raise KeyError(f"未登记场景 {place_key}")
    n = len(pics) + 1
    pics.append((f"Picture {n}", pl["board"], pl["ref"], "place", place_key))
    subj_lines.append(
        f"<Subject {n}> is the location defined by <Picture {n}>: {norm_place(pl)}.")
    retention.append(
        f"<Subject {n}> (appears in [Shot 1]): fully_preserved - the same room, furniture "
        f"layout and light direction as <Picture {n}>.")
    place_sub = f"<Subject {n}>"

    # ---- 道具 ----
    prop_subs = []
    for pid in shot.get("prop_ids") or []:
        pr = props.get(pid)
        if not pr:
            raise KeyError(f"未登记道具 {pid}")
        n = len(pics) + 1
        pics.append((f"Picture {n}", pr["board"], pr["ref"], "prop", pid))
        subj_lines.append(f"<Subject {n}> is the {pr['name']} whose shape and colour come from <Picture {n}>.")
        retention.append(f"<Subject {n}> (appears in [Shot 1]): fully_preserved - same shape, colour and material as <Picture {n}>.")
        prop_subs.append(f"<Subject {n}>")

    cast_subs = [f"<Subject {i + 1}>" for i in range(len(shot.get("cast_ids") or []))]
    who = " and ".join(cast_subs) if cast_subs else "the room"

    # ---- 画外音（说话人不在画面里：不定义 Subject、不喂他的参考图）----
    dl = []
    for sid, text in shot.get("offscreen") or []:
        voice = {"S1": "a woman's voice", "S2": "a man's voice",
                 "S3": "a young woman's voice", "S4": "a neutral electronic voice"}.get(sid, "a voice")
        dl.append(f"{voice} from off-screen, close and natural ({sid}) says, <d>[Chinese] {text}</d>")

    # ---- 台词 ----
    for sid, text in shot.get("lines") or []:
        if sid == "S4":
            dl.append(f"A neutral electronic voice with no emotion (S4) says, <d>[Chinese] {text}</d>")
        elif sid in speaker_map:
            dl.append(f"<Subject {speaker_map[sid]}> ({sid}) says, <d>[Chinese] {text}</d>")
        else:
            raise KeyError(f"{shot['id']} 的说话人 {sid} 不在本镜 cast 里：{shot.get('cast_ids')}")

    sec = shot.get("seconds", 5.17)
    summary = (f"[reference generation] The target video is a {sec:.2f}-second single continuous shot, "
               f"no cuts, of {who} in {place_sub}"
               + (f", with {', '.join(prop_subs)}" if prop_subs else "")
               + f". {shot['casting']}.")

    desc = (f"[Shot 1] {shot['camera']}. The place is {place_sub}. {shot['casting']}. "
            f"{shot['action']}." + (" " + " ".join(dl) if dl else "")
            + (f" {shot['guard']}." if shot.get("guard") else ""))

    body = [
        ("subject_definitions", " ".join(subj_lines)),
        ("summary", summary),
        ("retention_analysis", " ".join(retention)),
        ("detailed_description", desc),
        ("overall_soundscape", shot.get("sound", "")),
        ("non_diegetic_music", shot.get("music", "None.")),
    ]
    text = "\n\n".join(f"{k}: {v.strip()}" for k, v in body if v)
    refs = {"pictures": {}}
    for slot, board, ref, kind, key in pics:
        refs["pictures"][slot] = {"role": f"{kind}:{key}", "file": board, "h3_file": ref}
    return text, refs, [p[0] for p in pics]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--ep", default="e01")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    reg = load_json(root / "02_assets/H3_CAST.json")
    if not reg:
        print("缺 02_assets/H3_CAST.json", file=sys.stderr); sys.exit(2)
    shots = load_json(root / f"04_feed/{a.ep}_shots.json")
    if not shots:
        print(f"缺 04_feed/{a.ep}_shots.json", file=sys.stderr); sys.exit(2)

    ep_tag = a.ep.upper()
    made = []
    for shot in shots:
        seg = f"{ep_tag}-{shot['id']}"
        d = root / "04_feed" / "segments" / seg
        text, refs, slots = build_one(a.ep, shot, reg["cast"], reg["places"], reg.get("props", {}))
        missing = [s for s in refs["pictures"].values()
                   if not (root / s["h3_file"]).is_file()]
        if missing:
            print(f"[缺图] {seg}: {[m['h3_file'] for m in missing]}")
        if a.dry_run:
            print(f"--- {seg}  refs={len(slots)}")
            print(text[:400] + " …")
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "prompt.txt").write_text(text + "\n", encoding="utf-8")
        (d / "refs.json").write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
        made.append(seg)
        print(f"{seg}: {len(slots)} 图, {len(shot.get('lines') or [])} 句台词")
    if made:
        print(f"\n生成 {len(made)} 个镜头包 → 04_feed/segments/")


if __name__ == "__main__":
    main()
