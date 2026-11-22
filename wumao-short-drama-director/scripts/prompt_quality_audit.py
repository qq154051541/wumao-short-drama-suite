#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt_quality_audit.py · 提示词质量八维诊断器（模型无关 · P19）

依据：从公开成片提示词的写法共性中归纳的八个质量维度。
      本文件与配套规则库只包含方法论与判据，不含任何第三方成稿或来源数据。

定位：**质量层**，与合规层正交 ——
  - `validate_prompt.py`（C1~C41）管「合不合规」（FAIL 必须清零才能交付）；
  - 本器管「够不够好」（只给建议，⛔ 不自动改稿、不判 FAIL、不拦交付）。
  两者互不替代、互不覆盖；本器对**中文七段式投喂稿**与任意中文视频提示词都可用，
  ⛔ 不绑定 MiniMax / Hailuo / H3 模型，不重建 P13 已剥离的 H3 适配器。

八维（D1~D8）与三条「反模式」的实证依据见
`references/prompt-quality-enhancement.md` §二/§三。

CLI：
    python3 scripts/prompt_quality_audit.py feed.md              # 体检一份稿
    python3 scripts/prompt_quality_audit.py feed.md --json       # 机读输出
    python3 scripts/prompt_quality_audit.py --corpus             # 显示八维模型定义
    python3 scripts/prompt_quality_audit.py --self-test          # 自测
