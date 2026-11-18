#!/usr/bin/env python3
"""Remove the background from an existing anime tachie image.

MVP de-background pipeline for the `remove-tachie-bg` skill:
  downscale -> rembg isnet-anime -> alpha clamp -> (green: de-green +
  solid-green dig-out + speck cleanup) -> transparent PNG + dark/white
  check previews.

`--bg-type native` is the no-rembg path for images the generator already
delivered with a real alpha channel: verify the alpha is real -> snap
near-opaque alpha to 255 -> drop near-transparent alpha -> bleed edge colour
into fully transparent pixels -> same previews.

`--match-size <image>` replaces the downscale step on either path: the input
is resized to that reference image's pixel size, so every expression of one
character ends up on the same canvas as its base tachie.

See skills/remove-tachie-bg/SKILL.md for when/how to use.
Deliberately NOT included (v2): background auto-detection, alpha-matting
refinement, batch mode, complex-background handling.
"""
import argparse
import io
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# native 路徑門檻 (2026-11-18 hongliu 13 張實測: 全透明 48.5–49.4%, 本體 alpha 落在 250–254)
NATIVE_MIN_TRANSPARENT = 0.10  # 全透明像素低於此比例 → 不是真透明(棋盤格假透明或畫了背景)
NATIVE_OPAQUE_FROM = 250       # 本體 alpha 250–254 會微透出底色 → 拉到 255
NATIVE_DROP_BELOW = 30         # 與 rembg 路徑的 α≤30→0 一致; 也清掉 image_gen 留在 α≈2–3 的綠底殘色
EXIT_NOT_NATIVE = 3            # 呼叫端據此走退路: 基準圖退回 rembg, 表情差分改綠幕重生
NOT_NATIVE_HINT = "take the fallback route (base image: rembg; expression variant: green-screen regeneration)"
ASPECT_TOLERANCE = 0.01        # --match-size 容許的長寬比誤差


