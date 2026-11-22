#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""absorb_candidate.py · 外部点子的结构化初筛（只产候选，不自动改规则）

用法：
    python absorb_candidate.py --title "分镜只做输出" --source github --license Apache-2.0 \
        --gain "防止下游偷改已定结构" --verify "check_package 断言分镜表无新增字段" --note "..."
    python absorb_candidate.py --list
    python absorb_candidate.py --self-test
"""
import argparse
import datetime
import json
import os
import re
import sys

OK_LICENSE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC-BY-4.0", "self", "自撰"}
WATCH_LICENSE = {"NOASSERTION", "UNKNOWN", "GPL-3.0", "AGPL-3.0", "SSPL", "PROPRIETARY"}
TRACE_RE = re.compile(r"https?://|www\.|@[\w.-]{3,}|公众号|微信号|douyin|抖音|weixin|qq\.com|"
                      r"[\w.-]+@[\w.-]+\.\w+|star\s*[:=]?\s*\d|点赞|粉丝", re.I)
CODE_RE = re.compile(r"```|^\s*(def |class |function |import |from \w+ import )", re.M)

STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "07_reports", "absorption")


def card_path():
    return os.path.join(STORE, "candidates.jsonl")


def judge(title, source, lic, gain, verify, note):
    """返回 (verdict, reasons)。初筛只做机器能判的部分，最终裁决留给人。"""
    bad, warn = [], []
    if not gain or len(gain) < 8:
        bad.append("缺「增量」：说不清比现有做法好在哪")
    if not verify or len(verify) < 8:
        bad.append("缺「可验」：没有可检查的验证方式")
    if not note or len(note) < 20:
        bad.append("摘要过短，无法判断是否为抽象而非摘抄")
    if len(note) > 800:
        warn.append("摘要 >800 字，疑似贴了原文，需人工确认是否已去原文")
    if CODE_RE.search(note):
        warn.append("摘要含代码块，疑似复制实现，需改为方法论描述")
    if TRACE_RE.search(note) or TRACE_RE.search(source):
        bad.append("含来源痕迹（链接/账号/真人/平台数据），对外规则正文不得收录")
    L = (lic or "UNKNOWN").strip()
    if L in WATCH_LICENSE:
        bad.append("来源许可 %s：只允许远距离观察，不落盘具体条目" % L)
    elif L not in OK_LICENSE:
        warn.append("许可 %s 未登记，需人工确认兼容矩阵" % L)
    if any(k in note for k in ("原文", "逐字", "全文如下", "复制如下")):
        warn.append("摘要中出现原文暗示词，人工复核")
    if bad:
        return "REJECT", bad + warn
    if warn:
        return "REVIEW", warn
    return "ACCEPT", ["5 问齐备；待人工裁决归属与冲突后判据化"]


def add(args):
    verdict, reasons = judge(args.title, args.source, args.license, args.gain, args.verify, args.note)
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "title": args.title, "source": args.source, "license": args.license,
        "gain": args.gain, "verify": args.verify, "note": args.note,
        "verdict": verdict, "reasons": reasons, "landed": False,
    }
    os.makedirs(STORE, exist_ok=True)
    with open(card_path(), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("[%s] %s" % (verdict, args.title))
    for r in reasons:
        print("   -", r)
    print("   候选卡：%s" % card_path())
    print("   ⚠ 初筛不修改任何规则；人工裁决后按 skill-evolution-protocol.md 六步闭环落地。")
    return 0


def list_cards():
    p = card_path()
    if not os.path.exists(p):
        print("暂无候选卡"); return 0
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    print("候选 %d 条：" % len(rows))
    for i, r in enumerate(rows[-12:], 1):
        print("  %2d [%s] %-28s %s" % (i, r["verdict"], r["title"][:28], r["ts"][:16]))
    return 0


def self_test():
    ok = True
    v, _ = judge("A", "github", "MIT", "明确减少下游返工", "check_package 断言字段不变", "归纳出一条可检查的流程纪律，不引用任何外部成稿")
    ok &= v == "ACCEPT"
    v, _ = judge("B", "https://x.com/a", "MIT", "减少返工", "包检断言", "带链接的摘要")
    ok &= v == "REJECT"
    v, _ = judge("C", "repo", "NOASSERTION", "减少返工", "包检断言", "一段抽象的方法论描述，长度足够且不贴原文")
    ok &= v == "REJECT"
    v, _ = judge("D", "github", "MIT", "", "包检断言", "一段抽象的方法论描述，长度足够且不贴原文")
    ok &= v == "REJECT"
    print("[+] absorb_candidate self-test %s" % ("PASSED" if ok else "FAILED"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="外部点子结构化初筛")
    ap.add_argument("--title"); ap.add_argument("--source", default="self")
    ap.add_argument("--license", default="self")
    ap.add_argument("--gain", default=""); ap.add_argument("--verify", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if a.list:
        sys.exit(list_cards())
    if not a.title:
        print("[!] 需要 --title"); return 2
    return add(a)


if __name__ == "__main__":
    sys.exit(main())
