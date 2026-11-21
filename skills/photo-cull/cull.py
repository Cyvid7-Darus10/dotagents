#!/usr/bin/env python3
"""
photo-cull: objective first-pass culling of a folder of camera RAW files.

Pipeline:
  1. Use macOS `sips` to extract a downscaled JPEG preview from each RAW
     (Sony .ARW and friends are read natively, no extra deps).
  2. Score each preview with OpenCV/NumPy:
       - sharpness   : variance of the Laplacian (center-weighted)
       - exposure    : mean brightness + shadow/highlight clipping %
  3. Group consecutive frames into "bursts" (near-duplicates) by filename
     sequence number, so Claude can later pick the best frame per burst.
  4. Emit metrics.csv + a human-readable summary. Flags blurry / over- /
     under-exposed frames. Does NOT delete or move anything.

Usage:
    python3 cull.py /path/to/shoot_folder [--max-dim 1024] [--workers N]
                                          [--skip-previews]

Originals are never modified. Previews go to <folder>/_previews/.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2
import numpy as np

RAW_EXTS = {".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2", ".orf", ".dng"}

# Thresholds (tuned for 1024px previews; adjust per shoot if needed).
BLUR_SHARPNESS = 60.0      # below this = likely soft/blurry
DARK_MEAN = 50.0           # mean luma below this = underexposed
BRIGHT_MEAN = 205.0        # mean luma above this = overexposed
CLIP_FRACTION = 0.10       # >10% of pixels clipped at an extreme = flagged
BURST_GAP = 3              # sequence-number gap that starts a new burst (fallback)
TIME_GAP = 8.0             # seconds between captures that starts a new burst


def find_raws(folder):
    out = []
    for name in sorted(os.listdir(folder)):
        if os.path.splitext(name)[1].lower() in RAW_EXTS:
            out.append(name)
    return out


def preview_path(previews_dir, raw_name):
    base = os.path.splitext(raw_name)[0]
    return os.path.join(previews_dir, base + ".jpg")


def make_preview(args):
    raw_path, out_path, max_dim = args
    if os.path.exists(out_path):
        return out_path, None
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", str(max_dim),
             raw_path, "--out", out_path],
            check=True, capture_output=True, text=True,
        )
        return out_path, None
    except subprocess.CalledProcessError as e:
        return out_path, (e.stderr or str(e)).strip()


def score_preview(jpg_path):
    """Return dict of quality metrics for one preview JPEG."""
    img = cv2.imread(jpg_path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Center-weighted sharpness: the subject is usually near the middle, so a
    # blurred background shouldn't tank the score and a soft subject shouldn't
    # be rescued by a crisp background.
    cy0, cy1 = int(h * 0.2), int(h * 0.8)
    cx0, cx1 = int(w * 0.2), int(w * 0.8)
    center = gray[cy0:cy1, cx0:cx1]
    sharp_full = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp_center = float(cv2.Laplacian(center, cv2.CV_64F).var())
    sharpness = max(sharp_full, sharp_center)

    mean = float(gray.mean())
    total = gray.size
    shadow_clip = float((gray <= 5).sum()) / total
    highlight_clip = float((gray >= 250).sum()) / total

    flags = []
    if sharpness < BLUR_SHARPNESS:
        flags.append("blurry")
    if mean < DARK_MEAN:
        flags.append("underexposed")
    if mean > BRIGHT_MEAN:
        flags.append("overexposed")
    if shadow_clip > CLIP_FRACTION:
        flags.append("crushed-shadows")
    if highlight_clip > CLIP_FRACTION:
        flags.append("blown-highlights")

    return {
        "sharpness": round(sharpness, 1),
        "mean": round(mean, 1),
        "shadow_clip_pct": round(shadow_clip * 100, 1),
        "highlight_clip_pct": round(highlight_clip * 100, 1),
        "flags": flags,
    }


def seq_number(name):
    m = re.search(r"(\d+)", os.path.splitext(name)[0])
    return int(m.group(1)) if m else None


def capture_time(raw_path):
    """Capture timestamp (epoch seconds) from the RAW's metadata via sips."""
    try:
        out = subprocess.run(["sips", "-g", "creation", raw_path],
                             check=True, capture_output=True, text=True).stdout
        m = re.search(r"creation:\s*([\d: ]+)", out)
        if not m:
            return None
        return datetime.strptime(m.group(1).strip(), "%Y:%m:%d %H:%M:%S").timestamp()
    except (subprocess.CalledProcessError, ValueError):
        return None


