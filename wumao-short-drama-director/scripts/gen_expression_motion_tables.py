#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_expression_motion_tables.py · 把 expression_motion_bank.json 的 429 条渲染进权威 md 的 AUTO:TABLES 标记"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPT_DIR)
BANK = os.path.join(SKILL, "scripts", "expression_motion_bank.json")
MD = os.path.join(SKILL, "references", "expression-motion-prompt-bank.md")


def esc(s):
    return (s or "").replace("|", "\\|").strip()


def main():
    with open(BANK, encoding="utf-8") as f:
        b = json.load(f)

    out = []
    out.append("### 表 E · 微表情 50 组（公式① 五件套 · 情绪场景型）\n")
    out.append("| ID | 名称 | 微表情 | 眼神落点 | 嘴角变化 | 呼吸停顿 | 小动作 | 适用场景 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for e in b["micro"]:
        s = e.get("slots") or {}
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            e["id"], esc(e["name"]), esc(s.get("face")), esc(s.get("gaze")),
            esc(s.get("mouth")), esc(s.get("breath")), esc(s.get("small")), esc(e["use"])))

    out.append("\n### 表 F · 漫剧五官分镜表情 54 组（公式② 六段式 · 6 卷 × 9 条）\n")
    out.append("| ID | 卷 | 名称 | 成品短语（眉→眼→瞳→鼻→唇→脸颊） |")
    out.append("|---|---|---|---|")
    for e in b["facial"]:
        out.append("| %s | %s | %s | %s |" % (
            e["id"], esc(e["vol"]), esc(e["name"]), esc(e["prompt"])))

    out.append("\n### 表 A · 日常动作提示词 100 条（10 类 · 可直接整句使用）\n")
    out.append("| ID | 类别 | 动作名 | 成品短语 |")
    out.append("|---|---|---|---|")
    for e in b["action"]:
        out.append("| %s | %s | %s | %s |" % (
            e["id"], esc(e["cat"]), esc(e["name"]), esc(e["prompt"])))

    out.append("\n### 表 P · 动作灵感 100 条（10 册 · 站姿／移动／情绪／双人／战斗／职业／钩子／镜头）\n")
    out.append("| ID | 册 | 名称 | 用途 | 镜头 | 动作重点 |")
    out.append("|---|---|---|---|---|---|")
    for e in b["pose"]:
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            e["id"], esc(e["book"]), esc(e["name"]), esc(e["use"]),
            esc(e["cam"]), esc(e["prompt"])))

    tables = "\n".join(out)
    with open(MD, encoding="utf-8") as f:
        md = f.read()
    BEG, END = "<!-- AUTO:TABLES:BEGIN -->", "<!-- AUTO:TABLES:END -->"
    if BEG not in md or END not in md:
        print("[!] 标记不存在，未改动")
        return 1
    md = re.sub(re.escape(BEG) + r".*?" + re.escape(END), BEG + "\n" + tables + "\n" + END,
                md, flags=re.S)
    with open(MD, "w", encoding="utf-8") as f:
        f.write(md)
    print("[+] 已写入 %d 条到 %s" % (
        len(b["micro"]) + len(b["facial"]) + len(b["action"]) + len(b["pose"]), MD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
