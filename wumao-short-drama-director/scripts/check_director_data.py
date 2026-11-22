#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_director_data.py — 导演台数据落盘自检（交付前门禁 · 2026-11-20）

背景（四轮连续踩坑后固化）：
  同一份内容在交付 md 里写得很全，但导演台每个视图读**各自独立**的数据源，
  互不通用；M1 形态（图未生成）下自动发现大面积失效，必须显式登记。
  结果：「/board 没数据」「资产页空」「人物角色页空」「shot_count=0」轮番出现。

  本脚本把 `references/output-directory-spec.md` 的「导演台数据落盘避错清单」
  变成机器可判定的门禁：**交付前跑一次，FAIL 清零再交付**。

用法：
  python scripts/check_director_data.py --root <项目目录> [--json]

检查项（与避错清单①四视图一一对应）：
  D1  剧本：01_script/episodes/E0N.md 存在且首行 `# E0N · 标题`
  D2  段投产包：每个 E0N 对应 NN=(集序-1)*6+1..集序*6 的 SNN/ 含 prompt.txt + prompt.md + refs.json
  D3  资产页：02_assets/IMAGE_PROMPTS.json 存在且条目 key 为规范相对路径、prompt 非空
  D4  人物页：02_assets/CHARACTERS.json 存在，characters 非空、relations 的 from/to 均为已登记 id
  D5  分镜卡时码列：SNN/prompt.md 表格时码列为纯数字范围（非 00:05.000），否则 shot_count=0
  D6  H3 官方对白：若段 prompt.txt 含中文台词，须用 <d>[Chinese]...</d> + (Sx) 说话人 ID
  D7  动态实时：director_server.py 发 no-store 头、director_ui.html 前端带 no-store + 时间戳
  D8  改图复核：02_assets/ASSET_LINKS.json 存在（缺失仅 WARN，不阻断）

退出码：0 = 全 PASS（允许 WARN）· 1 = 有 FAIL · 2 = 用法/读取错误
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FAIL = "FAIL"
WARN = "WARN"
PASS = "PASS"

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
ASSET_PREFIXES = ("02_assets/characters/", "02_assets/scenes/", "02_assets/props/", "02_assets/audio/")
TIMECCODE_RANGE = re.compile(r"^\s*\d+(?:\.\d+)?\s*[-~～—]\s*\d+(?:\.\d+)?\s*$")
MD_DIALOGUE = re.compile(r"[「」]")