def load_scaled(path, mode, max_edge, match_size=None):
    """Open + resize: 給了 match_size 就縮放到那個尺寸, 否則只把長邊壓到 max_edge
    (立繪用不到 8K, 超大圖 rembg 慢且不會更準).

    縮放一律在這裡做, 不在收尾之後: Pillow 縮 RGBA 走 premultiplied alpha, 縮完全透明像素的
    RGB 會歸零, 之後才做的 edge bleed 會被洗掉.
    """
    try:
        img = Image.open(path).convert(mode)
    except OSError as e:  # UnidentifiedImageError(壞檔/非圖片)也是 OSError
        sys.exit(f"[error] cannot read image ({e}). PNG/JPEG/WebP supported.")
    w, h = img.size
    if match_size:
        tw, th = match_size
        # 長寬比差超過 1% 就不縮: 硬拉會把角色壓扁或拉長, 這種圖該重生而不是修
        if abs(w * th - h * tw) > ASPECT_TOLERANCE * h * tw:
            sys.exit(f"[error] aspect ratio mismatch: input is {w}x{h}, --match-size reference is {tw}x{th}. "
                     "Resizing would distort the character — regenerate the image instead.")
        if (w, h) == (tw, th):
            print(f"[match-size] already {tw}x{th}")
        else:
            img = img.resize((tw, th))
            print(f"[match-size] {w}x{h} -> {tw}x{th}")
        return img
    scale = min(1.0, max_edge / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
        print(f"[downscale] {w}x{h} -> {img.size[0]}x{img.size[1]}")
    return img


def native_pipeline(args):
    """Finalize a generator-native RGBA image without re-segmenting it."""
    src = Image.open(args.input)
    if "A" not in src.getbands():
        print(f"[not-native] no alpha channel (mode={src.mode}) — {NOT_NATIVE_HINT}")
        sys.exit(EXIT_NOT_NATIVE)
    arr = np.array(load_scaled(args.input, "RGBA", args.max_edge, args.match_px))
    a = arr[:, :, 3].astype(np.int32)

    transparent_share = float((a == 0).mean())
    if transparent_share < NATIVE_MIN_TRANSPARENT:
        print(f"[not-native] only {transparent_share:.1%} fully transparent px "
              f"(< {NATIVE_MIN_TRANSPARENT:.0%}) — likely fake/checkered transparency; {NOT_NATIVE_HINT}")
        sys.exit(EXIT_NOT_NATIVE)

    snapped = int(((a >= NATIVE_OPAQUE_FROM) & (a < 255)).sum())
    dropped = int(((a > 0) & (a <= NATIVE_DROP_BELOW)).sum())
    a[a >= NATIVE_OPAQUE_FROM] = 255
    a[a <= NATIVE_DROP_BELOW] = 0
    arr[:, :, 3] = a.astype(np.uint8)

    # 全透明像素的 RGB 改成最近可見像素的顏色 (edge bleed): 引擎縮放/雙線性濾波會混到
    # 透明像素的 RGB, 留著綠底殘色會滲綠邊, 塗黑則滲黑邊; 等同 Godot Fix Alpha Border 先做掉
    hidden = a == 0
    if hidden.any() and (~hidden).any():
        _, (iy, ix) = ndimage.distance_transform_edt(hidden, return_indices=True)
        for c in range(3):
            arr[:, :, c] = arr[iy, ix, c]

    stats = [f"[native] real alpha: {transparent_share:.1%} fully transparent px",
             f"[native] snapped {snapped} px alpha {NATIVE_OPAQUE_FROM}-254 -> 255, "
             f"dropped {dropped} px alpha 1-{NATIVE_DROP_BELOW} -> 0, edge colour bled into transparent px"]
    return arr, stats


def rembg_pipeline(args):
    """Segment with rembg, clamp alpha, and (green only) de-green."""
    # 函式庫 API 而非 rembg CLI: CLI 進入點無條件 import server/GUI 依賴(在 [cli] extra,
    # 拖 gradio/fastapi 全套), 函式庫核心只需 [cpu]; CLI 的 i 命令內部即是 remove(bytes, session)
    try:
        from rembg import new_session, remove as rembg_remove
    except ImportError as e:
        sys.exit(f"[error] rembg import failed ({e}). Is rembg[cpu] installed? See requirements.txt")

    # 1. load + downscale
    img = load_scaled(args.input, "RGB", args.max_edge, args.match_px)

    # 2. rembg (anime-tuned segmentation; 餵 PNG bytes — 輸出驗證基準建立在此路徑, 勿改餵 PIL 物件)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cut_bytes = rembg_remove(buf.getvalue(), session=new_session("isnet-anime"))
    rgba = Image.open(io.BytesIO(cut_bytes)).convert("RGBA")
    arr = np.array(rgba)
    a = arr[:, :, 3].astype(np.int32)

    # 3. alpha clamp (>=120 -> opaque, <=30 -> transparent; keep the feathered rim between)
    a[a >= 120] = 255
    a[a <= 30] = 0
    arr[:, :, 3] = a.astype(np.uint8)

    # 4. green-spill decontamination (only for green screens)
    greenish_count = 0
    if args.bg_type == "green":
        r = arr[:, :, 0].astype(int)
        g = arr[:, :, 1].astype(int)
        b = arr[:, :, 2].astype(int)
        partial = (a > 30) & (a < 255)               # feathered edge band
        greenish = partial & (g > r + 18) & (g > b + 18)
        greenish_count = int(greenish.sum())
        # 輕壓:偏綠像素的綠通道壓到 max(r,b),不做完整反解
        arr[:, :, 1] = np.where(greenish, np.maximum(r, b), g).astype(np.uint8)

    # 4b. solid-green dig-out (green only): feather 帶去綠救不到 alpha=255 的縫隙綠塊
    # (rembg 把封閉縫隙裡的綠背景誤判為前景), 色域挖除後清掉挖剩的孤立碎片.
    # 角色本身含飽和綠(綠瞳/綠髮/綠衣)會被誤殺 → --no-green-dig 跳過
    dug_count = 0
    speck_count = 0
    if args.bg_type == "green" and not args.no_green_dig:
        r = arr[:, :, 0].astype(int)
        g = arr[:, :, 1].astype(int)
        b = arr[:, :, 2].astype(int)
        a2 = arr[:, :, 3]
        green_bg = (a2 > 0) & (g > r + 40) & (g > b + 40) & (g > 120)
        dug_count = int(green_bg.sum())
        arr[:, :, 3] = np.where(green_bg, 0, a2).astype(np.uint8)

        mask = arr[:, :, 3] > 0
        labels, n = ndimage.label(mask)
        if n > 1:
            sizes = ndimage.sum(mask, labels, range(1, n + 1))
            keep = np.argmax(sizes) + 1
            small = np.isin(labels, [i for i in range(1, n + 1) if i != keep and sizes[i - 1] <= 64])
            speck_count = int(small.sum())
            arr[:, :, 3] = np.where(small, 0, arr[:, :, 3]).astype(np.uint8)

    stats = []
    if args.bg_type == "green":
        stats.append(f"[de-green] decontaminated {greenish_count} edge pixels")
        if not args.no_green_dig:
            stats.append(f"[green-dig] removed {dug_count} solid green px"
                         + (f" + {speck_count} px in isolated specks" if speck_count else ""))
    return arr, stats


def main():
    ap = argparse.ArgumentParser(description="De-background an anime tachie image.")
    ap.add_argument("input", help="path to the source image")
    ap.add_argument("-o", "--output", required=True, help="path for the transparent RGBA PNG")
    ap.add_argument(
        "--bg-type",
        choices=["green", "solid", "transparent", "other", "native"],
        default="other",
        help="original background type; 'green' triggers green-spill decontamination + solid-green dig-out; "
             f"'native' = generator already delivered real alpha (no rembg; exits {EXIT_NOT_NATIVE} if the alpha is not real)",
    )
    ap.add_argument(
        "--no-green-dig",
        action="store_true",
        help="skip solid-green residue dig-out (escape hatch when the character's own palette contains saturated green, e.g. green eyes/hair/outfit)",
    )
    ap.add_argument("--max-edge", type=int, default=1536, help="downscale long edge to this (default 1536)")
    ap.add_argument(
        "--match-size",
        metavar="IMAGE",
        default=None,
        help="resize the input to this reference image's pixel size before processing "
             "(expression variant -> the character's base tachie); overrides --max-edge, "
             "refuses if the aspect ratios differ by more than 1%%",
    )
    ap.add_argument("--preview-dir", default=None, help="dir for _darkcheck/_whitecheck previews (default: output dir)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"[error] input not found: {args.input}")

    args.match_px = None
    if args.match_size:
        try:
            with Image.open(args.match_size) as ref:
                args.match_px = ref.size
        except OSError as e:
            sys.exit(f"[error] cannot read --match-size reference ({e})")

    if args.bg_type == "native":
        arr, stats = native_pipeline(args)
    else:
        arr, stats = rembg_pipeline(args)

    out = Image.fromarray(arr, "RGBA")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.save(args.output)

    # 5. dual-background previews (dark exposes bright artifacts, white exposes dark/green)
    pv = args.preview_dir or os.path.dirname(os.path.abspath(args.output))
    os.makedirs(pv, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.output))[0]
    previews = []
    for name, bg in [("darkcheck", (30, 30, 38, 255)), ("whitecheck", (255, 255, 255, 255))]:
        canvas = Image.new("RGBA", out.size, bg)
        canvas.alpha_composite(out)
        p = os.path.join(pv, f"{base}_{name}.png")
        canvas.convert("RGB").save(p)
        previews.append(p)

    for line in stats:
        print(line)
    print(f"[done] {args.output}")
    print(f"[check] eyeball BOTH previews:\n        {previews[0]}\n        {previews[1]}")


if __name__ == "__main__":
    main()
