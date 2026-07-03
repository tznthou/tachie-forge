#!/usr/bin/env python3
"""Remove the background from an existing anime tachie image.

MVP de-background pipeline for the `remove-tachie-bg` skill:
  downscale -> rembg isnet-anime -> alpha clamp -> (green: de-green) ->
  transparent PNG + dark/white check previews.

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

# 函式庫 API 而非 rembg CLI: CLI 進入點無條件 import server/GUI 依賴(在 [cli] extra,
# 拖 gradio/fastapi 全套), 函式庫核心只需 [cpu]; CLI 的 i 命令內部即是 remove(bytes, session)
try:
    from rembg import new_session, remove as rembg_remove
except ImportError as e:
    sys.exit(f"[error] rembg import failed ({e}). Is rembg[cpu] installed? See requirements.txt")


def main():
    ap = argparse.ArgumentParser(description="De-background an anime tachie image.")
    ap.add_argument("input", help="path to the source image")
    ap.add_argument("-o", "--output", required=True, help="path for the transparent RGBA PNG")
    ap.add_argument(
        "--bg-type",
        choices=["green", "solid", "transparent", "other"],
        default="other",
        help="original background type; 'green' triggers green-spill decontamination",
    )
    ap.add_argument("--max-edge", type=int, default=1536, help="downscale long edge to this (default 1536)")
    ap.add_argument("--preview-dir", default=None, help="dir for _darkcheck/_whitecheck previews (default: output dir)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"[error] input not found: {args.input}")

    # 1. load + downscale (立繪用不到 8K,超大圖 rembg 慢且不會更準)
    try:
        img = Image.open(args.input).convert("RGB")
    except OSError as e:  # UnidentifiedImageError(壞檔/非圖片)也是 OSError
        sys.exit(f"[error] cannot read image ({e}). PNG/JPEG/WebP supported.")
    w, h = img.size
    scale = min(1.0, args.max_edge / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
        print(f"[downscale] {w}x{h} -> {img.size[0]}x{img.size[1]}")

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

    if args.bg_type == "green":
        print(f"[de-green] decontaminated {greenish_count} edge pixels")
    print(f"[done] {args.output}")
    print(f"[check] eyeball BOTH previews:\n        {previews[0]}\n        {previews[1]}")


if __name__ == "__main__":
    main()