def check(root: Path):
    results = []

    def add(code, status, msg):
        results.append({"code": code, "status": status, "msg": msg})

    # ---- D1 剧本 E0N.md ----
    ep_dir = root / "01_script" / "episodes"
    eps = sorted(ep_dir.glob("E*.md")) if ep_dir.is_dir() else []
    if not eps:
        add("D1", FAIL, "01_script/episodes/ 无 E0N.md → /api/manifest episodes=0、/board 剧本树空")
    else:
        bad = []
        for f in eps:
            first = f.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            if not first or not re.match(r"^#\s*E\d+", first[0].strip()):
                bad.append(f.name)
        if bad:
            add("D1", FAIL, f"首行缺 `# E0N · 标题`：{', '.join(bad)}（episode_title 读不到）")
        else:
            add("D1", PASS, f"{len(eps)} 集剧本首行合规：{', '.join(f.stem for f in eps[:6])}")

    # ---- D2 段投产包 SNN/ ----
    seg_expected = []
    for f in eps:
        m = re.match(r"E(\d+)", f.stem)
        if m:
            idx = int(m.group(1))
            seg_expected += [f"S{n:02d}" for n in range((idx - 1) * 6 + 1, idx * 6 + 1)]
    seg_dir = root / "04_feed" / "segments"
    if not seg_expected:
        add("D2", WARN, "无集剧本，无法推算应有哪些段投产包（先修 D1）")
    else:
        missing_seg, missing_file = [], []
        for s in seg_expected:
            d = seg_dir / s
            if not d.is_dir():
                missing_seg.append(s)
                continue
            for fn in ("prompt.txt", "prompt.md", "refs.json"):
                if not (d / fn).is_file():
                    missing_file.append(f"{s}/{fn}")
        if missing_seg:
            add("D2", FAIL, f"缺段目录：{', '.join(missing_seg)} → /api/production 段数不足")
        if missing_file:
            add("D2", FAIL, f"段目录内缺文件：{', '.join(missing_file)} → 段详情/参考图不全")
        if not missing_seg and not missing_file:
            add("D2", PASS, f"{len(seg_expected)} 个段投产包齐备：{', '.join(seg_expected[:6])}")

    # ---- D3 资产页 IMAGE_PROMPTS.json ----
    ip_path = root / "02_assets" / "IMAGE_PROMPTS.json"
    ip = {}
    if not ip_path.is_file():
        add("D3", FAIL, "缺 02_assets/IMAGE_PROMPTS.json → 资产页三分类全空")
    else:
        try:
            ip = json.loads(ip_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            add("D3", FAIL, f"IMAGE_PROMPTS.json 解析失败：{e}")
            ip = {}
        if isinstance(ip, dict) and ip:
            bad_key = [k for k in ip if not k.startswith(ASSET_PREFIXES)]
            empty_prompt = [k for k, v in ip.items() if isinstance(v, dict) and not (v.get("prompt") or "").strip()]
            if bad_key:
                add("D3", FAIL, f"key 非规范资产路径（资产页分组靠前缀判定）：{', '.join(bad_key[:3])}")
            if empty_prompt:
                add("D3", FAIL, f"提示词为空：{', '.join(empty_prompt[:3])}")
            if not bad_key and not empty_prompt:
                kinds = {}
                for v in ip.values():
                    k = (v.get("kind") or "?") if isinstance(v, dict) else "?"
                    kinds[k] = kinds.get(k, 0) + 1
                add("D3", PASS, f"{len(ip)} 张资产卡，分布 {kinds}")
        elif isinstance(ip, dict):
            add("D3", FAIL, "IMAGE_PROMPTS.json 为空对象 → 资产页仍空")

    # ---- D4 人物页 CHARACTERS.json ----
    ch_path = root / "02_assets" / "CHARACTERS.json"
    if not ch_path.is_file():
        add("D4", FAIL, "缺 02_assets/CHARACTERS.json → 人物角色页空（registered:false）；注意资产页读的是 IMAGE_PROMPTS.json，二者不通用")
    else:
        try:
            ch = json.loads(ch_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            add("D4", FAIL, f"CHARACTERS.json 解析失败：{e}")
            ch = {}
        chars = ch.get("characters") if isinstance(ch, dict) else []
        rels = ch.get("relations") if isinstance(ch, dict) else []
        if not chars:
            add("D4", FAIL, "CHARACTERS.json.characters 为空 → 人物角色页 registered:false")
        else:
            ids = {c.get("id") for c in chars if isinstance(c, dict) and c.get("id")}
            nodef = [c.get("name") or c.get("id") for c in chars
                     if isinstance(c, dict) and not all(c.get(k) for k in ("name", "rank", "personality", "appearance", "outfit", "voice"))]
            bad_rel = [r for r in rels if isinstance(r, dict) and (r.get("from") not in ids or r.get("to") not in ids)]
            no_anchor = [c.get("name") for c in chars if isinstance(c, dict) and not (c.get("anchors") or {})]
            if nodef:
                add("D4", WARN, f"人物卡字段不全（前端显示待补）：{', '.join(str(x) for x in nodef[:3])}")
            if no_anchor:
                add("D4", WARN, f"人物无 anchors（卡片上无法点开提示词）：{', '.join(str(x) for x in no_anchor[:3])}")
            if bad_rel:
                add("D4", FAIL, f"{len(bad_rel)} 条关系 from/to 指向未登记 id（会被丢弃）")
            if not bad_rel:
                add("D4", PASS, f"{len(chars)} 人物 + {len(rels)} 关系齐备，registered=True")

    # ---- D5 分镜卡时码列 ----
    bad_tc = []
    checked_seg = 0
    for s in seg_expected:
        pm = seg_dir / s / "prompt.md"
        if not pm.is_file():
            continue
        checked_seg += 1
        for line in pm.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0] in ("镜号", "Shot", "") or set("".join(cells)) <= set("-: "):
                continue
            # 第2列是时码；纯数字范围才被 parse_shots_table 解析
            if not TIMECCODE_RANGE.match(cells[1]):
                bad_tc.append(f"{s}:{cells[1]}")
                break
    if bad_tc:
        add("D5", FAIL, f"分镜卡时码列非纯数字范围（会 shot_count=0）：{'; '.join(bad_tc[:4])}。改成 `0-5`，官方切点 At MM:SS.mmm 写进镜头描述列")
    elif checked_seg:
        add("D5", PASS, f"{checked_seg} 个 prompt.md 分镜卡时码列合规（纯数字范围）")

    # ---- D6 H3 官方对白格式 ----
    h3_bad = []
    for s in seg_expected:
        pt = seg_dir / s / "prompt.txt"
        if not pt.is_file():
            continue
        text = pt.read_text(encoding="utf-8", errors="ignore")
        # 官方三段字段：有 integrated_multimodal_description 即视作 H3 稿
        if "integrated_multimodal_description" not in text:
            continue
        if MD_DIALOGUE.search(text) and "<d>[" not in text:
            h3_bad.append(f"{s}: 裸「」台词无 <d> 包裹")
        if "<d>[" in text and not re.search(r"\(S\d+(?:,S\d+)*\)", text):
            h3_bad.append(f"{s}: 有 <d> 台词但无 (Sx) 说话人 ID")
    if h3_bad:
        add("D6", FAIL, f"H3 对白非官方格式：{'; '.join(h3_bad)}。用 `(Sx)` + `<d>[Chinese] 逐字原文</d>`")
    else:
        add("D6", PASS, "H3 稿对白格式合规或本集无 H3 稿")

    # ---- D7 动态实时 ----
    ds = root / "导演台" / "director_server.py"
    dui = root / "导演台" / "director_ui.html"
    miss = []
    if ds.is_file():
        t = ds.read_text(encoding="utf-8", errors="ignore")
        if "no-store" not in t:
            miss.append("director_server.py 未发 no-store 头")
    else:
        miss.append("缺 导演台/director_server.py")
    if dui.is_file():
        t = dui.read_text(encoding="utf-8", errors="ignore")
        if "no-store" not in t or "Date.now()" not in t:
            miss.append("director_ui.html 的 api() 未带 no-store / 时间戳")
    else:
        miss.append("缺 导演台/director_ui.html")
    if miss:
        add("D7", FAIL, f"动态实时缺失：{'; '.join(miss)} → 改稿后 /board 可能读到旧数据")
    else:
        add("D7", PASS, "后端 no-store + 前端 no-store/时间戳齐备，改稿刷新即见")

    # ---- D8 ASSET_LINKS.json（WARN 级） ----
    if not (root / "02_assets" / "ASSET_LINKS.json").is_file():
        add("D8", WARN, "缺 02_assets/ASSET_LINKS.json → 改图后不会标「需复核」段（仅显示出场段）")
    else:
        add("D8", PASS, "ASSET_LINKS.json 在位")

    return results


def main():
    ap = argparse.ArgumentParser(description="导演台数据落盘自检（交付前门禁）")
    ap.add_argument("--root", required=True, help="项目根目录")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"[x] 根目录不存在：{root}")
        return 2
    res = check(root)
    n_fail = sum(1 for r in res if r["status"] == FAIL)
    n_warn = sum(1 for r in res if r["status"] == WARN)
    if a.json:
        print(json.dumps({"root": str(root), "results": res, "fail": n_fail, "warn": n_warn}, ensure_ascii=False, indent=2))
    else:
        print(f"=== 导演台数据落盘自检 · {root.name} ===")
        for r in res:
            mark = {PASS: "[+]", WARN: "[!]", FAIL: "[x]"}[r["status"]]
            print(f"{mark} {r['code']} {r['msg']}")
        print(f"\n{'[+] 四视图数据齐备，可交付' if n_fail == 0 else '[x] FAIL 未清零，导演台视图会空，禁止交付'}"
              f"（FAIL {n_fail} · WARN {n_warn}）")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
