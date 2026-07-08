#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate-brand-assets.py — WP9 tvOS App Icon & Top Shelf 素材管线

程序化生成 wiliwili tvOS 的「App Icon & Top Shelf Image」Brand Assets：
  - 三层视差素材（back 渐变+光斑+星点/流星 / middle 粉色云层剪影 / front 白色猫 logo）
  - 组装成 Xcode 规范的 Assets.xcassets/*.brandassets 目录（含全部 Contents.json）
  - 输出到 assets/generated/，脚本幂等，自检输出每个生成 PNG 的真实分辨率

前景猫 logo：
  - 若存在 assets/logo-source.png（用户放入的白色线条猫/粉底），用「接近白色」色距
    抠图得到带 alpha 的纯白 logo；
  - 若缺失，则用程序绘制的占位猫脸（白色线条：圆脸+双尖耳+眯眼+张嘴+胡须）并打印醒目 WARN，
    保证 CI 管线可端到端跑通。

依赖：Pillow（PIL）。沙箱/CI 安装：pip install pillow --break-system-packages
用法：python3 scripts/generate-brand-assets.py [--source PATH] [--out DIR]

Brand Assets 目录/Contents.json 结构依据（真实 Xcode 工程样例，已核对）：
  - bitrise-io/sample-tvos-app  …/App Icon & Top Shelf Image.brandassets/Contents.json
  - optimizely/tvOS-demo        …/App Icon - Large.imagestack (layers / imagestacklayer / Content.imageset)
"""

import argparse
import json
import math
import os
import random
import shutil
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.stderr.write(
        "\n[FATAL] 需要 Pillow：pip install pillow --break-system-packages\n\n"
    )
    raise

# ---------------------------------------------------------------------------
# 设计常量（对齐 WP9 Spec）
# ---------------------------------------------------------------------------
GRAD_TOP = (0xFB, 0x72, 0x99)     # bilibili 主色 #FB7299
GRAD_BOTTOM = (0xFF, 0x85, 0xB7)  # #FF85B7
CLOUD_COLOR = (0xFF, 0xB8, 0xD6)  # 更浅的粉，用于中景云层/丘陵
STAR_SEED = 20260708              # 固定种子 → 幂等（每次生成同样的星点分布）

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = os.path.join(REPO_ROOT, "assets", "logo-source.png")
DEFAULT_OUT = os.path.join(REPO_ROOT, "assets", "generated")

BRAND_DIR_NAME = "App Icon & Top Shelf Image.brandassets"

INFO = {"version": 1, "author": "xcode"}


def wjson(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# 图形基元
# ---------------------------------------------------------------------------
def make_gradient(w, h):
    """垂直渐变 GRAD_TOP → GRAD_BOTTOM（先做 1×h 列再放大，快且平滑）。"""
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = round(GRAD_TOP[0] + (GRAD_BOTTOM[0] - GRAD_TOP[0]) * t)
        g = round(GRAD_TOP[1] + (GRAD_BOTTOM[1] - GRAD_TOP[1]) * t)
        b = round(GRAD_TOP[2] + (GRAD_BOTTOM[2] - GRAD_TOP[2]) * t)
        col.putpixel((0, y), (r, g, b))
    return col.resize((w, h))


def render_back(w, h):
    """背景层：渐变 + 柔光斑 + 星点 + 流星线。返回不透明 RGBA。"""
    base = make_gradient(w, h).convert("RGBA")
    rnd = random.Random(STAR_SEED)
    unit = max(w, h)

    # 柔光斑（几个大半径的白色低透明径向块，高斯模糊）
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(3):
        cx = rnd.uniform(0.15, 0.85) * w
        cy = rnd.uniform(0.10, 0.55) * h
        rad = rnd.uniform(0.12, 0.22) * unit
        gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                   fill=(255, 255, 255, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(6, unit * 0.03)))
    base = Image.alpha_composite(base, glow)

    # 星点
    stars = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    n_stars = max(18, int(w * h / 26000))
    for _ in range(n_stars):
        sx = rnd.uniform(0, w)
        sy = rnd.uniform(0, h * 0.62)
        sr = rnd.uniform(0.0008, 0.0028) * unit
        a = rnd.randint(120, 235)
        sd.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, a))

    # 流星线（1-2 条带拖尾的斜线，画完轻微模糊）
    for _ in range(2):
        mx = rnd.uniform(0.2, 0.9) * w
        my = rnd.uniform(0.05, 0.35) * h
        length = rnd.uniform(0.10, 0.20) * unit
        ang = math.radians(rnd.uniform(200, 235))
        ex = mx + length * math.cos(ang)
        ey = my + length * math.sin(ang)
        sd.line([mx, my, ex, ey], fill=(255, 255, 255, 180),
                width=max(1, int(unit * 0.0016)))
    stars = stars.filter(ImageFilter.GaussianBlur(radius=max(0.4, unit * 0.0008)))
    base = Image.alpha_composite(base, stars)
    return base


def render_middle(w, h):
    """中景层：更浅粉的云朵/丘陵剪影（模糊圆叠加），置于下半部。透明背景。"""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(STAR_SEED + 1)
    unit = max(w, h)
    baseline = h * 0.72
    # 一排交叠的圆模拟起伏云层/丘陵
    n = max(5, int(w / (unit * 0.14)))
    for i in range(n + 2):
        cx = (i / n) * w + rnd.uniform(-0.05, 0.05) * w
        rad = rnd.uniform(0.12, 0.20) * unit
        cy = baseline + rnd.uniform(-0.03, 0.05) * h
        alpha = rnd.randint(150, 205)
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                  fill=CLOUD_COLOR + (alpha,))
    # 底部填实，保证下缘全出血
    d.rectangle([0, int(baseline + 0.06 * h), w, h], fill=CLOUD_COLOR + (205,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(2, unit * 0.012)))
    return layer


def _draw_placeholder_cat(size):
    """程序化占位白猫脸：圆脸 + 双尖耳 + 眯眼 + 张嘴 + 胡须。透明背景、白色线条。"""
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    W = (255, 255, 255, 255)
    lw = max(2, int(S * 0.018))
    cx, cy = S * 0.5, S * 0.56
    fr = S * 0.30  # 脸半径

    # 双尖耳（三角形）
    ear_dy = fr * 0.95
    ear_w = fr * 0.62
    ear_h = fr * 0.80
    for sgn in (-1, 1):
        ex = cx + sgn * fr * 0.62
        ey = cy - ear_dy
        d.polygon([(ex - ear_w / 2, ey + ear_h),
                   (ex, ey - ear_h * 0.15),
                   (ex + ear_w / 2, ey + ear_h)], outline=W, width=lw)
    # 圆脸
    d.ellipse([cx - fr, cy - fr, cx + fr, cy + fr], outline=W, width=lw)
    # 眯眼（两条上凸弧）
    eye_dx = fr * 0.42
    eye_y = cy - fr * 0.10
    eye_w = fr * 0.34
    eye_h = fr * 0.26
    for sgn in (-1, 1):
        ex = cx + sgn * eye_dx
        d.arc([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
              start=200, end=340, fill=W, width=lw)
    # 鼻子（小三角）
    nx, ny = cx, cy + fr * 0.16
    ns = fr * 0.10
    d.polygon([(nx - ns, ny), (nx + ns, ny), (nx, ny + ns)], fill=W)
    # 张嘴（两条下弧 + 中缝）
    d.arc([cx - fr * 0.34, ny, cx + fr * 0.02, ny + fr * 0.40],
          start=20, end=160, fill=W, width=lw)
    d.arc([cx - fr * 0.02, ny, cx + fr * 0.34, ny + fr * 0.40],
          start=20, end=160, fill=W, width=lw)
    d.line([nx, ny + ns, nx, ny + fr * 0.20], fill=W, width=lw)
    # 胡须（每侧三根）
    for sgn in (-1, 1):
        wx = cx + sgn * fr * 0.30
        for k, dy in enumerate((-0.06, 0.02, 0.10)):
            wy = cy + fr * (0.16 + dy)
            d.line([wx, wy, cx + sgn * fr * 1.15, wy + sgn * 0], fill=W,
                   width=max(1, lw // 2))
    return img


def load_logo(source_path):
    """
    返回 (logo_rgba, used_placeholder:bool)
    logo_rgba：正方形、透明背景、纯白 logo（front 层用）。
    """
    if source_path and os.path.isfile(source_path):
        src = Image.open(source_path).convert("RGBA")
        # 「接近白色」色距抠图：以灰度亮度做软阈值，得到 alpha；颜色强制纯白。
        L = src.convert("L")
        lo, hi = 170, 235
        span = hi - lo
        alpha = L.point(lambda v: 0 if v < lo else (255 if v > hi
                                                    else int((v - lo) / span * 255)))
        # 若原图本身带 alpha，取交集（避免把透明区当白）
        src_a = src.getchannel("A")
        alpha = Image.eval(alpha, lambda x: x)  # copy
        alpha = _min_channel(alpha, src_a)
        white = Image.new("RGBA", src.size, (255, 255, 255, 0))
        white.putalpha(alpha)
        # 收紧到内容包围盒再放正方画布，保证不同源图尺寸下比例一致
        bbox = alpha.getbbox()
        if bbox:
            white = white.crop(bbox)
        logo = _fit_square(white)
        return logo, False

    sys.stderr.write(
        "\n"
        "**********************************************************************\n"
        "* WARN: assets/logo-source.png 不存在 —— 使用【程序化占位猫脸】。      *\n"
        "*       生成的图标仅供 CI 管线端到端验证，非最终视觉。               *\n"
        "*       用户放入白色线条猫 logo 到 assets/logo-source.png 后重跑本脚本。*\n"
        "**********************************************************************\n\n"
    )
    return _draw_placeholder_cat(1024), True


def _min_channel(a, b):
    """逐像素取两个单通道图的较小值（用作 alpha 交集）。"""
    from PIL import ImageChops
    if a.size != b.size:
        b = b.resize(a.size)
    return ImageChops.darker(a, b)


def _fit_square(img):
    """把任意矩形 RGBA 放进透明正方形画布（居中，边长=较长边）。"""
    w, h = img.size
    s = max(w, h)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(img, ((s - w) // 2, (s - h) // 2), img)
    return canvas


def render_front(w, h, logo_sq):
    """前景层：白色猫 logo。banner(宽高比>2)左对齐，其余居中。透明背景。"""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    is_banner = (w / h) > 2.0
    target_h = int(h * (0.62 if is_banner else 0.66))
    scale = target_h / logo_sq.height
    target_w = int(logo_sq.width * scale)
    logo = logo_sq.resize((target_w, target_h), Image.LANCZOS)
    if is_banner:
        x = int(w * 0.06)
        y = (h - target_h) // 2
    else:
        x = (w - target_w) // 2
        y = int(h * 0.5 - target_h / 2)
    layer.paste(logo, (x, y), logo)
    return layer


def composite_flat(w, h, logo_sq):
    """把 back+middle+front 压平成一张不透明 RGB（App Store / Top Shelf 用）。"""
    out = render_back(w, h)
    out = Image.alpha_composite(out, render_middle(w, h))
    out = Image.alpha_composite(out, render_front(w, h, logo_sq))
    return out.convert("RGB")


# ---------------------------------------------------------------------------
# 目录/JSON 组装
# ---------------------------------------------------------------------------
def imageset(dir_path, entries):
    """
    entries: list of (idiom, scale, PIL.Image | None)
    生成 imageset 目录：Contents.json + 各 PNG。
    """
    os.makedirs(dir_path, exist_ok=True)
    images = []
    for idiom, scale, img in entries:
        entry = {"idiom": idiom, "scale": scale}
        if img is not None:
            fname = "img-%s-%s.png" % (idiom, scale)
            img.save(os.path.join(dir_path, fname))
            entry["filename"] = fname
        images.append(entry)
    wjson(os.path.join(dir_path, "Contents.json"),
          {"images": images, "info": INFO})


def imagestacklayer(dir_path, content_entries):
    """imagestacklayer：Contents.json(仅 info) + Content.imageset/。"""
    os.makedirs(dir_path, exist_ok=True)
    wjson(os.path.join(dir_path, "Contents.json"), {"info": INFO})
    imageset(os.path.join(dir_path, "Content.imageset"), content_entries)


def imagestack(dir_path, layers):
    """
    imagestack：Contents.json(layers) + 每个 *.imagestacklayer/。
    layers: list of (layer_name, content_entries)
    """
    os.makedirs(dir_path, exist_ok=True)
    layer_refs = []
    for name, entries in layers:
        ln = "%s.imagestacklayer" % name
        imagestacklayer(os.path.join(dir_path, ln), entries)
        layer_refs.append({"filename": ln})
    wjson(os.path.join(dir_path, "Contents.json"),
          {"layers": layer_refs, "info": INFO})


def build(out_dir, source_path):
    logo_sq, placeholder = load_logo(source_path)

    xcassets = os.path.join(out_dir, "Assets.xcassets")
    brand = os.path.join(xcassets, BRAND_DIR_NAME)
    # 幂等：清空受管输出
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(brand, exist_ok=True)
    wjson(os.path.join(xcassets, "Contents.json"), {"info": INFO})

    # ---- App Icon (home) 400x240pt：3 层视差，@1x/@2x -------------------
    def layer_entries(kind):
        e = []
        for scale, (w, h) in (("1x", (400, 240)), ("2x", (800, 480))):
            if kind == "back":
                img = render_back(w, h)
            elif kind == "middle":
                img = render_middle(w, h)
            else:
                img = render_front(w, h, logo_sq)
            e.append(("tv", scale, img))
        return e

    imagestack(
        os.path.join(brand, "App Icon.imagestack"),
        [("Front", layer_entries("front")),
         ("Middle", layer_entries("middle")),
         ("Back", layer_entries("back"))],
    )

    # ---- App Icon - App Store 1280x768：单层压平（@1x）------------------
    appstore = composite_flat(1280, 768, logo_sq).convert("RGBA")
    imagestack(
        os.path.join(brand, "App Icon - App Store.imagestack"),
        [("Front", [("tv", "1x", appstore)])],
    )

    # ---- Top Shelf Image Wide 2320x720pt：tv + tv-marketing，@1x/@2x ----
    wide_1x = composite_flat(2320, 720, logo_sq)
    wide_2x = composite_flat(4640, 1440, logo_sq)
    imageset(
        os.path.join(brand, "Top Shelf Image Wide.imageset"),
        [("tv", "1x", wide_1x), ("tv", "2x", wide_2x),
         ("tv-marketing", "1x", wide_1x), ("tv-marketing", "2x", wide_2x)],
    )

    # ---- Top Shelf Image 1920x720 / 3840x1440：tv @1x/@2x --------------
    ts_1x = composite_flat(1920, 720, logo_sq)
    ts_2x = composite_flat(3840, 1440, logo_sq)
    imageset(
        os.path.join(brand, "Top Shelf Image.imageset"),
        [("tv", "1x", ts_1x), ("tv", "2x", ts_2x)],
    )

    return xcassets, placeholder


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def self_check(xcassets_dir):
    pngs, jsons, bad = [], [], []
    for root, _dirs, files in os.walk(xcassets_dir):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, xcassets_dir)
            if fn.endswith(".png"):
                with Image.open(p) as im:
                    pngs.append((rel, im.size))
            elif fn == "Contents.json":
                try:
                    with open(p, encoding="utf-8") as f:
                        json.load(f)
                    jsons.append(rel)
                except Exception as exc:  # noqa
                    bad.append((rel, str(exc)))

    print("\n=== 生成 PNG 分辨率自检（%d 个）===" % len(pngs))
    for rel, (w, h) in pngs:
        print("  %5dx%-5d  %s" % (w, h, rel))
    print("\n=== Contents.json 校验（%d 个，均合法 JSON）===" % len(jsons))
    for rel in jsons:
        print("  ok  %s" % rel)
    if bad:
        print("\n!!! 非法 Contents.json:")
        for rel, err in bad:
            print("  FAIL %s : %s" % (rel, err))
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Generate tvOS Brand Assets")
    ap.add_argument("--source", default=DEFAULT_SOURCE,
                    help="白色猫 logo 源图 (默认 assets/logo-source.png)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="输出目录 (默认 assets/generated)")
    args = ap.parse_args()

    print("[generate-brand-assets] source=%s" % args.source)
    print("[generate-brand-assets] out   =%s" % args.out)
    xcassets, placeholder = build(args.out, args.source)
    ok = self_check(xcassets)

    print("\n[generate-brand-assets] 完成。xcassets=%s" % xcassets)
    if placeholder:
        print("[generate-brand-assets] 注意：使用了占位猫脸（logo-source.png 缺失）。")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
