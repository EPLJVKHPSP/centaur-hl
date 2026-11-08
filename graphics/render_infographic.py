#!/usr/bin/env python3
"""Render the 1600x900 Centaur research graphic from audited results.json.

Brand assets:
- Original transparent Centaur logo from https://www.centaur.io/
  (_next/static/immutable/media/centaur-logo-with-rectangle.341wr0kli1imq.png)
- Inter and Geist Mono, the font families specified in Centaur's live stylesheet.
  The site's immutable font subsets are cached in the OS temp directory and are
  never placed in the project/output. Requires Pillow and internet on first run.

The graphic is a descriptive historical comparison; it makes no live-trading claim.
"""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import tempfile
import urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent
OUT = ASSETS / "dip_signal_infographic.png"
DATA = json.loads((ROOT / "results.json").read_text())
EARLIER = DATA["results"]["earlier"]["3_matched_peers"]
LATER = DATA["results"]["recent"]["3_matched_peers"]
assert (EARLIER["n"], LATER["n"]) == (97, 17), "Review changed sample sizes"
assert (round(EARLIER["mean_net_signal_pct"], 3), round(EARLIER["mean_net_peer_pct"], 3), round(EARLIER["mean_excess_pp"], 3)) == (1.515, .535, .980)
assert (round(LATER["mean_net_signal_pct"], 3), round(LATER["mean_net_peer_pct"], 3), round(LATER["mean_excess_pp"], 3)) == (3.700, 1.006, 2.693)

FONT_LINKS = {
    "Inter": "https://www.centaur.io/_next/static/immutable/media/83afe278b6a6bb3c-s.p.45535valc9rzk.woff2",
    "Geist Mono": "https://www.centaur.io/_next/static/immutable/media/797e433ab948586e-s.p.1v5bejj26fx9h.woff2",
}
FONT_DIR = Path(tempfile.gettempdir()) / "centaur_graphic_font_cache"
FONT_DIR.mkdir(parents=True, exist_ok=True)
FONTS = {}
for family, url in FONT_LINKS.items():
    target = FONT_DIR / ("inter-latin.woff2" if family == "Inter" else "geistmono-latin.woff2")
    if not target.exists():
        try:
            urllib.request.urlretrieve(url, target)
        except Exception as exc:
            raise RuntimeError("Can't access Centaur's official typefaces for exact brand rendering") from exc
    FONTS[family] = target

SCALE = 2
WIDTH, HEIGHT = 1600, 900
C = {
    "background": "#070708",
    "panel": "#121315",
    "panel_border": "#292B2F",
    "divider": "#2B2D33",
    "grid": "#292C30",
    "white": "#F6F7F8",
    "secondary": "#B4B6BD",
    "muted": "#888B93",
    "mint": "#68E2A4",
    "mint_bright": "#77E7B0",
    "peer": "#81848D",
    "amber": "#E2C28C",
}
canvas = Image.new("RGB", (WIDTH*SCALE, HEIGHT*SCALE), C["background"])
d = ImageDraw.Draw(canvas)
_FONT_CACHE = {}
_TEXT_BOUNDS = []

def color(key): return C.get(key, key)

def font(size: float, weight: int=400, mono: bool=False):
    key = (size, weight, mono)
    if key not in _FONT_CACHE:
        f = ImageFont.truetype(str(FONTS["Geist Mono" if mono else "Inter"]), round(size*SCALE))
        f.set_variation_by_axes([weight])
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]

def txt(x: float, y: float, value: str, size: float, ink="white", weight=400, mono=False, align="left"):
    anchor = {"left": "lt", "right": "rt", "center": "mt"}[align]
    xy = (round(x*SCALE), round(y*SCALE))
    face = font(size,weight,mono)
    bounds = d.textbbox(xy, value, font=face, anchor=anchor)
    assert bounds[0] >= (80-2)*SCALE and bounds[2] <= (1520+2)*SCALE, (value, "outside horizontal safe area", bounds)
    assert bounds[1] >= 24*SCALE and bounds[3] <= 880*SCALE, (value, "outside vertical safe area", bounds)
    _TEXT_BOUNDS.append((value, bounds))
    d.text(xy, value, fill=color(ink), font=face, anchor=anchor)

def txtlen(value: str, size: float, weight=400, mono=False):
    return font(size,weight,mono).getlength(value) / SCALE

def pct(value: float) -> str:
    # Display .005 ties consistently (e.g. 1.515 → 1.52), as in the assignment brief.
    return f"{Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"

def rectangle(box, ink, radius=0, stroke=None, sw=1):
    coords=tuple(round(v*SCALE) for v in box)
    d.rounded_rectangle(coords, round(radius*SCALE), fill=color(ink), outline=color(stroke) if stroke else None, width=round(sw*SCALE))

def stroke(x1,y1,x2,y2,ink="divider",width=1):
    d.line((round(x1*SCALE),round(y1*SCALE),round(x2*SCALE),round(y2*SCALE)),fill=color(ink),width=round(width*SCALE))

