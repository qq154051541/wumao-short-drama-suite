#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""init_project_tree.py · 按 output-directory-spec.md 建标准目录树（幂等）

用法：
    python init_project_tree.py --root <项目目录>
    python init_project_tree.py --root <项目目录> --check
    python init_project_tree.py --self-test
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

DIRS = [
    "00_source",
    "01_script/development", "01_script/episodes", "01_script/beats", "01_script/dialogue",
    "02_assets/characters", "02_assets/scenes", "02_assets/props", "02_assets/audio",
    "03_storyboard/shots", "03_storyboard/boards",
    "04_feed/segments", "04_feed/compiled",
    "05_qc/machine", "05_qc/quality", "05_qc/consistency",
    "06_delivery/listing", "06_delivery/cover", "06_delivery/subtitles",
    "07_reports", "_tmp",
]

STATE = {
    "schema": "wumao-project-state/1.0",
    "version": "1.0.0",
    "locks": {"asset_mode": "M1"},
    "stage": "P0",
    "workflow": {"checks": "未知", "blocked_by": [], "next_action": "未知"},
    "directories": DIRS,
    "note": "唯一事实源；源文件放 00_source 且不打包；每段投产包在 04_feed/segments/SNN/",
}

README = """# {name}

> 目录由 `init_project_tree.py` 生成，规范见包内 `references/output-directory-spec.md`。
> **唯一事实源**：根目录 `project_state.json`。

| 目录 | 放什么 |
|---|---|
| `00_source/` | 用户自备原文 / 大纲（⛔ 不打包、不上传） |
| `01_script/` | 开发圣经、分集剧本 E01.md、爽点表、台词本 |
| `02_assets/` | 角色 / 场景 / 道具 / 音色档案与图号索引 |
| `03_storyboard/` | 分镜表、故事板图 |
| `04_feed/segments/SNN/` | **每段一个投产包**：prompt.md + refs.json + SNN.srt + audio_note.md |
| `05_qc/` | 机检报告、八维体检、跨集一致性台账 |
| `06_delivery/` | 上架字段、封面、SRT 汇总、12 项自检 |
| `07_reports/` | 看板与 HTML 报告 |
| `导演台/` | 导演台**程序**（技能安装，升级会覆盖，⛔ 不手改） |
| `导演台数据/` | 导演台**数据**：任务 / 镜状态 / 历史快照 / 提交剧本（升级不清空） |
| `_tmp/` | 流水线临时文件，交付前清空 |

## 打开导演台

双击根目录 **`启动导演台.bat`**，浏览器打开 `http://127.0.0.1:8770/board`。

```bash
# 等价命令行
python 导演台/director_server.py --root . --port 8770
# 技能更新后重新同步导演台
python <技能目录>/scripts/install_director_console.py --root .
```
"""


def build(root, name=None, force=False):
    root = os.path.abspath(root)
    made = []
    for d in DIRS:
        p = os.path.join(root, d.replace("/", os.sep))
        if not os.path.isdir(p):
            os.makedirs(p, exist_ok=True)
            made.append(d)
    rp = os.path.join(root, "README.md")
    if force or not os.path.exists(rp):
        with open(rp, "w", encoding="utf-8", newline="\n") as f:
            f.write(README.format(name=name or os.path.basename(root)))
    sp = os.path.join(root, "project_state.json")
    if force or not os.path.exists(sp):
        with open(sp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(STATE, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return made


def check(root):
    missing = [d for d in DIRS if not os.path.isdir(os.path.join(root, d.replace("/", os.sep)))]
    for f in ("README.md", "project_state.json"):
        if not os.path.exists(os.path.join(root, f)):
            missing.append(f)
    return missing


def self_test():
    t = tempfile.mkdtemp(prefix="wb-tree-")
    try:
        a = build(os.path.join(t, "proj"), "试片")
        if not a:
            print("[!] 首次建目录为空"); return False
        b = build(os.path.join(t, "proj"), "试片")
        if b:
            print("[!] 非幂等，重复建目录:", b); return False
        m = check(os.path.join(t, "proj"))
        if m:
            print("[!] 缺:", m); return False
        st = json.load(open(os.path.join(t, "proj", "project_state.json"), encoding="utf-8"))
        if len(st["directories"]) != len(DIRS):
            print("[!] state 目录数不符"); return False
        print("[+] init_project_tree self-test PASSED")
        return True
    finally:
        shutil.rmtree(t, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="按规范初始化短剧项目目录")
    ap.add_argument("--root")
    ap.add_argument("--name")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖 README 和状态文件")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if not a.root:
        print("[!] 需要 --root <项目目录>"); return 2
    if a.check:
        m = check(a.root)
        if m:
            print("[-] 缺目录/文件：" + ", ".join(m)); return 1
        print("[+] OK 目录合规（%d 个目录 + 2 个根文件）" % len(DIRS)); return 0
    made = build(a.root, a.name, a.force)
    print("[+] 项目：%s" % a.root)
    print("[+] 新建 %d 个目录%s" % (len(made), "（其余已存在，未覆盖）" if not made else ""))
    # 导演台随项目落地：每次建目录都把可双击的导演台铺进项目根
    try:
        import install_director_console as console
        info = console.install(os.path.abspath(a.root), quiet=True)
        n = len(info["installed"]) + len(info["updated"])
        print("[+] 导演台：%s（%d 个文件，双击 %s）"
              % ("已同步" if n else "已是最新", n, console.LAUNCHER))
    except Exception as exc:
        print("[!] 导演台未安装：%s（可稍后跑 scripts/install_director_console.py --root .）" % exc)
    print("[+] 校验：%s" % ("OK" if not check(a.root) else "仍有缺失"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
