#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_h3_refs.py — 从「设定板」派生 H3 出片专用单图参考。

病根（2026-11-20 实拍复盘）：
  看板用的角色板是「1 张大脸 + 3 套无脸人台/无头衣服 + 飘浮发型」，
  场景板是 3x3 九宫格（每格还带乱码标题条），道具板是 2x2。
  这些板当 H3 的 ref_image 喂进去，模型每次抓到的是不同区域：
    - 脸在每段之间飘（抓到"无脸人台"就丢脸，抓到发型就换头）
    - 空间乱（九宫格里随机一格当场景 → 一会儿车里一会儿车外）
    - 画面里出现多部手机 / 多个戒指盒 / 半截无头身体
  结论：**身份参考板 ≠ 出片参考图**。出片必须给「一人一张、正面、单格」的单图。

本脚本做的事：
  1. characters: 自动找角色板里"大脸"与右侧换装区之间的背景竖缝 → 裁出正脸，
     居中贴到 9:16 画布（背景取板子底色），得到「半身正面参考」。
  2. scenes: 从九宫格按 (row, col) 取单格，并裁掉上下标题条。
  3. props: 从 2x2 取单格。

用法：
  python build_h3_refs.py --root <项目根>            # 读 02_assets/h3_refs.spec.json
  python build_h3_refs.py --root <项目根> --dry-run  # 只打印将要生成的文件
缺 spec 时按 02_assets/{characters,scenes,props}/ 里的文件名自动生成一份默认 spec。
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow：pip install pillow", file=sys.stderr)
    sys.exit(2)

OUT_DIR = "02_assets/h3_refs"
SPEC_REL = "02_assets/h3_refs.spec.json"


def bg_color(im, box=8):
    """取左上角一小块的中位色当板子底色（设定板背景都是纯色）。"""
    w, h = im.size
    px = im.crop((0, 0, box, box)).convert("RGB").getdata()
    rs = sorted(p[0] for p in px)
    gs = sorted(p[1] for p in px)
    bs = sorted(p[2] for p in px)
    m = len(rs) // 2
    return (rs[m], gs[m], bs[m])


def find_face_seam(im, bg, tol=18, fallback_ratio=0.44):
    """从左往右找第一道"几乎整列都是底色"的竖缝 —— 大脸与换装区的分界。

    只认 0.20~0.46 宽度区间内的缝：设定板右侧换装区之间也有缝（在 0.63 附近），
    不设上界会把一整套「无脸人台」一起裁进来（实测李洛板就踩了这个坑）。
    """
    w, h = im.size
    small = im.convert("RGB").resize((w // 8, h // 8))
    sw, sh = small.size
    px = small.load()
    for x in range(int(sw * 0.20), int(sw * 0.46)):
        hits = 0
        for y in range(sh):
            r, g, b = px[x, y]
            if abs(r - bg[0]) <= tol and abs(g - bg[1]) <= tol and abs(b - bg[2]) <= tol:
                hits += 1
        if hits >= sh * 0.97:
            return x * 8
    return int(w * fallback_ratio)


def build_character(src: Path, dst: Path, ratio=(9, 16)):
    im = Image.open(src).convert("RGB")
    bg = bg_color(im)
    seam = find_face_seam(im, bg)
    face = im.crop((0, 0, seam, im.size[1]))
    tw = int(round(face.size[1] * ratio[0] / ratio[1]))
    tw = max(tw, face.size[0])
    canvas = Image.new("RGB", (tw, face.size[1]), bg)
    canvas.paste(face, ((tw - face.size[0]) // 2, 0))
    canvas.save(dst, quality=95)
    return {"seam": seam, "size": canvas.size}


def build_cell(src: Path, dst: Path, row: int, col: int, grid=(3, 3), trim=46, blur=1.6):
    """取单格 → 裁掉上下标题条 → 轻度模糊。

    场景板上除了标题条还有 AI 生成的假按钮/假铭牌（"⑥反视镜"之类），
    裁不干净，于是统一做一次小半径高斯模糊：空间结构、光影、机位都还在，
    但乱码文字与按钮轮廓糊掉，H3 不会照着画字幕/UI。
    """
    im = Image.open(src).convert("RGB")
    w, h = im.size
    cw, ch = w // grid[1], h // grid[0]
    left, top = col * cw + 3, row * ch + trim
    right, bottom = (col + 1) * cw - 3, (row + 1) * ch - trim
    crop = im.crop((left, top, right, bottom))
    if blur:
        from PIL import ImageFilter
        crop = crop.filter(ImageFilter.GaussianBlur(blur))
    crop.save(dst, quality=95)
    return {"size": crop.size, "cell": f"r{row}c{col}"}


def default_spec(root: Path):
    spec = {"characters": [], "scenes": [], "props": []}
    for d, key in (("02_assets/characters", "characters"), ("02_assets/scenes", "scenes"),
                   ("02_assets/props", "props")):
        p = root / d
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.png")):
            if f.stem.endswith(("_bak", "_H3")):
                continue
            item = {"file": f.relative_to(root).as_posix(),
                    "out": f"h3ref_{f.stem}.png"}
            if key == "characters":
                item["mode"] = "face"
            else:
                item["cell"] = [0, 0]
            spec[key].append(item)
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-spec", action="store_true", help="把默认 spec 落盘供人工改格位")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    spec_path = root / SPEC_REL
    if spec_path.is_file():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    else:
        spec = default_spec(root)
        if a.write_spec and not a.dry_run:
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"已写默认 spec：{SPEC_REL}（请核对每个 scene 的 cell 格位）")
    out_dir = root / OUT_DIR
    if not a.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    made, skipped = [], []
    for item in spec.get("characters", []):
        src = root / item["file"]
        dst = out_dir / item.get("out", f"h3ref_{src.stem}.png")
        if not src.is_file():
            skipped.append((item["file"], "源缺失"))
            continue
        if a.dry_run:
            print(f"[char] {item['file']} -> {OUT_DIR}/{dst.name}")
            continue
        info = build_character(src, dst)
        made.append((dst.name, f"脸宽{info['seam']}px {info['size'][0]}x{info['size'][1]}"))
    for key, grid in (("scenes", (3, 3)), ("props", (2, 2))):
        for item in spec.get(key, []):
            src = root / item["file"]
            dst = out_dir / item.get("out", f"h3ref_{src.stem}.png")
            if not src.is_file():
                skipped.append((item["file"], "源缺失"))
                continue
            row, col = item.get("cell", [0, 0])
            if a.dry_run:
                print(f"[{key}] {item['file']} cell r{row}c{col} -> {OUT_DIR}/{dst.name}")
                continue
            info = build_cell(src, dst, row, col, grid=grid)
            made.append((dst.name, f"{info['cell']} {info['size'][0]}x{info['size'][1]}"))
    if a.dry_run:
        return
    print(f"生成 {len(made)} 张 → {OUT_DIR}/")
    for n, note in made:
        print(f"  {n}  ({note})")
    for n, why in skipped:
        print(f"  跳过 {n}：{why}")


if __name__ == "__main__":
    main()
