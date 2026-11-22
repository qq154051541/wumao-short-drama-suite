#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_asset_board.py · 导演台看板（按资产分类展示 · 单文件 HTML · 无外部依赖）

用法：
    python build_asset_board.py --root <项目目录> --out 07_reports/board.html
    python build_asset_board.py --self-test
"""
import argparse
import datetime
import html
import json
import os
import shutil
import sys
import tempfile

GROUPS = [
    ("source", "00_source", "来源", "◆"),
    ("script", "01_script", "剧本", "✎"),
    ("characters", "02_assets/characters", "角色", "◉"),
    ("scenes", "02_assets/scenes", "场景", "▦"),
    ("props", "02_assets/props", "道具", "◈"),
    ("audio", "02_assets/audio", "音色/音轨", "♪"),
    ("storyboard", "03_storyboard", "分镜", "▤"),
    ("feed", "04_feed", "投喂包", "▶"),
    ("qc", "05_qc", "质检", "✓"),
    ("delivery", "06_delivery", "交付", "⬆"),
    ("reports", "07_reports", "报告", "▧"),
]
SKIP_DIRS = {"_tmp", ".git", "__pycache__", "node_modules"}
SKIP_FILES = {"board.html", "project_state.json", "README.md", ".DS_Store", "Thumbs.db"}

CSS = """
:root{--bg:#080c17;--panel:#101728;--panel2:#151f36;--line:#22304d;--txt:#e8f0ff;--dim:#8ea3c7;
--cy:#22d3ee;--pu:#8b5cf6;--pk:#f472b6;--gr:#34d399}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
a{color:var(--cy);text-decoration:none}
.wrap{display:flex;min-height:100vh}
.side{width:238px;flex:none;background:linear-gradient(180deg,#0d1424,#0a1020);border-right:1px solid var(--line);
padding:22px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{font-size:17px;font-weight:700;letter-spacing:.5px;margin:0 0 4px;
background:linear-gradient(90deg,var(--cy),var(--pu));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--dim);font-size:11px;margin-bottom:20px}
.nav a{display:flex;align-items:center;gap:9px;padding:8px 11px;border-radius:9px;color:var(--dim);
cursor:pointer;font-size:13px;margin-bottom:2px;border:1px solid transparent}
.nav a:hover{background:var(--panel2);color:var(--txt)}
.nav a.on{background:linear-gradient(90deg,rgba(34,211,238,.14),rgba(139,92,246,.10));
border-color:rgba(34,211,238,.35);color:var(--txt)}
.nav .ico{width:17px;text-align:center;color:var(--cy)}
.nav .n{margin-left:auto;font-size:11px;color:var(--dim);background:#1b2640;padding:1px 7px;border-radius:9px}
.main{flex:1;padding:26px 30px;min-width:0}
h1{font-size:22px;margin:0 0 4px}
.meta{color:var(--dim);font-size:12px;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:12px;margin-bottom:22px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:14px 16px;
box-shadow:0 0 0 1px rgba(34,211,238,.04),0 8px 24px rgba(0,0,0,.28)}
.stat b{display:block;font-size:24px;background:linear-gradient(90deg,var(--cy),var(--pu));
-webkit-background-clip:text;background-clip:text;color:transparent}
.stat span{color:var(--dim);font-size:11px}
.tools{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap}
#q{flex:1;min-width:220px;background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:10px 14px;color:var(--txt);outline:none;font-size:13px}
#q:focus{border-color:var(--cy);box-shadow:0 0 0 3px rgba(34,211,238,.12)}
.hint{color:var(--dim);font-size:11px;align-self:center}
h2.sec{font-size:15px;margin:26px 0 12px;padding-left:10px;border-left:3px solid var(--cy)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px;
transition:.18s;min-width:0}
.card:hover{border-color:var(--cy);transform:translateY(-2px);box-shadow:0 8px 24px rgba(34,211,238,.10)}
.card .fn{font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .path{color:var(--dim);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:5px 0 9px}
.tag{display:inline-block;font-size:10px;padding:2px 8px;border-radius:7px;margin-right:5px;
background:rgba(139,92,246,.16);color:#c4b5fd;border:1px solid rgba(139,92,246,.3)}
.tag.t2{background:rgba(34,211,238,.12);color:var(--cy);border-color:rgba(34,211,238,.28)}
.card .ft{color:var(--dim);font-size:10px;margin-top:9px;border-top:1px solid var(--line);padding-top:8px}
.empty{color:var(--dim);background:var(--panel);border:1px dashed var(--line);border-radius:12px;padding:16px}
.hide{display:none!important}
footer{color:var(--dim);font-size:11px;margin-top:34px;border-top:1px solid var(--line);padding-top:14px}
"""

JS = """
function show(g){
  document.querySelectorAll('.nav a').forEach(function(a){a.classList.toggle('on',a.dataset.g===g)});
  document.querySelectorAll('.sec').forEach(function(s){s.classList.toggle('hide',g!=='all'&&s.dataset.g!==g)});
  document.querySelectorAll('.grid').forEach(function(x){x.classList.toggle('hide',g!=='all'&&x.dataset.g!==g)});
  filter();
}
function filter(){
  var q=document.getElementById('q').value.toLowerCase(),n=0;
  document.querySelectorAll('.card').forEach(function(c){
    var sec=c.closest('.sec'), grid=c.closest('.grid');
    var vis=c.innerText.toLowerCase().indexOf(q)>=0;
    c.classList.toggle('hide',!vis||(sec&&sec.classList.contains('hide'))||(grid&&grid.classList.contains('hide')));
    if(vis)n++;
  });
  document.getElementById('hit').textContent=document.getElementById('q').value?('命中 '+n+' 项'):'';
}
document.addEventListener('keydown',function(e){
  if((e.ctrlKey||e.metaKey)&&e.key==='f'){e.preventDefault();document.getElementById('q').focus()}
  if(e.key==='Escape'){document.getElementById('q').value='';filter()}
});
"""


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.0f%s" % (n, u) if u == "B" else "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fTB" % n


def scan(root):
    out = {g[0]: [] for g in GROUPS}
    out["other"] = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f in SKIP_FILES or f.startswith("."):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                st = os.stat(p)
            except OSError:
                continue
            key = "other"
            for k, pref, _, _ in GROUPS:
                if rel.startswith(pref + "/") or rel == pref:
                    key = k
                    break
            out.setdefault(key, []).append({
                "name": f, "path": rel, "size": st.st_size,
                "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M"),
                "ext": os.path.splitext(f)[1].lstrip(".").lower() or "file",
            })
    for v in out.values():
        v.sort(key=lambda x: x["path"])
    return out


def render(root, data):
    total = sum(len(v) for v in data.values())
    size = sum(x["size"] for v in data.values() for x in v)
    name = os.path.basename(os.path.abspath(root))
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>导演台 · %s</title><style>%s</style><div class="wrap">' % (html.escape(name), CSS)]
    parts.append('<aside class="side"><div class="brand">导演台 · 资产看板</div>'
                 '<div class="sub">Wumao Short-Drama Director · V1.0.0</div><div class="nav">')
    parts.append('<a data-g="all" class="on" onclick="show(\'all\')"><span class="ico">◧</span>全部资产'
                 '<span class="n">%d</span></a>' % total)
    for k, pref, label, ico in GROUPS:
        parts.append('<a data-g="%s" onclick="show(\'%s\')"><span class="ico">%s</span>%s'
                     '<span class="n">%d</span></a>' % (k, k, ico, label, len(data.get(k, []))))
    parts.append('</div></aside><main class="main">')
    parts.append('<h1>%s</h1><div class="meta">项目根目录：%s ｜ 生成于 %s</div>' %
                 (html.escape(name), html.escape(root), datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    parts.append('<div class="stats">')
    for label, val in (("文件总数", str(total)), ("总体积", human(size)),
                       ("资产分类", str(len(GROUPS))), ("角色档案", str(len(data.get("characters", [])))),
                       ("投喂包", str(len(data.get("feed", []))))):
        parts.append('<div class="stat"><b>%s</b><span>%s</span></div>' % (val, label))
    parts.append('</div><div class="tools"><input id="q" placeholder="搜索文件名 / 路径…  (Ctrl+F 聚焦，Esc 清空)"'
                 ' oninput="filter()"><span class="hint" id="hit"></span></div>')
    for k, pref, label, ico in GROUPS + [("other", "", "其他", "·")]:
        items = data.get(k, [])
        parts.append('<h2 class="sec" data-g="%s">%s %s <span style="color:var(--dim);font-weight:400;font-size:12px">%d 项</span></h2>' %
                     (k, ico, label, len(items)))
        parts.append('<div class="grid" data-g="%s">' % k)
        if not items:
            parts.append('<div class="empty">暂无文件</div>')
        for x in items:
            parts.append('<div class="card"><div class="fn">%s</div><div class="path">%s</div>'
                         '<span class="tag">%s</span><span class="tag t2">%s</span>'
                         '<div class="ft">%s ｜ %s</div></div>' %
                         (html.escape(x["name"]), html.escape(x["path"]),
                          html.escape(x["ext"].upper()), label, human(x["size"]), x["mtime"]))
        parts.append('</div>')
    parts.append('<footer>分类口径见 references/output-directory-spec.md ｜ 唯一事实源 project_state.json ｜ '
                 '本看板为单文件 HTML，可离线打开</footer></main></div><script>%s</script></html>' % JS)
    return "\n".join(parts)


def self_test():
    t = tempfile.mkdtemp(prefix="wb-board-")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import init_project_tree
        root = os.path.join(t, "proj")
        init_project_tree.build(root, "自测")
        with open(os.path.join(root, "02_assets", "characters", "女主.md"), "w", encoding="utf-8") as f:
            f.write("test")
        d = scan(root)
        if not d["characters"]:
            print("[!] 角色分类未命中"); return False
        out = render(root, d)
        if "导演台" not in out or "女主.md" not in out:
            print("[!] HTML 内容缺失"); return False
        print("[+] build_asset_board self-test PASSED")
        return True
    finally:
        shutil.rmtree(t, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="生成按资产分类的导演台看板")
    ap.add_argument("--root")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if not a.root:
        print("[!] 需要 --root <项目目录>"); return 2
    out = a.out or os.path.join(a.root, "07_reports", "board.html")
    d = scan(a.root)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(a.root, d))
    print("[+] 看板已生成：%s" % os.path.abspath(out))
    print("[+] %d 个文件 / %s / %d 类" %
          (sum(len(v) for v in d.values()), human(sum(x["size"] for v in d.values() for x in v)), len(GROUPS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