def assign_bursts(rows):
    """Group consecutive frames into bursts.

    Prefer capture-time gaps (a new scene/burst starts after a pause of
    >TIME_GAP seconds). Fall back to sequence-number gaps when timestamps are
    missing — useful for shoots numbered contiguously across the whole day.
    """
    burst = 0
    prev_t = None
    prev_n = None
    for i, r in enumerate(rows):
        t, n = r.get("time"), r["seq"]
        if i > 0:
            new = False
            if t is not None and prev_t is not None:
                new = (t - prev_t) > TIME_GAP
            elif n is not None and prev_n is not None:
                new = (n - prev_n) > BURST_GAP
            if new:
                burst += 1
        r["burst"] = burst
        if t is not None:
            prev_t = t
        if n is not None:
            prev_n = n
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--max-dim", type=int, default=1024,
                    help="longest edge of generated previews (px)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--skip-previews", action="store_true",
                    help="reuse existing _previews/ instead of regenerating")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"Not a folder: {folder}")

    raws = find_raws(folder)
    if not raws:
        sys.exit(f"No RAW files found in {folder}")

    previews_dir = os.path.join(folder, "_previews")
    os.makedirs(previews_dir, exist_ok=True)
    print(f"Found {len(raws)} RAW files in {os.path.basename(folder)}")

    # 1. Previews -------------------------------------------------------------
    if not args.skip_previews:
        jobs = [(os.path.join(folder, r), preview_path(previews_dir, r),
                 args.max_dim) for r in raws]
        done = 0
        errs = 0
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for out_path, err in ex.map(make_preview, jobs):
                done += 1
                if err:
                    errs += 1
                    print(f"  ! preview failed: {os.path.basename(out_path)}: {err}")
                if done % 50 == 0 or done == len(jobs):
                    print(f"  previews: {done}/{len(jobs)}")
        if errs:
            print(f"  {errs} preview(s) failed")

    # 2. Capture times (for burst grouping) -----------------------------------
    print("  reading capture times...")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        times = list(ex.map(capture_time,
                            [os.path.join(folder, r) for r in raws]))
    time_by_file = dict(zip(raws, times))

    # 3. Score ----------------------------------------------------------------
    rows = []
    for r in raws:
        jpg = preview_path(previews_dir, r)
        m = score_preview(jpg) if os.path.exists(jpg) else None
        if m is None:
            rows.append({"file": r, "seq": seq_number(r),
                         "time": time_by_file.get(r), "preview": "",
                         "sharpness": 0.0, "mean": 0.0, "shadow_clip_pct": 0.0,
                         "highlight_clip_pct": 0.0, "flags": ["no-preview"]})
            continue
        rows.append({"file": r, "seq": seq_number(r),
                     "time": time_by_file.get(r),
                     "preview": os.path.relpath(jpg, folder), **m})

    rows.sort(key=lambda x: (x["time"] is None, x["time"] or 0,
                             x["seq"] or 0, x["file"]))
    assign_bursts(rows)

    # 4. Write metrics.csv ----------------------------------------------------
    csv_path = os.path.join(folder, "metrics.csv")
    with open(csv_path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["file", "burst", "sharpness", "mean", "shadow_clip_pct",
                     "highlight_clip_pct", "flags", "preview"])
        for r in rows:
            wr.writerow([r["file"], r["burst"], r["sharpness"], r["mean"],
                         r["shadow_clip_pct"], r["highlight_clip_pct"],
                         ";".join(r["flags"]), r["preview"]])

    # 5. Summary --------------------------------------------------------------
    clean = [r for r in rows if not r["flags"]]
    flagged = [r for r in rows if r["flags"]]
    n_bursts = (rows[-1]["burst"] + 1) if rows else 0

    # Best (sharpest, unflagged) frame per burst — the natural shortlist.
    by_burst = {}
    for r in rows:
        if r["flags"]:
            continue
        b = r["burst"]
        if b not in by_burst or r["sharpness"] > by_burst[b]["sharpness"]:
            by_burst[b] = r
    picks = sorted(by_burst.values(), key=lambda x: x["seq"] or 0)

    print("\n" + "=" * 60)
    print(f"  Total frames     : {len(rows)}")
    print(f"  Bursts (groups)  : {n_bursts}")
    print(f"  Clean (no flags) : {len(clean)}")
    print(f"  Flagged          : {len(flagged)}")
    print(f"  Shortlist        : {len(picks)} (sharpest clean frame per burst)")
    print("=" * 60)
    print(f"\nmetrics.csv written to: {csv_path}")

    print("\nShortlist — sharpest clean frame in each burst:")
    for r in picks:
        print(f"  burst {r['burst']:>3}  {r['file']:<18} "
              f"sharp={r['sharpness']:<8} mean={r['mean']}")

    if flagged:
        print(f"\nFlagged frames ({len(flagged)}):")
        for r in flagged[:40]:
            print(f"  {r['file']:<18} {','.join(r['flags'])}")
        if len(flagged) > 40:
            print(f"  ... and {len(flagged) - 40} more (see metrics.csv)")


if __name__ == "__main__":
    main()
