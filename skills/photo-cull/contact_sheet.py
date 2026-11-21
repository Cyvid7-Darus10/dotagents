#!/usr/bin/env python3
"""
Build labeled contact sheets (thumbnail grids) from a culling shortlist so the
whole shortlist can be reviewed in a handful of images instead of hundreds of
separate Read calls.

By default it reads <folder>/metrics.csv and uses the shortlist (sharpest clean
frame per burst). Pass --all to sheet every clean frame, or --files to sheet an
explicit list.

Usage:
    python3 contact_sheet.py <folder> [--all] [--cols 6] [--rows 5]
                                      [--thumb 320] [--files a.ARW b.ARW ...]

Sheets are written to <folder>/_contact_sheets/sheet_NN.jpg
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def load_rows(folder):
    path = os.path.join(folder, "metrics.csv")
    if not os.path.exists(path):
        sys.exit(f"No metrics.csv in {folder} — run cull.py first.")
    with open(path) as f:
        return list(csv.DictReader(f))


def shortlist(rows):
    """Sharpest clean (unflagged) frame per burst."""
    best = {}
    for r in rows:
        if r["flags"]:
            continue
        b = r["burst"]
        s = float(r["sharpness"])
        if b not in best or s > float(best[b]["sharpness"]):
            best[b] = r
    return [best[b] for b in sorted(best, key=lambda x: int(x))]


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def build(folder, picks, cols, rows_per, thumb):
    out_dir = os.path.join(folder, "_contact_sheets")
    os.makedirs(out_dir, exist_ok=True)
    label_h = max(18, thumb // 12)
    cell_w, cell_h = thumb, thumb + label_h
    pad = 6
    per_sheet = cols * rows_per
    f = font(max(12, thumb // 22))

    sheets = []
    for s in range(0, len(picks), per_sheet):
        chunk = picks[s:s + per_sheet]
        sw = cols * cell_w + pad * (cols + 1)
        sh = rows_per * cell_h + pad * (rows_per + 1)
        sheet = Image.new("RGB", (sw, sh), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        for i, r in enumerate(chunk):
            cx = pad + (i % cols) * (cell_w + pad)
            cy = pad + (i // cols) * (cell_h + pad)
            jpg = os.path.join(folder, r["preview"])
            try:
                im = Image.open(jpg)
                im.thumbnail((thumb, thumb))
                ox = cx + (thumb - im.width) // 2
                oy = cy + (thumb - im.height) // 2
                sheet.paste(im, (ox, oy))
            except OSError:
                draw.rectangle([cx, cy, cx + thumb, cy + thumb], outline=(80, 80, 80))
            name = os.path.splitext(r["file"])[0]
            label = f"{name}  b{r['burst']} s{int(float(r['sharpness']))}"
            if r["flags"]:
                label += f"  [{r['flags']}]"
            draw.text((cx + 3, cy + thumb + 2), label, fill=(235, 235, 235), font=f)
        sheet_path = os.path.join(out_dir, f"sheet_{s // per_sheet + 1:02d}.jpg")
        sheet.save(sheet_path, quality=85)
        sheets.append(sheet_path)
    return sheets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--all", action="store_true", help="sheet all clean frames")
    ap.add_argument("--files", nargs="*", help="explicit file list to sheet")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--rows", type=int, default=5)
    ap.add_argument("--thumb", type=int, default=320)
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    rows = load_rows(folder)

    if args.files:
        wanted = set(args.files)
        picks = [r for r in rows if r["file"] in wanted]
    elif args.all:
        picks = [r for r in rows if not r["flags"]]
    else:
        picks = shortlist(rows)

    if not picks:
        sys.exit("Nothing to sheet.")
    sheets = build(folder, picks, args.cols, args.rows, args.thumb)
    print(f"{len(picks)} frames -> {len(sheets)} contact sheet(s):")
    for s in sheets:
        print(f"  {s}")


if __name__ == "__main__":
    main()