"""

import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPT_DIR)

# ---------------------------------------------------------------- 八维定义
# 每维：(编号, 名称, 命中正则, 缺口时的正向改写建议, 权重)
DIMENSIONS = (
    ("D1", "首帧/身份锚定清单",
     r"(保持|保留|不变|一致|同一|沿用|沿用参考|精确|锁定|@CHR|@图片\d|参考图\s*\d|首帧)",
     "首行写「首帧精确沿用参考图N，锁定 <外貌/服装/道具/画风> 至少三项不变」，把要保留的东西逐项列出来，而不是笼统写「保持一致」。",
     2),
    ("D2", "每镜唯一新信息",
     r"(转身|抬头|低头|回头|推开|抬起|放下|滑落|落下|出现|浮现|露出|收紧|松开|停住|定住|接住|递出|抽出|合上|翻开|撞|碎|亮起|熄灭|逼近|后退|跨出|站起|坐下|举起|垂下)",
     "每个时间戳段只写**一个不可逆事件**（谁做了什么、画面因此变成什么）。⛔ 别用「快速展示」「多个特写」「一系列镜头」这类笼统词。",
     2),
    ("D3", "时间码/节拍骨架",
     r"(\[\d+\s*[-–~]\s*\d+\s*秒?\]|\b\d{1,2}\s*[-–~]\s*\d{1,2}s\b|镜头\s*\d+|第\s*[一二三四五六七八九十\d]+\s*(拍|镜|段)|时间轴分镜)",
     "长段按 `[起始秒-结束秒]` 分段，并确认**各段时长累加 = 段总长**；每段写一个事件，镜号连续不跳号。",
     1),
    ("D4", "运镜因观看需要而动",
     r"(镜头|机位|摄影机|推|拉|摇|移|跟|环绕|俯|仰|升|降|焦段|景别)",
     "把运镜写成**因果句**：「镜头随她转身缓缓横移，把门后的来人带进画面」。⛔ 别在句末堆三四个运镜标签。",
     1),
    ("D5", "声音与事件同步",
     r"(音效|声音|配乐|音乐|环境音|脚步|风声|雨声|呼吸|旁白|画外音|静默|无声|BPM|节拍|响起|声[\s]*【)",
     "声音绑到**具体事件**：「图标落地的同时，一声短促下滑音接轻撞击声」，而不是只写「有背景音乐」；静默也要显式写。",
     1),
    ("D6", "物理因果与交互边界",
     r"(受力|惯性|摩擦|反弹|弹起|布料|衣摆|发丝|重量|重心|接触|碰撞|涟漪|晃动|凹陷|飘动|带动|牵动|仅\s*[^，。]{1,12}\s*(可|能)|其余[^，。]{0,10}(不动|保持|固定)|完全不动)",
     "写清**谁碰谁、结果是什么、什么必须保持不动**：「裙摆扫过背景，背景像布帘荡开一道横向涟漪；仅左侧三枚图标可被带动，顶栏与底部完全不动」。用**正向锁定**代替否定式禁令。",
     1),
    ("D7", "跨切继承 / 段缝承接",
     r"(承接|延续|接上|仍是|仍保持|沿用上|同一(动作|视线|光线|道具)|视线方向|动作方向|声桥|光线接续|末帧|首帧接续|段缝)",
     "段缝写明**承接项**（动作方向 / 视线目标 / 一道光 / 一件道具 / 一段声桥 / 一股受力），写「上一镜留下的倾斜图标在下一镜仍保持倾斜」。",
     1),
    ("D8", "收束态与余韵",
     r"(最终|最后|收势|收束|落定|停在|定格|余韵|归于|恢复|重新|回到原位|末尾|收尾|保持住)",
     "末镜写清**最终状态**：「她回到原位双手交叠，桌面完全平静，只有两枚图标仍微微歪着」——给画面一个可停住的落点。",
     1),
)

# 反模式：命中即提示（不扣分、不 FAIL，只作为「写多了」的提醒）
ANTIPATTERNS = (
    ("A1", "否定式禁令堆砌",
     r"(禁[止用写]|不得|不要|别写|严禁|不能出现|避免出现|无\s*[^\s，。]{1,6}(感|效果))",
     "本包粉色大象法则：被禁的词根本身是画面词。改用**正向锁定**（「仅 X 可动 / Y 保持不动 / 画面只出现 Z」）。"),
    ("A2", "笼统的批量展示词",
     r"(快速展示|多个特写|一系列镜头|一组镜头|各种|若干|多个不同|大量)",
     "模型会把「批量」读成糊成一片。改成**枚举式节拍骨架**：逐条编号、每条一个可读的独立状态。"),
    ("A3", "抽象情绪结果词",
     r"(表情平静|神情复杂|神色凝重|面无表情|表情自然|一脸|很生气|非常震惊|感到|心情复杂)",
     "结果词不产生画面。按 `facs-micro-expression.md` 落成具体器官动作（眉/眼/嘴角/呼吸）。"),
)

# 运镜标签堆砌：同一行出现 ≥3 个运镜词
CAM_WORDS = re.compile(r"(推镜|拉镜|摇镜|移镜|跟拍|环绕|俯拍|仰拍|升镜|降镜|变焦|横移|纵深|手持|斯坦尼康|轨道)")

# 七段式自带的【强制禁止项】栏是**本包正式设计**（中文四项极简句，见
# model-adapters.md §5 主格式），不该被 A1「否定式禁令堆砌」误报。
# 反模式扫描时剔除该栏；八维正向扫描仍看全文。
FORBIDDEN_SECTION = re.compile(r"【强制禁止项】[\s\S]*?(?=【|\Z)")


def _without_forbidden_section(text):
    return FORBIDDEN_SECTION.sub("", text)


def audit(text):
    """对一段中文提示词做八维体检，返回结构化结果（⛔ 不修改原文）。"""
    n_chars = len(text)
    scan_text = _without_forbidden_section(text)
    dims = []
    for code, name, pat, advice, weight in DIMENSIONS:
        hits = re.findall(pat, text)
        ok = bool(hits)
        dims.append({
            "code": code, "name": name, "pass": ok,
            "weight": weight, "hit_count": len(hits),
            "advice": "" if ok else advice,
        })
    ants = []
    for code, name, pat, advice in ANTIPATTERNS:
        hits = re.findall(pat, scan_text)
        if hits:
            ants.append({"code": code, "name": name,
                         "hit_count": len(hits), "advice": advice})
    # 运镜标签堆砌（逐行；同样剔除七段式禁用栏）
    dense = [i + 1 for i, line in enumerate(scan_text.splitlines())
             if len(CAM_WORDS.findall(line)) >= 3]
    if dense:
        ants.append({
            "code": "A4", "name": "单行运镜标签堆砌",
            "hit_count": len(dense),
            "advice": "第 %s 行出现 ≥3 个运镜词。改成一句因果式运镜描述，一行一运镜。"
                      % "、".join(map(str, dense[:6])),
        })
    got = sum(d["weight"] for d in dims if d["pass"])
    total = sum(d["weight"] for d in dims)
    return {
        "chars": n_chars,
        "score": got, "max_score": total,
        "coverage": round(100.0 * got / total, 1),
        "dimensions": dims,
        "antipatterns": ants,
        "note": "质量层建议稿 · 不判 FAIL · 不自动改稿 · 不替代 validate_prompt.py 的 C 码合规门禁",
    }


def report(res, as_json=False):
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print("=" * 66)
    print(" 提示词质量八维体检  ·  %d 字  ·  覆盖 %d/%d 分（%.1f%%）"
          % (res["chars"], res["score"], res["max_score"], res["coverage"]))
    print("=" * 66)
    for d in res["dimensions"]:
        mark = "[✓]" if d["pass"] else "[ ]"
        print(" %s %s %-18s %s" % (mark, d["code"], d["name"],
                                   "命中 %d 处" % d["hit_count"] if d["pass"] else "缺"))
        if d["advice"]:
            print("        → %s" % d["advice"])
    if res["antipatterns"]:
        print("-" * 66)
        print(" 反模式提醒（写多了，不是写错了）：")
        for a in res["antipatterns"]:
            print(" · %s %s（命中 %d 处）→ %s" %
                  (a["code"], a["name"], a["hit_count"], a["advice"]))
    else:
        print("-" * 66)
        print(" 反模式：0 命中")
    print("-" * 66)
    print(" ⚠️ %s" % res["note"])
    return 0


def corpus():
    """显示八维模型定义（纯内置，不依赖任何外部数据文件）。"""
    print("=== 提示词质量八维模型（D1~D8）===")
    for code, name, _pat, _advice, weight in DIMENSIONS:
        print("  %s %-18s 权重 %d" % (code, name, weight))
    print("=== 反模式（写多了，不是写错了）===")
    for code, name, _pat, _advice in ANTIPATTERNS:
        print("  %s %s" % (code, name))
    print("  A4 单行运镜标签堆砌")
    print("  ⚠️ 八维是体检维度，不是必填栏位；只给建议、不判 FAIL、不自动改稿。")
    return 0


def self_test():
    # 一份「八维齐全」的中文稿
    good = """【画幅风格】16:9，写实。首帧精确沿用参考图1，锁定女主短发、米白衬衫、深棕挎包三项不变。
