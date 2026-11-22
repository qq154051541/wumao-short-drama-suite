#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_asset_image_tables.py · 把 bank.json 的 image/portrait 渲染进权威 md 表格区（幂等）"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPT_DIR)
BANK = os.path.join(SCRIPT_DIR, "expression_motion_bank.json")
MD = os.path.join(SKILL, "references", "asset-image-prompt-bank.md")


def esc(s):
    return (s or "").replace("|", "\\|").strip()


def main():
    with open(BANK, encoding="utf-8") as f:
        b = json.load(f)
    img, port = b["image"], b["portrait"]

    out = []
    # 100 条按 10 类分表
    cats = []
    for e in img:
        if not cats or cats[-1][0] != e["cat"]:
            cats.append((e["cat"], []))
        cats[-1][1].append(e)
    out.append("### 2.1 100 条分类速查（%d 类）\n" % len(cats))
    for cname, rows in cats:
        out.append("**%s（%s）**\n" % (cname, "%s~%s" % (rows[0]["no"], rows[-1]["no"])))
        out.append("| ID | 名称 | 成品提示词 |")
        out.append("|---|---|---|")
        for e in rows:
            out.append("| %s | %s | %s |" % (e["id"], esc(e["name"]), esc(e["prompt"])))
        out.append("")

    # 5 条角色范式全文
    out.append("\n### 2.2 五条高密度角色范式 · 全文（P2 出图可直接复制）\n")
    dims = [d["dim"] for d in b["portrait_dims"]]
    out.append("> 十段维度：" + " → ".join(dims) + "\n")
    for e in port:
        out.append("#### %s · %s（%s · %d 字）\n" % (e["id"], esc(e["name"]), e["ratio"], len(e["prompt"])))
        out.append("> " + e["prompt"] + "\n")

    tables = "\n".join(out)
    with open(MD, encoding="utf-8") as f:
        md = f.read()
    BEG, END = "<!-- AUTO:TABLES:BEGIN -->", "<!-- AUTO:TABLES:END -->"
    if BEG not in md or END not in md:
        print("[!] 标记不存在，未改动")
        return 1
    md = re.sub(re.escape(BEG) + r".*?" + re.escape(END),
                BEG + "\n" + tables + "\n" + END, md, flags=re.S)
    with open(MD, "w", encoding="utf-8") as f:
        f.write(md)
    print("[+] 已写入 %d 条生图 + %d 条角色范式到 %s" % (len(img), len(port), MD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
