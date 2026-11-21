#!/usr/bin/env python3
"""WCAG contrast measurement from real screenshots (no dependencies).

Samples a background pixel and scans a text box for the glyph's PEAK pixel
(antialiasing means most text pixels are blends — the core color is the
extreme), then reports the WCAG 2.x contrast ratio.

Usage:
  contrast.py shot.png --bg X,Y --box X0,Y0,X1,Y1
  contrast.py shot.png --bg 700,720 --box 370,615,720,690

Coordinates are PIXELS in the PNG (a 3x device screenshot is 3px per point).
AA thresholds: 4.5:1 normal text, 3.0:1 large text (>=18pt regular / 14pt bold).
"""
import argparse
import struct
import sys
import zlib


def read_png(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, w, h, ct, idat = 8, 0, 0, 0, b""
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        if typ == b"IHDR":
            w, h, _, ct = struct.unpack(">IIBB", d[pos + 8:pos + 18])[:4]
        elif typ == b"IDAT":
            idat += d[pos + 8:pos + 8 + ln]
        elif typ == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(idat)
    ch = 4 if ct == 6 else 3
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, out


def px(w, ch, buf, x, y):
    i = (y * w + x) * ch
    return buf[i], buf[i + 1], buf[i + 2]


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(c1, c2):
    l1, l2 = sorted((lum(c1), lum(c2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--bg", required=True, help="background sample pixel: X,Y")
    ap.add_argument("--box", required=True, help="text scan box: X0,Y0,X1,Y1")
    a = ap.parse_args()
    w, h, ch, buf = read_png(a.png)
    bx, by = map(int, a.bg.split(","))
    x0, y0, x1, y1 = map(int, a.box.split(","))
    bg = px(w, ch, buf, bx, by)
    best = bg
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            c = px(w, ch, buf, x, y)
            if ratio(c, bg) > ratio(best, bg):
                best = c
    r = ratio(best, bg)
    verdict = "PASS AA" if r >= 4.5 else ("PASS AA-large only" if r >= 3.0 else "FAIL")
    print(f"bg rgb{bg}  text-peak rgb{best}  ratio {r:.2f}:1  {verdict}")
    sys.exit(0 if r >= 3.0 else 1)


if __name__ == "__main__":
    main()