【时间轴分镜】[0-4秒]：她推开木门，门轴带动门后风铃晃了一下；镜头随她转身缓缓横移，把门外来人带进画面。
[4-8秒]：她抬起手接住落下的信封，指尖压住纸角；布料袖口因动作牵动，仅信封可被带动，桌面其余物件完全不动。
[8-12秒]：末帧定格在她低头读完信的样子，承接上一镜的视线方向，风铃恢复静止。
【音效】门轴吱呀声与风铃短响同步，信封落地时一声轻响，随后归于静默。
"""
    r = audit(good)
    assert r["score"] == r["max_score"], [(d["code"], d["name"]) for d in r["dimensions"] if not d["pass"]]
    assert not r["antipatterns"], r["antipatterns"]

    # 一份「空泛 + 反模式」的稿
    bad = "一个女孩，表情平静，快速展示多个特写，一系列镜头，禁止不要出现文字，不能出现模糊。"
    rb = audit(bad)
    assert rb["score"] < r["max_score"]
    codes = [a["code"] for a in rb["antipatterns"]]
    assert "A1" in codes and "A2" in codes and "A3" in codes, codes

    # 运镜标签堆砌
    dense = audit("推镜 拉镜 摇镜 跟拍 环绕 俯拍，镜头很多。")
    assert any(a["code"] == "A4" for a in dense["antipatterns"])

    # ★ 栏位感知：七段式自带的【强制禁止项】是正式设计，不得被 A1 误报
    seven_seg = ("【画幅风格】16:9 写实。【场景资产】木桌、信封。\n"
                 "【时间轴分镜】[0-4秒]：她推开木门，风铃晃动。\n"
                 "【强制禁止项】画面：禁字幕、禁水印（含 Logo）；音频：禁背景音乐、禁旁白。\n")
    rs = audit(seven_seg)
    assert "A1" not in [a["code"] for a in rs["antipatterns"]], rs["antipatterns"]
    # 但同一句否定词出现在正文（非禁用栏）仍须报
    body_bad = "画面里禁字幕、禁水印，不要出现文字。"
    assert "A1" in [a["code"] for a in audit(body_bad)["antipatterns"]]

    # 不自动改稿：audit 不返回任何改写后文本
    assert "text" not in r and "rewritten" not in r
    assert len(DIMENSIONS) == 8
    print("[+] prompt_quality_audit self-test PASSED（八维 / 三条反模式 / 运镜堆砌 / 只建议不改稿 / 离线无外部依赖）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="提示词质量八维诊断器（模型无关 · 只建议不改稿）")
    ap.add_argument("file", nargs="?", help="待体检的中文提示词文件；省略则读 stdin")
    ap.add_argument("--json", action="store_true", help="机读 JSON 输出")
    ap.add_argument("--corpus", action="store_true", help="显示八维模型定义")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.corpus:
        return corpus()
    if a.file:
        if not os.path.isfile(a.file):
            print("[!] 文件不存在：%s" % a.file)
            return 1
        text = open(a.file, encoding="utf-8").read()
    else:
        text = sys.stdin.read()
    if not text.strip():
        print("[!] 输入为空")
        return 1
    return report(audit(text), a.json)


if __name__ == "__main__":
    sys.exit(main())