# Brand and editorial header; use the actual corporate PNG wordmark and mark.
logo=Image.open(ASSETS / "centaur_official_logo.png").convert("RGBA")
logo_w=232
logo=logo.resize((round(logo_w*SCALE),round(logo_w*logo.height/logo.width*SCALE)), Image.Resampling.LANCZOS)
canvas.paste(logo, (80*SCALE, 31*SCALE), logo)
txt(1518,61,"CENTAUR  /  RESEARCH",17,"secondary",500,True,"right")
stroke(80,121,1520,121,"divider",1)

headline="Can trader LONG calls beat the dip?"
assert txtlen(headline, 67, 660) < 1440, "Headline overflow"
txt(80,151,headline,67,"white",660)
txt(80,238,"114 historical signals · simulated 24h returns",28,"secondary",400)

# Minimal three-step strip: the copy is legible at mobile-preview scale.
steps = [
    (80, "01", "Public LONG", ["First from this trader for this coin", "in 7 days"]),
    (565, "02", "Coin is down", ["Price fell over the previous 24h"]),
    (1047, "03", "Trade for 24h", ["Enter next hourly open;", "exit 24h later"]),
]
for x, number, title, lines in steps:
    txt(x, 313, number, 24, "mint",600,True)
    txt(x+60, 308, title, 27, "white",600)
    for i, line in enumerate(lines):
        txt(x+60, 348+i*25, line, 19, "secondary",400)
stroke(536,306,536,390,"divider")
stroke(1018,306,1018,390,"divider")

# Exactly one explanatory chart, with a common visible zero and a 0-4% scale.
rectangle((80,415,1520,761),"panel",radius=18,stroke="panel_border",sw=1)
txt(107,440,"Average 24h return, after assumed costs",27,"white",600)
txt(1492,453,"0–4% scale",16,"muted",500,True,"right")

x0, bar_width=649, 570
chart_y_top, chart_y_bottom=499,726
for tick in range(5):
    x=x0+bar_width*(tick/4)
    stroke(x,chart_y_top,x,chart_y_bottom,"divider" if tick==0 else "grid",1.2 if tick==0 else 1)
    txt(x,481,f"{tick}%",15,"muted",400,True,"center")

# Period/series labels are written into the chart, eliminating a tiny legend.
# Bar fill width is exactly value / 4 * 570 px, including a visible zero baseline.
def pair(y, period, n, row):
    signal=row["mean_net_signal_pct"]
    peer=row["mean_net_peer_pct"]
    diff=row["mean_excess_pp"]
    txt(107,y-7,period,21,"white",600)
    txt(107,y+21,f"{n} signals",18,"muted",400)
    for off,label,value,paint in (
        (0,"Public LONG",signal,"mint"),
        (45,"Other coins after similar dips",peer,"peer"),
    ):
        yy=y+off
        txt(344,yy-2,label,19,"white" if off==0 else "secondary",550 if off==0 else 400)
        length=bar_width*value/4
        assert value>=0 and 0<=length<=bar_width
        rectangle((x0,yy+1,x0+length,yy+25),paint,radius=5)
        end_label=f"+{pct(value)}%"
        assert x0+length+13+txtlen(end_label,21,650)<1343, (period,label,'bar collides with difference column')
        txt(x0+length+13,yy, end_label,21,"white",650)
    # Keep a full 28px inset from the panel right edge, with space after the divider.
    stroke(1325,y-10,1325,y+67,"divider")
    txt(1492,y-7,f"+{pct(diff)} pp",31,"mint",650,align="right")
    txt(1492,y+31,"vs peers",17,"muted",400,align="right")

pair(525,"AUG 10 – OCT 24",97,EARLIER)
stroke(106,624,1493,624,"divider")
pair(652,"OCT 25 – NOV 6",17,LATER)

# Cautious takeaway and readable source line; claims stay within the evidence.
rectangle((80,795,89,804),"mint",radius=2)
txt(109,780,"Higher average returns in both tested windows — but not a proven trading edge.",24,"white",560)
source_lines = [
    "Source: Centaur-derived public LONG calls + Binance spot hourly prices.",
    "Simulated; 0.30 pp round-trip cost assumed. Both windows used in strategy selection; no live fills.",
]
source_size=18
assert all(txtlen(line,source_size,400)<1440 for line in source_lines)
for i, line in enumerate(source_lines):
    txt(80,829+i*26,line,source_size,"muted",400)

# Text should remain inside its safe area and never collide with another label.
# Check the real font-rendered glyph rectangles, rather than estimated string widths.
for i, (label_a, a) in enumerate(_TEXT_BOUNDS):
    for label_b, b in _TEXT_BOUNDS[i+1:]:
        if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
            raise AssertionError(f"Text collision: {label_a!r} and {label_b!r}")

canvas.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS).save(OUT,optimize=True)
print(f"Exported {OUT} at {WIDTH}x{HEIGHT}")
print(f"Data: earlier={EARLIER['n']} later={LATER['n']} signals; bars scaled 0–4%")
