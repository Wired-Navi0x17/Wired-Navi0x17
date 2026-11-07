#!/usr/bin/env python3
"""
Profile generator for github.com/Wired-Navi0x17.

Renders every card in assets/*.svg from status.yml plus live GitHub data, and
rewrites the pinned-repository block in README.md.

Standard library only, so it runs the same on NixOS and in GitHub Actions.

    python build.py                 # render everything
    python build.py --sync-system   # read this machine (fastfetch) into status.yml, then render
    python build.py --offline       # render without touching the network
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
PINNED_DIR = ASSETS / "pinned"
STATUS = ROOT / "status.yml"
README = ROOT / "README.md"
USER = "Wired-Navi0x17"
OFFLINE = "--offline" in sys.argv

# Palette: Tokyo Ghoul manga. Ink black, off-white paper, one blood red.
# Greys are kept bright enough to read on a phone. Nixie orange-red is only for
# the Steins;Gate meter.
C = {
    "ink": "#0b0b0b",
    "panel": "#141414",
    "line": "#363636",
    "red": "#c8102e",        # strokes, fills, highlights
    "red_hi": "#f0384b",     # red text (brighter for legibility)
    "red_dk": "#5c0a14",
    "paper": "#f4f2ed",
    "text": "#dcdad5",
    "muted": "#aaa8a3",
    "dim": "#7c7a75",
    "nixie": "#ff5f2e",
    "nixie_core": "#ffd8c8",
}

# Made in Abyss layer names double as section depths. Lain calls its episodes
# "Layer:01" and so on, so one label carries both shows.
LAYERS = [
    ("0 M", "EDGE OF THE ABYSS"),
    ("1,350 M", "FOREST OF TEMPTATION"),
    ("2,600 M", "GREAT FAULT"),
    ("7,000 M", "THE GOBLETS OF GIANTS"),
    ("12,000 M", "SEA OF CORPSES"),
    ("13,000 M", "CAPITAL OF THE UNRETURNED"),
    ("?????", "FINAL MAELSTROM"),
]

SECTIONS = [
    ("Surface signal", "ABOUT"),
    ("Pinned transmissions", "PINNED REPOSITORIES"),
    ("Instruments", "TOOLKIT"),
    ("The machine", "SYSTEM"),
    ("Signal log", "ACTIVITY"),
    ("Open a channel", "CONTACT"),
]


# --------------------------------------------------------------------------- #
# status.yml: a small YAML subset (maps, lists of scalars, nesting, comments)
# --------------------------------------------------------------------------- #
def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse_yaml(text: str):
    rows = []
    for raw in text.splitlines():
        s = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith(("'", '"', "- '", '- "')) else raw.rstrip()
        if not s.strip() or s.strip().startswith("#"):
            continue
        rows.append((len(s) - len(s.lstrip(" ")), s.strip()))

    def block(i, indent):
        if i < len(rows) and rows[i][1].startswith("- "):
            out = []
            while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
                out.append(_scalar(rows[i][1][2:]))
                i += 1
            return out, i
        out = {}
        while i < len(rows) and rows[i][0] == indent:
            key, _, val = rows[i][1].partition(":")
            key = _scalar(key)
            i += 1
            if val.strip():
                out[key] = _scalar(val)
            elif i < len(rows) and rows[i][0] > indent:
                out[key], i = block(i, rows[i][0])
            else:
                out[key] = ""
        return out, i

    data, _ = block(0, 0) if rows else ({}, 0)
    return data


def load_status():
    return parse_yaml(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
# Glyphs that exist in the embedded font subsets. Anything else (emoji, kaomoji,
# box drawing) is stripped so nothing renders as tofu and the profile stays
# emoji-free even when a repo description contains one.
_ALLOWED = set(chr(c) for c in range(0x20, 0x7F)) | set(chr(c) for c in range(0xA0, 0x100)) | set(
    "–—‘’“”•…·→←"
)


def clean(s) -> str:
    s = "" if s is None else str(s)
    s = html.unescape(s)
    s = "".join(ch if ch in _ALLOWED else " " for ch in s)
    return re.sub(r"\s+", " ", s).strip(" -–—|·")


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def wrap(s: str, width: int, max_lines: int | None = None):
    lines = textwrap.wrap(s, width=width, break_long_words=True) or [""]
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = (last[: width - 1].rstrip(" ,.;:") + "…") if len(last) >= width - 1 else last.rstrip(" ,.;:") + "…"
    return lines


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip(" ,.;:") + "…"


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


FONTS = {
    "Bebas": "BebasNeue-Regular.woff",
    "Plex": "IBMPlexMono-Regular.woff",
    "Playfair": "PlayfairDisplay-Italic.woff",
    "Cutive": "CutiveMono-Regular.woff",
}
_FONT_CACHE: dict[str, str] = {}


def font_css(names):
    out = []
    for n in names:
        if n not in _FONT_CACHE:
            _FONT_CACHE[n] = b64(ASSETS / "fonts" / FONTS[n], "font/woff")
        style = "italic" if n == "Playfair" else "normal"
        out.append(f"@font-face{{font-family:'{n}';font-style:{style};src:url({_FONT_CACHE[n]}) format('woff');}}")
    return "".join(out)


BASE_CSS = f"""
.bebas{{font-family:'Bebas','Bebas Neue',Impact,sans-serif;}}
.plex{{font-family:'Plex','IBM Plex Mono',ui-monospace,Menlo,monospace;}}
.play{{font-family:'Playfair','Playfair Display',Georgia,serif;font-style:italic;}}
.cut{{font-family:'Cutive','Cutive Mono','Courier New',monospace;}}
"""

GRAIN = """<filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>
<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0"/></filter>"""


def svg_doc(w, h, body, fonts=("Bebas", "Plex"), defs="", title="", css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<style>{font_css(fonts)}{BASE_CSS}{css}</style>
<defs>{GRAIN}{defs}</defs>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="8" fill="{C['ink']}" stroke="{C['line']}"/>
{body}
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="8" filter="url(#grain)" opacity=".045" pointer-events="none"/>
</svg>
"""


def text(x, y, s, cls, size, fill, anchor="start", ls=0, extra=""):
    if cls == "plex":
        size = max(size, 8.5)
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{esc(s)}</text>')


def world_line(seed: str) -> str:
    """Deterministic 'divergence' for a string, styled like a Steins;Gate reading."""
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    return f"{(h % 2) + (h // 7 % 1000000) / 1e6:.6f}"


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# GitHub data
# --------------------------------------------------------------------------- #
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def http(url, data=None, accept="application/vnd.github+json"):
    headers = {"User-Agent": "wired-navi-profile-builder", "Accept": accept}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    out = json.loads(http("https://api.github.com/graphql", data=body))
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


GQL = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100){
      totalCount nodes{stargazerCount isFork}
    }
    contributionsCollection{contributionCalendar{totalContributions}}
    pinnedItems(first:6, types:REPOSITORY){nodes{... on Repository{
      name description url homepageUrl stargazerCount forkCount pushedAt isFork
      parent{nameWithOwner}
      repositoryTopics(first:6){nodes{topic{name}}}
      languages(first:5, orderBy:{field:SIZE, direction:DESC}){totalSize edges{size node{name}}}
      readme: object(expression:"HEAD:README.md"){... on Blob{text}}
    }}}
  }
}"""


_GENERIC = re.compile(r"^(about|overview|introduction|intro|features?|highlights|installation|install|usage|"
                      r"quick ?start|getting started|contents|table of contents|setup|requirements|license|demo|"
                      r"screenshots?|tech stack|contributing|credits|\d+\.\s.*)$", re.I)
_ABOUT = r"^((project |repository )?(about|overview|introduction|intro|description|summary)|(about|what is) {name}\??)$"


def _md_inline(s: str) -> str:
    s = re.sub(r"[*`]", "", s)
    s = re.sub(r"(?<!\w)_+|_+(?!\w)", "", s)   # _emphasis_ but not snake_case
    return clean(s)


def readme_summary(md: str, repo: str = ""):
    """Pull a tagline and a prose summary out of a repo README, in document order."""
    if not md:
        return "", None
    md = re.sub(r"```.*?```", "", md, flags=re.S)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", md)    # linked badges
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)                 # images / badges
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)             # links -> text
    md = re.sub(r"<[^>]+>", "", md)                               # html tags

    blocks: list[tuple[str, str]] = []   # (kind, text) kind in h1, h, p
    para: list[str] = []

    def flush():
        if para:
            blocks.append(("p", " ".join(para)))
            para.clear()

    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith(("---", "***", "|", "- [", "* [")):
            flush()
            continue
        if s.startswith("#"):
            flush()
            blocks.append(("h1" if re.match(r"#\s", s) else "h", _md_inline(s.lstrip("#"))))
            continue
        s = re.sub(r"^>\s*", "", s)
        if re.fullmatch(r"\*\*[^*]+\*\*:?", s) and not para:   # a bold line on its own is a headline
            blocks.append(("h", _md_inline(s)))
            continue
        para.append(s)
    flush()

    def usable(t):
        letters = sum(ch.isalpha() for ch in t)
        return letters >= 10 and "\u2190" not in t and "\u2192" not in t and not re.search(r"\s(•|/)\s.*\s(•|/)\s", t)   # skip nav rows

    name = repo.lower().replace("-", " ")
    tagline = ""
    for kind, t in blocks[:6]:
        t = _md_inline(t)
        if not usable(t) or _GENERIC.match(t) or t.lower().replace("-", " ") == name:
            continue
        if kind in ("h1", "h") and len(t) > 12:
            tagline = t
            break
        if kind == "p" and 15 <= len(t) <= 120 and not t.endswith(":"):
            tagline = t
            break

    about_re = re.compile(_ABOUT.format(name=re.escape(repo)), re.I)
    summary, from_about = "", False
    for idx, (kind, t) in enumerate(blocks):
        if kind != "p" and about_re.match(_md_inline(t)):
            for k2, t2 in blocks[idx + 1: idx + 4]:
                t2 = _md_inline(t2)
                if k2 == "p" and len(t2) >= 40 and usable(t2):
                    summary, from_about = t2, True
                    break
            if summary:
                break
    if not summary:
        for kind, t in blocks:
            t = _md_inline(t)
            if kind == "p" and len(t) >= 60 and t != tagline and usable(t):
                summary = t
                break
    return tagline, ((summary, from_about) if summary else None)


def scrape_pinned():
    page = http(f"https://github.com/{USER}", accept="text/html")
    names = re.findall(r'<span class="repo"[^>]*>\s*([^<\s]+)\s*<', page)
    return list(dict.fromkeys(names))[:6]


def fetch_github():
    stats = {"repos": None, "stars": None, "followers": None, "contributions": None}
    pinned = []
    if OFFLINE:
        return stats, None

    if TOKEN:
        try:
            u = gql(GQL, {"login": USER})["user"]
            repos = u["repositories"]["nodes"]
            stats.update(
                repos=u["repositories"]["totalCount"],
                stars=sum(r["stargazerCount"] for r in repos if not r["isFork"]),
                followers=u["followers"]["totalCount"],
                contributions=u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
            )
            for r in u["pinnedItems"]["nodes"]:
                total = r["languages"]["totalSize"] or 1
                pinned.append({
                    "name": r["name"], "url": r["url"], "description": r["description"],
                    "stars": r["stargazerCount"], "forks": r["forkCount"], "pushed": r["pushedAt"],
                    "fork_of": (r.get("parent") or {}).get("nameWithOwner"),
                    "topics": [t["topic"]["name"] for t in r["repositoryTopics"]["nodes"]],
                    "languages": [(e["node"]["name"], e["size"] / total) for e in r["languages"]["edges"]],
                    "readme": (r.get("readme") or {}).get("text", ""),
                })
            return stats, pinned
        except Exception as e:  # fall through to the REST/scrape path
            print(f"  GraphQL failed ({e}); falling back to REST", file=sys.stderr)

    # No token (local run) or GraphQL failure: REST + profile page scrape.
    try:
        user = json.loads(http(f"https://api.github.com/users/{USER}"))
        repos = json.loads(http(f"https://api.github.com/users/{USER}/repos?per_page=100"))
        stats.update(repos=user.get("public_repos"), followers=user.get("followers"),
                     stars=sum(r["stargazers_count"] for r in repos if not r["fork"]))
        m = re.search(r"([\d,]+)\s+contributions?\s+in the last year",
                      http(f"https://github.com/users/{USER}/contributions", accept="text/html"))
        if m:
            stats["contributions"] = int(m.group(1).replace(",", ""))
        by_name = {r["name"]: r for r in repos}
        for name in scrape_pinned():
            r = by_name.get(name) or json.loads(http(f"https://api.github.com/repos/{USER}/{name}"))
            langs = json.loads(http(r["languages_url"]))
            total = sum(langs.values()) or 1
            try:
                rd = http(f"https://api.github.com/repos/{USER}/{name}/readme", accept="application/vnd.github.raw")
            except urllib.error.HTTPError:
                rd = ""
            pinned.append({
                "name": name, "url": r["html_url"], "description": r.get("description"),
                "stars": r["stargazers_count"], "forks": r["forks_count"], "pushed": r["pushed_at"],
                "fork_of": None, "topics": r.get("topics", [])[:6],
                "languages": [(k, v / total) for k, v in list(langs.items())[:5]], "readme": rd,
            })
    except Exception as e:
        print(f"  GitHub fetch failed ({e}); keeping existing pinned cards", file=sys.stderr)
        return stats, None
    return stats, pinned


# --------------------------------------------------------------------------- #
# Cards
# --------------------------------------------------------------------------- #
def wires(w, y0=18, opacity=".5", signal=True):
    """Lain's power lines: sagging cables and one pulse travelling down the wire."""
    paths = []
    for i, (sag, off) in enumerate([(26, 0), (34, 9), (20, 17), (40, 24)]):
        y = y0 + off
        d = f"M-10 {y} Q {w*0.25} {y+sag} {w*0.5} {y+4} T {w+10} {y+2}"
        paths.append(f'<path id="wire{i}" d="{d}" fill="none" stroke="#3d3d3d" stroke-width="{1.2 - i*0.15:.2f}"/>')
    pulse = ""
    if signal:
        pulse = (f'<circle r="1.8" fill="{C["red_hi"]}"><animateMotion dur="9s" repeatCount="indefinite">'
                 f'<mpath xlink:href="#wire1"/></animateMotion>'
                 f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.85;1" dur="9s" repeatCount="indefinite"/></circle>')
    return f'<g opacity="{opacity}">{"".join(paths)}{pulse}</g>'


# --------------------------------------------------------------------------- #
# Made in Abyss: curse of ascent, whistle ranks, relic grades, the descent map
# --------------------------------------------------------------------------- #
CURSE = [
    "mild dizziness and nausea",
    "heavy nausea, headaches, numb limbs",
    "all of the above, plus hallucinations",
    "full-body pain, bleeding from every orifice",
    "loss of the senses, confusion, self-harm",
    "loss of humanity, or death",
    "certain death",
]
# (rank, contributions needed in the last 12 months, how deep it lets you go)
WHISTLES = [("Bell", 0, "training only"), ("Red", 50, "cleared to L1"), ("Blue", 200, "cleared to L2"),
            ("Moon", 600, "cleared to L3"), ("Black", 1500, "cleared to L5"), ("White", 4000, "no depth limit")]
WHISTLE_SHORT = ["TRAINING", "TO L1", "TO L2", "TO L3", "TO L5", "ANY DEPTH"]


def whistle_rank(contributions):
    rank = WHISTLES[0]
    for w in WHISTLES:
        if (contributions or 0) >= w[1]:
            rank = w
    return rank[0], rank[2]


def relic_grade(stars, forks):
    score = (stars or 0) + 2 * (forks or 0)
    for threshold, grade in [(20, "Special Grade"), (8, "1st Grade"), (3, "2nd Grade"), (1, "3rd Grade")]:
        if score >= threshold:
            return grade
    return "4th Grade"


def abyss_journey(st):
    """Seven (step, when, cost) rows from status.yml `abyss:`; falls back to the curse of ascent."""
    a = st.get("abyss", {}) or {}
    rows = []
    for i in range(7):
        e = a.get(f"L{i+1}", {}) or {}
        rows.append((clean(e.get("step")) or CURSE[i], clean(e.get("when")), clean(e.get("cost"))))
    try:
        here = min(7, max(1, int(a.get("here", 0))))
    except ValueError:
        here = 0
    return rows, here


def abyss_map(here=0):
    """The cross-section itself, drawn in a 1000-unit frame between x=30 and x=500."""
    tops = [96, 166, 256, 376, 466, 536, 606]
    bottom = 656
    cx = 265
    LW = [(96, 110), (120, 122), (140, 117), (166, 140), (190, 131), (214, 150), (236, 145), (256, 176), (300, 183),
          (340, 178), (376, 187), (392, 141), (420, 128), (466, 120), (480, 104), (510, 100), (536, 113), (552, 150),
          (580, 161), (606, 190), (630, 218), (656, 252)]
    RW = [(y, 2 * cx - x + ((y * 37) % 11) - 5) for y, x in LW]

    def pts(seq):
        return " ".join(f"{x},{y}" for y, x in seq)

    defs = f"""<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<line x1="0" y1="0" x2="0" y2="6" stroke="{C['paper']}" stroke-width=".7" opacity=".2"/></pattern>
<pattern id="tone" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="2.5" cy="2.5" r="1" fill="{C['paper']}" opacity=".35"/></pattern>
<linearGradient id="pit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#262626"/>
<stop offset=".45" stop-color="#0b0b0b"/><stop offset=".85" stop-color="#1a0508"/><stop offset="1" stop-color="{C['red_dk']}"/></linearGradient>
<radialGradient id="core" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{C['red_hi']}"/><stop offset="1" stop-color="{C['red']}" stop-opacity="0"/></radialGradient>"""
    b = []
    # Pit interior, then rock walls with manga hatching and an ink edge
    b.append(f'<polygon points="{pts(LW)} {pts(reversed(RW))}" fill="url(#pit)"/>')
    for wall in (f"30,{bottom} 30,96 {pts(LW)}", f"500,{bottom} 500,96 {pts(RW)}"):
        b.append(f'<polygon points="{wall}" fill="#1c1c1c"/>')
        b.append(f'<polygon points="{wall}" fill="url(#hatch)"/>')
    for seq in (LW, RW):
        b.append(f'<polyline points="{pts(seq)}" fill="none" stroke="{C["paper"]}" stroke-width="1.4" stroke-linejoin="round"/>')
    b.append(f'<line x1="30" y1="96" x2="110" y2="96" stroke="{C["paper"]}" stroke-width="1.4"/>')
    b.append(f'<line x1="{RW[0][1]}" y1="96" x2="500" y2="96" stroke="{C["paper"]}" stroke-width="1.4"/>')

    # Orth on the rim: houses, a tower, a lift gantry
    houses = [(36, 14), (48, 22), (62, 11), (74, 30), (88, 17), (98, 9), (430, 12), (442, 26), (456, 16), (470, 34), (484, 13)]
    for x, h in houses:
        b.append(f'<rect x="{x}" y="{96-h}" width="11" height="{h}" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".9"/>')
    b.append(f'<path d="M74 66 l5.5 -12 l5.5 12" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".9"/>')
    b.append(f'<path d="M470 62 l5.5 -10 l5.5 10" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".9"/>')
    b.append(text(cx, 58, "ORTH", "bebas", 18, C["paper"], "middle", ls=6))
    b.append(text(cx, 76, "THE TOWN ON THE RIM", "plex", 8.5, C["muted"], "middle", ls=2))
    b.append(f'<line x1="200" y1="96" x2="200" y2="150" stroke="{C["muted"]}" stroke-width=".8"/>')
    b.append(f'<rect x="196" y="120" width="8" height="7" fill="{C["paper"]}"><animate attributeName="y" values="104;142;104" dur="10s" repeatCount="indefinite"/></rect>')

    # L1 ledges
    for y, x0, x1 in [(130, 122, 146), (152, 118, 140)]:
        b.append(f'<path d="M{x0} {y}h{x1-x0}" stroke="{C["paper"]}" stroke-width="1"/>')
    # L2 Forest of Temptation, with the Inverted Forest hanging under an overhang
    for x in range(140, 182, 10):
        b.append(f'<path d="M{x} 196 l5 -14 l5 14z" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".8"/>')
    b.append(f'<path d="M148 216 L262 206 L268 213 L148 224z" fill="#1c1c1c" stroke="{C["paper"]}" stroke-width="1"/>')
    for x in range(160, 262, 13):
        b.append(f'<path d="M{x} 222 l5 16 l5 -16z" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".8"/>')
    # L3 Great Fault: caves in a sheer wall and a switchback trail
    for y, x in [(282, 186), (318, 190), (350, 184)]:
        b.append(f'<ellipse cx="{x}" cy="{y}" rx="4" ry="6" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".8"/>')
        b.append(f'<ellipse cx="{2*cx - x + 2}" cy="{y + 12}" rx="4" ry="6" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width=".8"/>')
    b.append(f'<polyline points="190,262 214,280 192,300 216,320 194,340 218,362" fill="none" stroke="{C["muted"]}" stroke-width=".8" stroke-dasharray="2 2"/>')
    # L4 Goblets of Giants: cup-shaped growths spilling water
    for gx, gy, r in [(196, 398, 24), (318, 392, 28), (258, 426, 20)]:
        b.append(f'<path d="M{gx-r} {gy} Q{gx} {gy + r*1.1} {gx+r} {gy}Z" fill="{C["ink"]}" stroke="{C["paper"]}" stroke-width="1.1"/>')
        b.append(f'<ellipse cx="{gx}" cy="{gy}" rx="{r}" ry="3.5" fill="#1c1c1c" stroke="{C["paper"]}" stroke-width="1.1"/>')
        b.append(f'<path d="M{gx} {gy + r*.55} V{gy + r + 14} M{gx-7} {gy + r + 14} H{gx+7}" stroke="{C["paper"]}" stroke-width="1.1"/>')
        for side in (-1, 1):
            x = gx + side * r
            b.append(f'<path d="M{x} {gy} q{side*3} 12 {side*2} 34" fill="none" stroke="{C["paper"]}" stroke-width=".9" '
                     f'stroke-dasharray="3 3" opacity=".8"><animate attributeName="stroke-dashoffset" values="0;-12" dur="1.2s" repeatCount="indefinite"/></path>')
    # L5 Sea of Corpses
    b.append(f'<rect x="100" y="490" width="330" height="46" fill="url(#tone)" opacity=".5"/>')
    for k, y in enumerate((490, 502, 514, 526)):
        d = "M100 {y} ".format(y=y) + " ".join(f"q 10 {-4 if j % 2 == 0 else 4} 20 0" for j in range(17))
        b.append(f'<path d="{d}" fill="none" stroke="{C["paper"]}" stroke-width="{1.1 - k*.2:.1f}" opacity="{.9 - k*.18:.2f}">'
                 f'<animateTransform attributeName="transform" type="translate" values="0 0;{6 if k % 2 else -6} 0;0 0" dur="{5+k}s" repeatCount="indefinite"/></path>')
    # L6 Capital of the Unreturned: a ruined skyline
    for x, h, broken in [(170, 26, 1), (184, 40, 0), (200, 18, 1), (214, 52, 1), (232, 30, 0), (300, 46, 1), (316, 22, 0), (330, 36, 1), (346, 16, 0)]:
        top = 600 - h
        d = f"M{x} 600 V{top + (6 if broken else 0)} l4 {-6 if broken else 0} l4 5 l4 -3 V600z"
        b.append(f'<path d="{d}" fill="#1c1c1c" stroke="{C["paper"]}" stroke-width=".8"/>')
    b.append(f'<path d="M248 600 a17 17 0 0 1 34 0z" fill="#1c1c1c" stroke="{C["paper"]}" stroke-width=".8"/>')
    # L7 Final Maelstrom and the bottom
    spiral = "M265 632 " + " ".join(f"a{r} {r} 0 0 1 {(-1)**k * 2 * r} 0" for k, r in enumerate([3, 6, 9, 12, 15, 18]))
    b.append(f'<g><path d="{spiral}" fill="none" stroke="{C["red_hi"]}" stroke-width="1.3"/>'
             f'<animateTransform attributeName="transform" type="rotate" values="0 265 632;-360 265 632" dur="14s" repeatCount="indefinite"/></g>')
    b.append(f'<circle cx="265" cy="652" r="8" fill="url(#core)"><animate attributeName="r" values="6;10;6" dur="3s" repeatCount="indefinite"/></circle>')
    b.append(text(cx, 680, "THE NETHERWORLD'S BOTTOM  ·  DEPTH UNKNOWN", "plex", 8.5, C["muted"], "middle", ls=2))

    # Layer boundaries and labels on the rock
    for i, y in enumerate(tops):
        if i:
            b.append(f'<line x1="30" y1="{y}" x2="500" y2="{y}" stroke="{C["red"]}" stroke-width=".8" stroke-dasharray="5 4" opacity=".75"/>')
        b.append(text(38, y + 16, f"L{i+1}", "bebas", 14, C["red_hi"], ls=1))

    # Descent route with a diver on it
    route = "M265 96 L232 130 L292 160 L242 200 L272 246 L256 300 L276 360 L240 410 L286 452 L250 492 L280 540 L255 590 L265 628"
    b.append(f'<path id="route" d="{route}" fill="none" stroke="{C["paper"]}" stroke-width="1" stroke-dasharray="1 4" opacity=".7"/>')
    b.append(f'<circle r="3.5" fill="{C["red_hi"]}" stroke="{C["ink"]}"><animateMotion dur="40s" repeatCount="indefinite"><mpath xlink:href="#route"/></animateMotion></circle>')


    if here:
        y = (tops[here - 1] + (tops[here] if here < 7 else bottom)) / 2
        b.append(f'<circle cx="{cx}" cy="{y}" r="5" fill="{C["red"]}" stroke="{C["paper"]}" stroke-width="1.2"/>')
        b.append(f'<circle cx="{cx}" cy="{y}" r="5" fill="none" stroke="{C["red_hi"]}" stroke-width="1.2">'
                 f'<animate attributeName="r" values="5;16" dur="2s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="1;0" dur="2s" repeatCount="indefinite"/></circle>')
        b.append(f'<rect x="{cx+14}" y="{y-9}" width="92" height="17" fill="{C["ink"]}" stroke="{C["red"]}"/>')
        b.append(text(cx + 60, y + 3.5, "YOU ARE HERE", "plex", 8.5, C["paper"], "middle", ls=1.5))
    return defs, b, tops


def abyss_card(st, stats, mobile=False):
    """An original cross-section of the Abyss; each layer is one step of Harshul's own descent."""
    rows, here = abyss_journey(st)
    defs, b, tops = abyss_map(here)
    contrib = stats.get("contributions")
    rank, cleared = whistle_rank(contrib)
    cur = [w[0] for w in WHISTLES].index(rank)
    title = ("The Abyss, a descent map of Harshul's path. " + "; ".join(
        f"Layer {i+1}, {LAYERS[i][1].title()}: {r[0]}" + (f" ({r[1]})" if r[1] else "") for i, r in enumerate(rows))
        + f". Whistle rank: {rank}.")
    if mobile:
        return abyss_mobile(rows, here, defs, b, tops, rank, cleared, cur, contrib, title)
    W, H = 1000, 800

    # Right side: the layer log
    b.append(text(540, 54, "HARSHUL'S DESCENT", "bebas", 32, C["paper"], ls=3))
    b.append(text(964, 46, "DESCENT MAP", "plex", 9, C["red_hi"], "end", ls=3))
    b.append(text(540, 74, "ONE LAYER PER STEP OF THE WAY DOWN", "plex", 8.5, C["muted"], ls=1))
    for i, (depth, layer) in enumerate(LAYERS):
        step, when, cost = rows[i]
        y0 = tops[i] + 22
        on = here == i + 1
        target = f"{i+1:02d} {SECTIONS[i][0].upper()}" if i < len(SECTIONS) else "END OF PAGE"
        b.append(f'<path d="M504 {y0-5}H532" stroke="{C["red"] if on else C["line"]}" stroke-dasharray="2 3"/>')
        b.append(text(540, y0, f"L{i+1}", "bebas", 20, C["red_hi"], ls=1))
        b.append(text(574, y0, layer, "bebas", 17, C["paper"], ls=2))
        b.append(text(964, y0, (when or depth).upper(), "plex", 9, C["red_hi"] if on else C["muted"], "end", ls=1))
        b.append(text(574, y0 + 17, clip(step, 62), "plex", 10.5, C["paper"] if on else C["text"]))
        if cost:
            b.append(f'<text x="574" y="{y0+33}" class="plex" font-size="9"><tspan fill="{C["dim"]}">COST  </tspan>'
                     f'<tspan fill="{C["muted"]}">{esc(clip(cost, 44))}</tspan></text>')
        b.append(text(964, y0 + 33, f"→ {target}", "plex", 8.5, C["red_hi"], "end", ls=1))

    # Whistle ranks
    b.append(f'<line x1="36" y1="700" x2="964" y2="700" stroke="{C["line"]}"/>')
    b.append(text(36, 728, "WHISTLE RANK", "plex", 9, C["red_hi"], ls=3))
    b.append(text(36, 752, f"{rank} whistle, {cleared}.", "play", 17, C["paper"]))
    b.append(text(36, 774, f"Earned from {contrib if contrib is not None else 'unknown'} contributions in 12 months.",
                  "plex", 9, C["muted"]))
    for k, (name, need, depth_ok) in enumerate(WHISTLES):
        x = 404 + k * 94
        on = k == cur
        col = C["red"] if on else (C["paper"] if k < cur else C["dim"])
        fill = C["red"] if on else "none"
        b.append(f'<circle cx="{x+5}" cy="733" r="5" fill="none" stroke="{col}" stroke-width="1.4"/>')
        b.append(f'<rect x="{x+10}" y="728" width="44" height="10" rx="5" fill="{fill}" stroke="{col}" stroke-width="1.4"/>')
        b.append(f'<rect x="{x+46}" y="725" width="6" height="3" fill="{col}"/>')
        b.append(text(x, 760, name.upper(), "bebas", 15, C["paper"] if k <= cur else C["dim"], ls=2))
        b.append(text(x, 776, f"{need}+", "plex", 8.5, C["muted"] if k <= cur else C["dim"]))
        b.append(text(x + 38, 776, WHISTLE_SHORT[k], "plex", 8.5, C["muted"] if k <= cur else C["dim"]))

    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex", "Playfair"), defs, title)


def hero(st, stats, today):
    W, H = 1000, 560
    p = st.get("profile", {})
    sysd = st.get("system", {})
    img = ASSETS / "img"

    duo = f"""<filter id="duo" color-interpolation-filters="sRGB">
<feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .07 .72 .9"/><feFuncG type="table" tableValues=".04 .07 .71 .89"/>
<feFuncB type="table" tableValues=".04 .07 .69 .87"/></feComponentTransfer></filter>
<filter id="duo2" color-interpolation-filters="sRGB">
<feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .1 .8 .93"/><feFuncG type="table" tableValues=".04 .1 .79 .92"/>
<feFuncB type="table" tableValues=".04 .1 .77 .9"/></feComponentTransfer></filter>
<filter id="duored" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .78"/><feFuncG type="table" tableValues=".04 .06"/>
<feFuncB type="table" tableValues=".04 .18"/></feComponentTransfer></filter>
<pattern id="tone" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="2.5" cy="2.5" r="1.05" fill="#f4f2ed"/></pattern>
<radialGradient id="toneFade" cx="1" cy="0" r="1"><stop offset="0" stop-color="#fff"/><stop offset=".7" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="toneMask"><rect width="1000" height="560" fill="url(#toneFade)"/></mask>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/>
<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="pulse" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="0">
<animate attributeName="stdDeviation" values="0;1.3;0" dur="3s" repeatCount="indefinite"/></feGaussianBlur></filter>
<filter id="shadow" x="-20%" y="-20%" width="150%" height="160%"><feDropShadow dx="8" dy="8" stdDeviation="3" flood-color="#000" flood-opacity=".62"/></filter>
<clipPath id="pclip"><polygon points="372,24 644,24 628,536 356,536"/></clipPath>
<linearGradient id="fadeB" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stop-color="{C['ink']}" stop-opacity="0"/>
<stop offset="1" stop-color="{C['ink']}" stop-opacity=".95"/></linearGradient>
<linearGradient id="fadeT" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C['ink']}" stop-opacity=".85"/>
<stop offset=".22" stop-color="{C['ink']}" stop-opacity="0"/></linearGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".55"/></pattern>
<pattern id="strip" width="26" height="133" patternUnits="userSpaceOnUse">
<image width="26" height="133" xlink:href="{b64(img / 'strip.png', 'image/png')}" preserveAspectRatio="none"/></pattern>
"""
    body = [wires(W, 14, ".55")]

    # Film strip, left edge
    body.append(f'<rect x="14" y="14" width="26" height="{H-28}" fill="url(#strip)" filter="url(#duored)" opacity=".55"/>')
    body.append(f'<line x1="46" y1="14" x2="46" y2="{H-14}" stroke="{C["line"]}"/>')

    # Telephone pole, top right
    body.append(f'<g stroke="#3d3d3d" stroke-width="2" opacity=".55"><line x1="858" y1="6" x2="858" y2="210"/>'
                f'<line x1="836" y1="22" x2="880" y2="22"/><line x1="842" y1="34" x2="874" y2="34"/></g>')

    # ---- Left column -------------------------------------------------------
    L = 66
    # screentone in the top-right corner, manga style
    body.append(f'<rect width="{W}" height="{H}" fill="url(#tone)" mask="url(#toneMask)" opacity=".16"/>')
    first, _, rest = clean(p.get("name", "")).partition("|")
    name_w = 0.42 * 40 * len(clean(p.get("name", "")))
    fit = ' textLength="272" lengthAdjust="spacingAndGlyphs"' if name_w > 272 else ""
    body += [
        text(L, 56, f"@{p.get('handle', USER).upper()}  //  LAYER:01 WEIRD", "plex", 9, C["muted"], ls=2),
        f'<text x="{L}" y="100" class="bebas" font-size="40" letter-spacing="1"{fit}>'
        f'<tspan fill="{C["paper"]}">{esc(first.strip().upper())}</tspan>'
        + (f'<tspan fill="{C["red_hi"]}"> | {esc(rest.strip().upper())}</tspan>' if rest else "") + "</text>",
        text(L, 122, clean(p.get("tagline", "")).upper(), "plex", 9.5, C["text"], ls=2),
    ]
    for i, lab in enumerate(["PROFILE", "NODE", "SIGNAL"]):
        x = L + 6 + i * 84
        fill = C["red"] if i == 0 else "none"
        body.append(f'<circle cx="{x}" cy="146" r="4.5" fill="{fill}" stroke="{C["red"]}"/>')
        body.append(text(x + 11, 149, lab, "plex", 8, C["muted"] if i else C["text"], ls=2))

    bx, by, bw, bh = 64, 170, 262, 334
    body.append(f'<rect x="{bx-6}" y="{by-6}" width="{bw+12}" height="{bh+12}" fill="none" stroke="{C["red"]}"/>')
    body.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{C["panel"]}" stroke="{C["paper"]}" stroke-width="2.5" filter="url(#shadow)"/>')
    cx = bx + bw / 2
    body += [
        text(cx, by + 38, p.get("alias", "Navi"), "play", 24, C["paper"], "middle"),
        f'<text x="{cx}" y="{by+56}" class="plex" font-size="8" text-anchor="middle" letter-spacing="2">'
        f'<tspan fill="{C["red"]}">• •</tspan><tspan fill="{C["muted"]}"> {esc(clean(p.get("motto", "a node in the wired")).upper())}</tspan></text>',
    ]
    os_short = clean(sysd.get("os", "Linux")).split(" ")[0]
    de_short = re.sub(r"\s*[\d.]+.*$", "", clean(sysd.get("desktop", "")))
    sh_short = clean(sysd.get("shell", "")).split(" ")[0]
    stack = " · ".join(x for x in [os_short, de_short, sh_short] if x).upper()
    body.append(text(cx, by + 76, stack, "plex", 8.5, C["text"], "middle", ls=2))
    body.append(text(cx, by + 92, clean(p.get("school_line", "")).upper(), "bebas", 13, C["red_hi"], "middle", ls=3))

    sw, sh, sk = 84, 86, 21
    sx0 = cx - (sw * 3 - sk * 2) / 2
    sy = by + 104
    for i in range(3):
        x = sx0 + i * (sw - sk)
        if i == 0:
            pts = f"{x},{sy} {x+sw},{sy} {x+sw-sk},{sy+sh} {x},{sy+sh}"
        elif i == 1:
            pts = f"{x+sk},{sy} {x+sw},{sy} {x+sw-sk},{sy+sh} {x},{sy+sh}"
        else:
            pts = f"{x+sk},{sy} {x+sw},{sy} {x+sw},{sy+sh} {x},{sy+sh}"
        defs_clip = f'<clipPath id="sl{i}"><polygon points="{pts}"/></clipPath>'
        duo += defs_clip
        body.append(f'<image x="{x}" y="{sy}" width="{sw}" height="{sh}" preserveAspectRatio="xMidYMid slice" '
                    f'xlink:href="{b64(img / f"slice-{i+1}.jpg", "image/jpeg")}" clip-path="url(#sl{i})" '
                    f'filter="url(#duo2)" opacity="{.82 + i*.05:.2f}"/>')
        body.append(f'<polygon points="{pts}" fill="none" stroke="{C["ink"]}" stroke-width="2"/>')

    bio = clean(p.get("bio", ""))
    ty = sy + sh + 24
    for line in wrap(bio, 39, 7):
        body.append(text(bx + 16, ty, line, "plex", 9.6, C["text"]))
        ty += 14
    body.append(text(bx + bw - 16, by + bh - 30, "in the wired,", "play", 11.5, C["text"], "end"))
    body.append(text(bx + bw - 16, by + bh - 15, "always connected.", "play", 11.5, C["dim"], "end"))

    body.append(text(L, H - 26, f"{clean(p.get('location','')).upper()}  ·  {p.get('timezone','')}",
                     "plex", 8, C["dim"], ls=2))

    # ---- Framed thumbnails (slide out from under the portrait) -------------
    thumbs = [("thumb-wired.jpg", "THE WIRED"), ("thumb-glitch.jpg", "SIGNAL LOSS"), ("thumb-navi.jpg", "NAVI")]
    for i, (f, cap) in enumerate(thumbs):
        tx, ty2 = 662 - i * 10, 300 + i * 80
        duo += f'<clipPath id="tc{i}"><rect width="124" height="72" rx="14"/></clipPath>'
        body.append(
            f'<g transform="translate({tx} {ty2})"><g>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{14 + i*4} 0;0 0" keyTimes="0;.5;1" '
            f'dur="{7 + i*1.5:.1f}s" begin="{i*.8:.1f}s" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"/>'
            f'<g filter="url(#shadow)"><image width="124" height="72" preserveAspectRatio="xMidYMid slice" '
            f'xlink:href="{b64(img / f, "image/jpeg")}" clip-path="url(#tc{i})" filter="url(#duo2)"/></g>'
            f'<rect x="1.5" y="1.5" width="121" height="69" rx="13" fill="none" stroke="{C["paper"]}" stroke-width="2.5"/>'
            f'</g></g>')
        body.append(text(tx + 156, ty2 + 34, cap, "plex", 7.5, C["red_hi"], ls=2))
        body.append(text(tx + 156, ty2 + 46, f"FRAME 0{i+1}", "plex", 7, C["dim"], ls=2))

    # ---- Portrait ----------------------------------------------------------
    body.append(f'<g clip-path="url(#pclip)">'
                f'<image x="356" y="24" width="288" height="512" preserveAspectRatio="xMidYMin slice" '
                f'xlink:href="{b64(img / "portrait.jpg", "image/jpeg")}" filter="url(#duo)"/>'
                f'<rect x="356" y="24" width="288" height="512" fill="url(#scan)" opacity=".35"/>'
                f'<rect x="356" y="24" width="288" height="512" fill="url(#fadeB)"/>'
                f'<rect x="356" y="24" width="288" height="512" fill="url(#fadeT)"/></g>')
    body.append(f'<polygon points="372,24 644,24 628,536 356,536" fill="none" stroke="{C["paper"]}" stroke-width="1.5"/>')
    body.append(text(390, 62, "PRESENT DAY", "bebas", 22, C["paper"], ls=1.5))
    body.append(text(390, 84, "PRESENT TIME", "bebas", 22, C["paper"], ls=1.5))
    body.append(f'<g transform="rotate(-7 500 300)"><rect x="326" y="286" width="348" height="27" fill="{C["red"]}" opacity=".92"/>'
                + text(500, 305, clean(p.get("name", "")).upper(), "cut", 16, C["paper"], "middle", ls=4) + "</g>")
    body.append(text(500, 424, clean(p.get("quote", "close the world, open the next")), "play", 15, C["paper"], "middle",
                     extra='filter="url(#pulse)"'))
    body.append(text(500, 446, "PROTOCOL 7  ·  ESTABLISHED", "plex", 8, C["muted"], "middle", ls=3))
    body.append(f'<g transform="rotate(180 494 516)">' + text(494, 520, "NO MATTER WHERE YOU ARE, EVERYONE IS ALWAYS CONNECTED",
                "bebas", 12.5, C["paper"], "middle", ls=1, extra='textLength="250" lengthAdjust="spacingAndGlyphs"') + "</g>")

    # ---- Divergence readout (Steins;Gate) ----------------------------------
    dv = str(st.get("signal", {}).get("divergence", "1.048596"))
    rx0 = 684
    body.append(text(rx0, 58, "WORLD LINE DIVERGENCE", "plex", 8, C["muted"], ls=3))
    for i, ch in enumerate(dv[:8]):
        x = rx0 + i * 26
        body.append(f'<rect x="{x}" y="68" width="22" height="50" rx="9" fill="#140806" stroke="#4a2018"/>')
        flick = ""
        if i in (2, 6):
            flick = f'<animate attributeName="opacity" values="1;.45;1;1;.8;1" keyTimes="0;.04;.08;.6;.63;1" dur="{4+i}s" repeatCount="indefinite"/>'
        body.append(f'<text x="{x+11}" y="104" class="cut" font-size="34" fill="{C["nixie"]}" text-anchor="middle" filter="url(#glow)">{esc(ch)}{flick}</text>')
    body.append(text(rx0, 138, "STEINS;GATE  ·  FIELD: NONE", "plex", 9, C["red_hi"], ls=2))
    body.append(text(rx0, 158, "El Psy Kongroo.", "play", 12, C["muted"]))
    sline = "  ·  ".join(f"{k} {v}" for k, v in [("REPOS", stats.get("repos")), ("STARS", stats.get("stars")),
                                                     ("FOLLOWERS", stats.get("followers"))] if v is not None)
    if sline:
        body.append(text(rx0, 196, sline, "plex", 8, C["text"], ls=2))
    if stats.get("contributions") is not None:
        body.append(text(rx0, 212, f"CONTRIBUTIONS / 12 MO  {stats['contributions']}", "plex", 8, C["text"], ls=2))
    body.append(f'<line x1="{rx0}" y1="226" x2="{rx0+210}" y2="226" stroke="{C["line"]}"/>')
    rank, cleared = whistle_rank(stats.get("contributions"))
    body.append(f'<text x="{rx0}" y="246" class="plex" font-size="9" letter-spacing="2"><tspan fill="{C["muted"]}">WHISTLE </tspan>'
                f'<tspan fill="{C["red_hi"]}">{rank.upper()}</tspan><tspan fill="{C["muted"]}">  \u00b7  {cleared.upper()}</tspan></text>')
    # Kaneki's count: 1000 - 7, cycling
    n, frames = 1000, []
    for k in range(6):
        frames.append((n, n - 7))
        n -= 7
    for k, (a, b) in enumerate(frames):
        vis = "1" if k == 0 else "0"
        vals = ";".join("1" if j == k else "0" for j in range(6))
        body.append(f'<text x="{rx0}" y="268" class="plex" font-size="9" fill="{C["red_hi"]}" letter-spacing="2" opacity="{vis}">'
                    f'{a} - 7 = {b}<animate attributeName="opacity" values="{vals}" dur="6s" calcMode="discrete" repeatCount="indefinite"/></text>')

    # ---- Abyss depth gauge -------------------------------------------------
    gx = 966
    body.append(f'<line x1="{gx}" y1="40" x2="{gx}" y2="{H-30}" stroke="{C["line"]}"/>')
    body.append(text(gx, 30, "DEPTH", "plex", 7, C["dim"], "middle", ls=2))
    for i, (depth, _) in enumerate(LAYERS):
        y = 56 + i * 72
        body.append(f'<line x1="{gx-4}" y1="{y}" x2="{gx+4}" y2="{y}" stroke="{C["red"]}"/>')
        body.append(text(gx - 9, y + 3, f"L{i+1}", "bebas", 11, C["red_hi"], "end", ls=1))
        body.append(text(gx - 9, y + 13, depth, "plex", 6.5, C["dim"], "end"))
    body.append(f'<polygon points="{gx+3},0 {gx+9},-4 {gx+9},4" fill="{C["red_hi"]}">'
                f'<animateTransform attributeName="transform" type="translate" values="0 56;0 488" dur="48s" repeatCount="indefinite"/></polygon>')

    title = f"{p.get('name','')} ({USER}): {bio}"
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair", "Cutive"), duo, title)


def section_header(n):
    W, H = 1000, 86
    depth, layer = LAYERS[n - 1]
    title, kicker = SECTIONS[n - 1]
    stitches = " ".join(f"M{x} 66l7 12" for x in range(34, 966, 14))
    body = [
        text(28, 37, f"LAYER:{n:02d}", "bebas", 17, C["red_hi"], ls=4),
        text(28, 56, f"{depth} — {layer}", "plex", 8.5, C["muted"], ls=2),
        text(300, 51, title, "play", 29, C["paper"]),
        text(972, 37, kicker, "plex", 8.5, C["text"], "end", ls=3),
        text(972, 56, f"{n:02d} / {len(SECTIONS):02d}", "plex", 8, C["dim"], "end", ls=2),
        f'<path d="M28 72H972" stroke="{C["line"]}" stroke-width="1.5"/>',
        f'<path d="{stitches}" stroke="{C["dim"]}" stroke-width="1.3" stroke-linecap="round"/>',
        f'<rect x="28" y="70" width="{40 + n*16}" height="3" fill="{C["red"]}"/>',
        f'<rect y="69" width="2" height="6" fill="{C["red_hi"]}"><animate attributeName="x" values="28;970;28" dur="14s" repeatCount="indefinite"/></rect>',
    ]
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), title=f"Layer {n:02d}: {title} ({kicker.lower()})")


def about_card(st):
    a = st.get("about", {})
    W = 1000
    body, ly = [], 64
    for line in wrap(clean(a.get("statement", "")), 44):
        body.append(text(40, ly, line, "play", 21, C["paper"]))
        ly += 31
    ly += 10
    for line in wrap(clean(a.get("detail", "")), 84):
        body.append(text(40, ly, line, "plex", 10.5, C["text"]))
        ly += 17

    backlog = st.get("backlog", []) or []
    if backlog:
        ly += 20
        body.append(text(40, ly, "STAGED PROTOCOLS / BACKLOG", "plex", 8, C["red_hi"], ls=3))
        ly += 20
        for item in backlog:
            for j, line in enumerate(wrap(clean(item), 78)):
                body.append(text(40, ly, "—" if j == 0 else "", "plex", 10.5, C["red"]))
                body.append(text(62, ly, line, "plex", 10.5, C["text"]))
                ly += 17
            ly += 4

    rx, ry = 610, 56
    for key, label in [("based_in", "BASED IN"), ("studying", "STUDYING"), ("now", "NOW SOLVING"),
                       ("research", "RESEARCH"), ("exploring", "EXPLORING")]:
        if not a.get(key):
            continue
        body.append(text(rx, ry, label, "plex", 8, C["red_hi"], ls=3))
        ry += 18
        for line in wrap(clean(a[key]), 48):
            body.append(text(rx, ry, line, "plex", 10.5, C["paper"]))
            ry += 16
        ry += 14
    H = max(ly, ry) + 26
    body.insert(0, f'<line x1="580" y1="40" x2="580" y2="{H-30}" stroke="{C["line"]}"/>')
    body.append(text(972, H - 18, "0 M — SURFACE", "plex", 7.5, C["dim"], "end", ls=2))
    desc = " ".join(clean(a.get(k, "")) for k in ("statement", "detail", "based_in", "studying", "now", "research", "exploring"))
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), title=f"About: {desc}")


RAMP = ["#c8102e", "#f4f2ed", "#9e9c97", "#5f5d59", "#7d0e1b"]


def project_card(i, r, override, mobile=False):
    W = 1000
    rd_tag, rd_sum = readme_summary(r.get("readme", ""), r["name"])
    desc = clean(r.get("description"))
    # Tagline: README headline, else a short description.
    # Summary: README About/Overview section, else the description, else the
    # first real paragraph of the README.
    if rd_tag:
        tagline = rd_tag
    elif desc and len(desc) <= 80:
        tagline = desc
    else:
        tagline = ""
    if rd_sum and rd_sum[1]:
        summary = rd_sum[0]
    elif desc and desc != tagline:
        summary = desc
    else:
        summary = rd_sum[0] if rd_sum else ""
    tagline = clean(override.get("tagline")) or tagline
    summary = clean(override.get("summary")) or summary
    if summary == tagline:
        summary = ""
    if not tagline and not summary:
        tagline = "No transmission recorded."
    tagline = clip(tagline, 78)
    if mobile:
        return project_m(i, r, tagline, summary, f"{r['name']}: {tagline}. {summary}")
    sum_lines = wrap(summary, 96, 3) if summary else []
    H = 178 + 16 * max(0, len(sum_lines) - 1) + (30 if r.get("topics") else 0)
    n_lang = len(r.get("languages") or [])
    H = max(H, 166 + 18 * ((min(n_lang, 4) + 1) // 2))

    pushed = (r.get("pushed") or "")[:10]
    body = [
        text(36, 46, f"PINNED · {i:02d}", "bebas", 14, C["red_hi"], ls=4),
        text(160, 45, f"WORLD LINE {world_line(r['name'])}", "plex", 9, C["nixie"], ls=2),
        text(380, 45, f"RELIC  {relic_grade(r.get('stars'), r.get('forks')).upper()}", "plex", 9, C["muted"], ls=2),
        text(36, 90, r["name"], "bebas", 42, C["paper"], ls=1),
        text(36, 118, tagline, "play", 15.5, C["text"]),
    ]
    y = 144 if tagline else 120
    for line in sum_lines:
        body.append(text(36, y, line, "plex", 10.5, C["muted"]))
        y += 16
    if r.get("topics"):
        x = 36
        y += 8
        for t in r["topics"][:6]:
            t = clean(t)
            w = len(t) * 5.4 + 18
            body.append(f'<rect x="{x}" y="{y}" width="{w:.0f}" height="18" rx="2" fill="none" stroke="{C["line"]}"/>')
            body.append(text(x + w / 2, y + 12.5, t, "plex", 9, C["text"], "middle"))
            x += w + 8

    # Right panel: composition bar in bronze tones + meta
    px, pw = 690, 274
    body.append(f'<line x1="666" y1="30" x2="666" y2="{H-30}" stroke="{C["line"]}"/>')
    body.append(text(px, 46, "LAST TRANSMISSION", "plex", 8, C["muted"], ls=3))
    body.append(text(px + pw, 46, pushed, "plex", 8, C["text"], "end", ls=2))
    body.append(text(px, 80, "COMPOSITION", "plex", 8, C["muted"], ls=3))
    langs = r.get("languages") or []
    x = px
    for j, (name, frac) in enumerate(langs):
        w = max(2, pw * frac)
        body.append(f'<rect x="{x:.1f}" y="88" width="{w:.1f}" height="6" fill="{RAMP[j % 5]}"/>')
        x += w
    if not langs:
        body.append(f'<rect x="{px}" y="88" width="{pw}" height="6" fill="{C["line"]}"/>')
    for j, (name, frac) in enumerate(langs[:4]):
        lx = px + (j % 2) * 140
        ly = 114 + (j // 2) * 18
        body.append(f'<rect x="{lx}" y="{ly-7}" width="7" height="7" fill="{RAMP[j % 5]}"/>')
        body.append(text(lx + 13, ly, f"{clean(name)} {frac*100:.1f}%", "plex", 9.5, C["text"]))
    meta = f"STARS {r.get('stars',0)}  ·  FORKS {r.get('forks',0)}"
    body.append(text(px, H - 34, meta, "plex", 8.5, C["text"], ls=2))
    body.append(text(px + pw, H - 34, "OPEN →", "plex", 8.5, C["red_hi"], "end", ls=2))
    title = f"{r['name']}: {tagline}. {summary}"
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), title=title)


def toolkit_card(st):
    groups = st.get("toolkit", {})
    W = 1000
    body, y = [], 52
    for gi, (group, items) in enumerate(groups.items()):
        body.append(text(36, y + 4, clean(group).upper(), "bebas", 15, C["red_hi"], ls=4))
        body.append(text(36, y + 20, f"0{gi+1}", "plex", 8, C["dim"], ls=2))
        x = 220
        for it in items or []:
            primary = it.endswith("*")
            it = clean(it.rstrip("*"))
            w = len(it) * 6.6 + 26
            if x + w > 964:
                x = 220
                y += 36
            stroke = C["red_hi"] if primary else C["line"]
            body.append(f'<rect x="{x}" y="{y-14}" width="{w:.0f}" height="26" rx="3" fill="{C["panel"]}" stroke="{stroke}"/>')
            body.append(text(x + w / 2, y + 3.5, it, "plex", 11, C["paper"] if primary else C["text"], "middle"))
            x += w + 10
        y += 36
        if gi < len(groups) - 1:
            body.append(f'<line x1="36" y1="{y-8}" x2="964" y2="{y-8}" stroke="{C["line"]}" stroke-dasharray="2 4"/>')
            y += 24
    H = y + 14
    body.append(text(964, H - 16, "OUTLINED = PRIMARY", "plex", 7.5, C["dim"], "end", ls=2))
    flat = "; ".join(f"{g}: " + ", ".join(i.rstrip('*') for i in v) for g, v in groups.items())
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex"), title=f"Toolkit. {flat}")


def system_card(st):
    s = st.get("system", {})
    W = 1000
    rows = [(k, s.get(v)) for k, v in [("OS", "os"), ("KERNEL", "kernel"), ("MACHINE", "machine"), ("DESKTOP", "desktop"),
                                         ("SHELL", "shell"), ("TERMINAL", "terminal"), ("CPU", "cpu"), ("GPU", "gpu"),
                                         ("MEMORY", "memory"), ("FILESYSTEM", "filesystem")] if s.get(v)]
    H = max(320, 118 + 24 * len(rows) + 50)
    ix = 290
    body = [
        f'<circle cx="140" cy="128" r="70" fill="none" stroke="{C["line"]}"/>',
        f'<circle cx="140" cy="128" r="76" fill="none" stroke="{C["red"]}" stroke-dasharray="1 5"/>',
        f'<image x="80" y="68" width="120" height="120" xlink:href="{b64(ASSETS / "img" / "navi.png", "image/png")}" filter="url(#duo2)"/>',
        text(140, 236, "NAVI", "bebas", 22, C["paper"], "middle", ls=6),
        text(140, 254, "COPLAND OS ENTERPRISE", "plex", 7.5, C["dim"], "middle", ls=2),
        f'<text x="{ix}" y="62" class="plex" font-size="14"><tspan fill="{C["red_hi"]}">{esc(s.get("user",""))}</tspan>'
        f'<tspan fill="{C["dim"]}">@</tspan><tspan fill="{C["paper"]}">{esc(s.get("host",""))}</tspan></text>',
        f'<line x1="{ix}" y1="76" x2="{ix+300}" y2="76" stroke="{C["line"]}" stroke-dasharray="3 3"/>',
    ]
    y = 104
    for k, v in rows:
        body.append(text(ix, y, k, "bebas", 13, C["red"], ls=3))
        body.append(text(ix + 100, y, clip(clean(v), 52), "plex", 11.5, C["paper"]))
        y += 24
    # palette swatches, fastfetch style
    for i, col in enumerate([C["ink"], C["dim"], C["red"], C["red_hi"], C["muted"], C["text"], C["paper"], C["nixie"]]):
        body.append(f'<rect x="{ix + i*24}" y="{y+2}" width="20" height="10" fill="{col}" stroke="{C["line"]}"/>')
    # flavour panel, kept apart from the real specs
    fx = 736
    body.append(f'<rect x="{fx}" y="44" width="228" height="132" fill="{C["panel"]}" stroke="{C["line"]}"/>')
    body.append(text(fx + 14, 66, "LORE", "plex", 8, C["red_hi"], ls=3))
    for j, (k, v) in enumerate([("host", "layer 07 // the wired"), ("uptime", "always connected"),
                                ("time", "present day, present time"), ("protocol", "seven")]):
        body.append(text(fx + 14, 92 + j * 20, k, "plex", 9, C["dim"]))
        body.append(text(fx + 70, 92 + j * 20, v, "plex", 9, C["text"]))
    body.append(text(964, H - 18, "SPECS READ FROM FASTFETCH · " + clean(s.get("synced", "")), "plex", 7.5, C["dim"], "end", ls=2))
    duo = f"""<filter id="duo2" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .95"/><feFuncG type="table" tableValues=".04 .15"/>
<feFuncB type="table" tableValues=".04 .25"/></feComponentTransfer></filter>"""
    title = "System. " + "; ".join(f"{k.title()}: {v}" for k, v in rows)
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex"), duo, title)


NIXIE_DEFS = f"""<filter id="nglow" x="-60%" y="-30%" width="220%" height="160%"><feGaussianBlur stdDeviation="4" result="a"/>
<feGaussianBlur in="SourceGraphic" stdDeviation="1" result="b"/><feMerge><feMergeNode in="a"/><feMergeNode in="a"/>
<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".13"/>
<stop offset=".12" stop-color="#fff" stop-opacity=".03"/><stop offset=".7" stop-color="#fff" stop-opacity="0"/>
<stop offset=".9" stop-color="#fff" stop-opacity=".08"/><stop offset="1" stop-color="#fff" stop-opacity=".02"/></linearGradient>
<radialGradient id="warm" cx=".5" cy=".6" r=".6"><stop offset="0" stop-color="{C['nixie']}" stop-opacity=".26"/>
<stop offset="1" stop-color="{C['nixie']}" stop-opacity="0"/></radialGradient>
<pattern id="mesh" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<path d="M0 2.5h5M2.5 0v5" stroke="#ff9070" stroke-width=".35" opacity=".3"/></pattern>
<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2416"/><stop offset=".5" stop-color="#24150c"/>
<stop offset="1" stop-color="#120a05"/></linearGradient>
<linearGradient id="brass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c9a35c"/><stop offset="1" stop-color="#6b4f22"/></linearGradient>
<linearGradient id="sock" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0c0c0c"/><stop offset=".45" stop-color="#2c2c2c"/>
<stop offset="1" stop-color="#0c0c0c"/></linearGradient>"""


def nixie_row(dv, x0, top, tw, th, gap, fs, seed="meter"):
    """A row of IN-14 style tubes on a wooden base. Every 14 s the reading shuffles like a
    world-line shift and settles again; at frame 0 the real reading is lit."""
    T = 14.0
    h = hashlib.sha1(seed.encode()).digest()
    out = []
    total = len(dv) * tw + (len(dv) - 1) * gap
    bot = top + th
    # base plate with brass trim and screws
    out.append(f'<rect x="{x0-22}" y="{bot-4}" width="{total+44}" height="{tw*.42:.0f}" rx="4" fill="url(#wood)" stroke="#000"/>')
    out.append(f'<rect x="{x0-22}" y="{bot-4}" width="{total+44}" height="2.2" fill="url(#brass)"/>')
    for sx in (x0 - 13, x0 + total + 13):
        out.append(f'<circle cx="{sx}" cy="{bot + tw*.2:.1f}" r="3" fill="url(#brass)" stroke="#000" stroke-width=".6"/>'
                   f'<path d="M{sx-2} {bot + tw*.2:.1f}h4" stroke="#3a2a10" stroke-width=".8"/>')
    r = tw / 2
    for i, ch in enumerate(dv):
        x = x0 + i * (tw + gap)
        mx = x + r
        body = f"M{x} {bot} V{top + r} A{r} {r} 0 0 1 {x + tw} {top + r} V{bot} Z"
        out.append(f'<path d="M{mx-3} {top+2} v-7 a3 3 0 0 1 6 0 v7z" fill="#2a1410" stroke="#4a2018" stroke-width=".8"/>')
        out.append(f'<path d="{body}" fill="#120706" stroke="#4a2018" stroke-width="1.5"/>')
        out.append(f'<path d="{body}" fill="url(#warm)"/>')
        # support posts and the anode mesh cage
        out.append(f'<path d="M{x+5} {top+r*.8} V{bot-2} M{x+tw-5} {top+r*.8} V{bot-2}" stroke="#5a3a2a" stroke-width="1.2"/>')
        out.append(f'<path d="M{x+5} {top+r*.8} H{x+tw-5}" stroke="#5a3a2a" stroke-width=".8"/>')
        ty = top + th * .74
        if ch == ".":
            out.append(f'<g filter="url(#nglow)"><circle cx="{x + tw*.3:.1f}" cy="{ty:.1f}" r="{fs*.07:.1f}" fill="{C["nixie_core"]}" '
                       f'stroke="{C["nixie"]}" stroke-width="1.2"/></g>')
        else:
            for g in "0123456789":
                out.append(f'<text x="{mx}" y="{ty:.1f}" class="cut" font-size="{fs}" fill="none" stroke="#6a2a1c" '
                           f'stroke-width=".7" text-anchor="middle" opacity=".33">{g}</text>')
            settle = .5 + .14 * i
            k = 7
            step = settle / k
            seq = [str(h[(i * 7 + j) % len(h)] % 10) for j in range(k)]
            g = [f'<g filter="url(#nglow)">']
            t0 = 4.0  # the true reading is lit at frame 0; the shift starts 4 s in
            for j, d in enumerate(seq):
                a0, a1 = (t0 + j * step) / T, (t0 + (j + 1) * step) / T
                g.append(f'<text x="{mx}" y="{ty:.1f}" class="cut" font-size="{fs}" fill="{C["nixie_core"]}" stroke="{C["nixie"]}" '
                         f'stroke-width="1.5" text-anchor="middle" opacity="0">{d}<animate attributeName="opacity" values="0;1;0;0" '
                         f'keyTimes="0;{a0:.4f};{a1:.4f};1" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></text>')
            q0, s0 = t0 / T, (t0 + settle) / T
            g.append(f'<text x="{mx}" y="{ty:.1f}" class="cut" font-size="{fs}" fill="{C["nixie_core"]}" stroke="{C["nixie"]}" '
                     f'stroke-width="1.6" text-anchor="middle">{esc(ch)}<animate attributeName="opacity" '
                     f'values="1;0;1;.4;1;1;.55;1" keyTimes="0;{q0:.4f};{s0:.4f};{s0+.006:.4f};{s0+.012:.4f};{.75+i*.02:.3f};{.753+i*.02:.3f};1" '
                     f'calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></text>')
            g.append("</g>")
            out.append("".join(g))
        out.append(f'<rect x="{x+4}" y="{top+8}" width="{tw-8}" height="{th-14}" rx="{r-4}" fill="url(#mesh)"/>')
        out.append(f'<path d="{body}" fill="url(#glass)"/>')
        out.append(f'<path d="M{x+5} {bot-8} V{top + r} A{r-5} {r-5} 0 0 1 {x + r*.7:.1f} {top+6}" fill="none" stroke="#fff" '
                   f'stroke-width="1.2" opacity=".12"/>')
        # socket with pins
        out.append(f'<rect x="{x-2}" y="{bot-10}" width="{tw+4}" height="12" rx="3" fill="url(#sock)" stroke="#000"/>')
        for p in range(5):
            px = x + 6 + p * (tw - 12) / 4
            out.append(f'<path d="M{px:.1f} {bot-10} v-4" stroke="#8a7a6a" stroke-width=".7" opacity=".7"/>')
    return "".join(out), total


def signal_card(st, stats, today, mobile=False):
    dv = str(st.get("signal", {}).get("divergence", "1.048596"))[:8]
    cells = [("PUBLIC REPOS", stats.get("repos")), ("STARS EARNED", stats.get("stars")), ("FOLLOWERS", stats.get("followers")),
             ("CONTRIBUTIONS / 12 MO", stats.get("contributions")), ("LAST SYNC", today)]
    title = f"World line divergence {dv}. " + ", ".join(f"{k.lower()} {v}" for k, v in cells if v is not None)
    if mobile:
        W = 480
        tw, gap = 46, 7
        x0 = (W - (8 * tw + 7 * gap)) / 2
        row, _ = nixie_row(dv, x0, 34, tw, 104, gap, 58)
        body = [wires(W, 6, ".35", signal=False), row]
        body.append(text(W / 2, 192, "WORLD LINE DIVERGENCE", "plex", 12, C["muted"], "middle", ls=3))
        body.append(text(W / 2, 210, "STEINS;GATE  ·  ATTRACTOR FIELD: NONE", "plex", 11, C["dim"], "middle", ls=1.5))
        body.append(f'<line x1="20" y1="226" x2="460" y2="226" stroke="{C["line"]}"/>')
        y = 270
        for i, (k, v) in enumerate(cells):
            cx = 20 + (i % 2) * 226
            if i % 2 == 0 and i:
                y += 70
            size = 28 if k == "LAST SYNC" else 40
            body.append(text(cx, y, "—" if v is None else v, "bebas", size, C["paper"], ls=1))
            body.append(text(cx, y + 20, k, "plex", 11, C["muted"], ls=1.5))
        H = y + 46
        return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Cutive"), NIXIE_DEFS, title)
    W, H = 1000, 340
    tw, gap = 70, 14
    x0 = (W - (8 * tw + 7 * gap)) / 2
    row, _ = nixie_row(dv, x0, 30, tw, 150, gap, 84)
    body = [wires(W, 6, ".35", signal=False), row]
    body.append(text(W / 2, 228, "WORLD LINE DIVERGENCE  ·  STEINS;GATE  ·  ATTRACTOR FIELD: NONE", "plex", 9, C["muted"], "middle", ls=3))
    body.append(f'<line x1="36" y1="246" x2="964" y2="246" stroke="{C["line"]}"/>')
    cw = (W - 72) / len(cells)
    for i, (k, v) in enumerate(cells):
        cx = 36 + i * cw
        if i:
            body.append(f'<line x1="{cx}" y1="264" x2="{cx}" y2="316" stroke="{C["line"]}"/>')
        size = 22 if k == "LAST SYNC" else 36
        body.append(text(cx + 20, 300, "—" if v is None else v, "bebas", size, C["paper"], ls=1))
        body.append(text(cx + 20, 318, k, "plex", 7.5, C["muted"], ls=2))
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Cutive"), NIXIE_DEFS, title)


def _vein_tree(rng, x, y, ang, length, width, depth, out, max_depth=3):
    """Branching, wandering vein. Appends (path, width, depth)."""
    pts, a = [(x, y)], ang
    for _ in range(4):
        a += rng.uniform(-.4, .4)
        x += math.cos(a) * length / 4
        y += math.sin(a) * length / 4
        pts.append((x, y))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f} " + " ".join(
        f"Q{pts[k][0]:.1f} {pts[k][1]:.1f} {(pts[k][0]+pts[k+1][0])/2:.1f} {(pts[k][1]+pts[k+1][1])/2:.1f}"
        for k in range(1, len(pts) - 1)) + f" L{pts[-1][0]:.1f} {pts[-1][1]:.1f}"
    out.append((d, width, depth))
    if depth < max_depth:
        for k in range(1, len(pts)):
            if rng.random() < .55:
                _vein_tree(rng, pts[k][0], pts[k][1], a + rng.choice((-1, 1)) * rng.uniform(.45, 1.0),
                           length * .55, width * .6, depth + 1, out, max_depth)


def _qpt(p0, p1, p2, t):
    return ((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0], (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1])


def kakugan(ex, ey, s=1.0, uid="k"):
    """A living kakugan: black sclera webbed with capillaries, a fibred red iris whose pupil
    sometimes pinches to a slit, lashes, creased lids, raised veins crawling over the skin
    and a slow tear of blood. GitHub serves SVG as an image with no scripts, so it can't
    follow the cursor; it watches the page on its own. At frame 0 the eye is open."""
    import random
    rng = random.Random(7)
    hw, hh = 62 * s, 40 * s
    L, R, T, B = (ex - hw, ey), (ex + hw, ey), (ex, ey - hh), (ex, ey + hh)
    eye = f"M{L[0]} {ey} Q{ex} {ey-hh} {R[0]} {ey} Q{ex} {ey+hh} {L[0]} {ey}Z"
    ir = 22 * s
    defs = (f'<radialGradient id="{uid}iris" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffd0b0"/>'
            f'<stop offset=".22" stop-color="#ff6a4a"/><stop offset=".55" stop-color="{C["red_hi"]}"/>'
            f'<stop offset=".85" stop-color="{C["red"]}"/><stop offset="1" stop-color="#3a0008"/></radialGradient>'
            f'<radialGradient id="{uid}scl" cx=".5" cy=".5" r=".65"><stop offset="0" stop-color="#2a0509"/>'
            f'<stop offset=".6" stop-color="#0a0102"/><stop offset="1" stop-color="#000"/></radialGradient>'
            f'<radialGradient id="{uid}sock" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#3a0610" stop-opacity=".75"/>'
            f'<stop offset=".55" stop-color="#1a0306" stop-opacity=".5"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="{uid}shade" cx=".5" cy=".15" r=".8"><stop offset="0" stop-color="#000" stop-opacity=".75"/>'
            f'<stop offset=".5" stop-color="#000" stop-opacity="0"/></radialGradient>'
            f'<filter id="{uid}glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{5*s:.1f}"/></filter>'
            f'<filter id="{uid}soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="{.5*s:.2f}"/></filter>'
            f'<clipPath id="{uid}clip"><path d="{eye}"/></clipPath>')
    out = []
    # bruised socket and lid creases
    out.append(f'<ellipse cx="{ex}" cy="{ey+4*s}" rx="{hw*1.7:.1f}" ry="{hh*1.9:.1f}" fill="url(#{uid}sock)"/>')
    for k, (lift, op) in enumerate([(24, .9), (34, .45)]):
        out.append(f'<path d="M{L[0]+12*s:.1f} {ey-6*s:.1f} Q{ex} {ey-hh-lift*s:.1f} {R[0]-4*s:.1f} {ey-10*s:.1f}" fill="none" '
                   f'stroke="{C["muted"] if k == 0 else C["dim"]}" stroke-width="{(1.1-k*.4)*s:.2f}" opacity="{op}" stroke-linecap="round"/>')
    for k, drop in enumerate((14, 24)):
        out.append(f'<path d="M{L[0]+18*s:.1f} {ey+10*s:.1f} Q{ex} {ey+hh+drop*s:.1f} {R[0]-16*s:.1f} {ey+10*s:.1f}" fill="none" '
                   f'stroke="{C["dim"]}" stroke-width="{.8*s:.2f}" opacity="{.6-k*.25}" stroke-dasharray="{"" if k == 0 else f"{3*s:.0f} {2*s:.0f}"}"/>')

    # raised veins crawling out over the skin, mostly from the outer corners and under the eye
    veins = []
    for i in range(4):
        _vein_tree(rng, R[0] - 2 * s, ey + rng.uniform(-5, 5) * s, rng.uniform(-.55, .55), rng.uniform(38, 58) * s, 1.8 * s, 0, veins, 2)
        _vein_tree(rng, L[0] + 2 * s, ey + rng.uniform(-5, 5) * s, math.pi + rng.uniform(-.55, .55), rng.uniform(38, 58) * s, 1.8 * s, 0, veins, 2)
    for t in (.32, .62):
        px, py = _qpt((R[0], ey), (ex, ey + hh), (L[0], ey), t)
        _vein_tree(rng, px, py + 3 * s, math.pi / 2 + rng.uniform(-.4, .4), rng.uniform(20, 30) * s, 1.1 * s, 1, veins, 2)
    under = "".join(f'<path d="{d}" stroke="#000" stroke-width="{w+1.4*s:.2f}" opacity=".8"/>' for d, w, _ in veins)
    over = "".join(f'<path d="{d}" stroke="{("#a00c26", "#7d0e1b", "#4a0712")[dep]}" stroke-width="{w:.2f}" '
                   f'opacity="{(.95, .75, .55)[dep]}"/>' for d, w, dep in veins)
    hi = "".join(f'<path d="{d}" stroke="#ff8a8a" stroke-width="{w*.28:.2f}" opacity=".45"/>' for d, w, dep in veins if dep == 0)
    out.append(f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{under}{over}{hi}'
               f'<animate attributeName="opacity" values="1;.62;1;.85;1" keyTimes="0;.18;.36;.5;1" dur="2.4s" repeatCount="indefinite"/></g>')

    # the eyeball
    caps = []
    for i in range(7):
        side = -1 if i % 2 else 1
        _vein_tree(rng, ex + side * (hw - 4 * s), ey + rng.uniform(-10, 10) * s, (math.pi if side > 0 else 0) + rng.uniform(-.5, .5),
                   rng.uniform(26, 44) * s, .9 * s, 1, caps, 3)
    caps_svg = "".join(f'<path d="{d}" stroke="{C["red"] if dep < 2 else C["red_dk"]}" stroke-width="{w:.2f}" opacity=".85"/>'
                       for d, w, dep in caps)
    pts = [(0, 0), (-16, -3), (-16, -3), (12, 2), (12, 2), (3, -7), (3, -7), (-8, 6), (-8, 6), (0, 0), (0, 0), (19, -1), (19, -1), (0, 0)]
    kts = [0, .10, .22, .23, .38, .39, .52, .53, .64, .65, .76, .77, .92, .93]
    vals = ";".join(f"{x*s:.1f} {y*s:.1f}" for x, y in pts) + ";0 0"
    kt = ";".join(f"{k:.2f}" for k in kts) + ";1"
    fib = []
    for k in range(96):
        a = k * 2 * math.pi / 96 + rng.uniform(-.02, .02)
        r0, r1 = 8 * s + rng.uniform(0, 2) * s, ir * rng.uniform(.72, .98)
        col = rng.choice(("#ffb0a0", "#ff7060", C["red_dk"], "#7a0010", "#ffd8c8"))
        fib.append(f'<path d="M{ex+math.cos(a)*r0:.1f} {ey+math.sin(a)*r0:.1f} L{ex+math.cos(a)*r1:.1f} {ey+math.sin(a)*r1:.1f}" '
                   f'stroke="{col}" stroke-width="{rng.uniform(.35, .8)*s:.2f}" opacity="{rng.uniform(.35, .8):.2f}"/>')
    collar = " ".join(f"{ex+math.cos(k*math.pi/14)*(10.5+(1.8 if k % 2 else -.6))*s:.1f},{ey+math.sin(k*math.pi/14)*(10.5+(1.8 if k % 2 else -.6))*s:.1f}"
                      for k in range(28))
    crypts = "".join(f'<ellipse cx="{ex+math.cos(a)*r:.1f}" cy="{ey+math.sin(a)*r:.1f}" rx="{1.4*s:.1f}" ry="{.7*s:.1f}" '
                     f'transform="rotate({math.degrees(a):.0f} {ex+math.cos(a)*r:.1f} {ey+math.sin(a)*r:.1f})" fill="#2a0006" opacity=".7"/>'
                     for a, r in [(rng.uniform(0, 6.28), rng.uniform(12, 18) * s) for _ in range(14)])
    blink_k = "0;.30;.312;.326;.80;.812;.826;.838;.85;1"
    out.append(
        f'<g clip-path="url(#{uid}clip)">'
        f'<path d="{eye}" fill="url(#{uid}scl)"/>'
        f'<g fill="none" stroke-linecap="round">{caps_svg}</g>'
        f'<g><animateTransform attributeName="transform" type="translate" values="{vals}" keyTimes="{kt}" dur="11s" repeatCount="indefinite"/>'
        f'<circle cx="{ex}" cy="{ey}" r="{ir*1.25:.1f}" fill="{C["red"]}" opacity=".55" filter="url(#{uid}glow)"/>'
        f'<circle cx="{ex}" cy="{ey}" r="{ir:.1f}" fill="url(#{uid}iris)"/>' + "".join(fib) + crypts +
        f'<polygon points="{collar}" fill="none" stroke="#ffb090" stroke-width="{.7*s:.2f}" opacity=".55"/>'
        f'<circle cx="{ex}" cy="{ey}" r="{ir:.1f}" fill="none" stroke="#1a0004" stroke-width="{3*s:.1f}"/>'
        f'<circle cx="{ex}" cy="{ey}" r="{ir-2.2*s:.1f}" fill="none" stroke="#000" stroke-width="{1*s:.1f}" opacity=".5"/>'
        # pupil: dilates, contracts, and every so often pinches into a slit
        f'<ellipse cx="{ex}" cy="{ey}" rx="{7*s:.1f}" ry="{7*s:.1f}" fill="#000">'
        f'<animate attributeName="rx" values="{7*s:.1f};{5*s:.1f};{5*s:.1f};{1.8*s:.1f};{1.8*s:.1f};{9.5*s:.1f};{7*s:.1f}" '
        f'keyTimes="0;.15;.4;.45;.62;.72;1" dur="13s" repeatCount="indefinite"/>'
        f'<animate attributeName="ry" values="{7*s:.1f};{5*s:.1f};{5*s:.1f};{9*s:.1f};{9*s:.1f};{9.5*s:.1f};{7*s:.1f}" '
        f'keyTimes="0;.15;.4;.45;.62;.72;1" dur="13s" repeatCount="indefinite"/></ellipse>'
        f'<ellipse cx="{ex+7*s:.1f}" cy="{ey-8*s:.1f}" rx="{3.4*s:.1f}" ry="{2.4*s:.1f}" fill="#fff" opacity=".92"/>'
        f'<circle cx="{ex-6*s:.1f}" cy="{ey+7*s:.1f}" r="{1.2*s:.1f}" fill="#fff" opacity=".55"/></g>'
        # wet line along the lower lid and shadow from the upper lid
        f'<path d="{eye}" fill="url(#{uid}shade)"/>'
        f'<path d="M{L[0]+8*s:.1f} {ey+3*s:.1f} Q{ex} {ey+hh-5*s:.1f} {R[0]-8*s:.1f} {ey+3*s:.1f}" fill="none" stroke="#fff" '
        f'stroke-width="{.8*s:.2f}" opacity=".18"/>'
        # eyelids: parked outside the eye, they snap shut for ~0.1 s; a double blink near the end
        f'<g><animateTransform attributeName="transform" type="translate" '
        f'values="0 {-hh};0 {-hh};0 0;0 {-hh};0 {-hh};0 0;0 {-hh};0 0;0 {-hh};0 {-hh}" '
        f'keyTimes="{blink_k}" dur="9s" repeatCount="indefinite"/>'
        f'<rect x="{L[0]}" y="{ey-hh}" width="{2*hw}" height="{hh}" fill="#120a0a"/>'
        f'<path d="M{L[0]} {ey} Q{ex} {ey+7*s:.1f} {R[0]} {ey}" fill="none" stroke="{C["paper"]}" stroke-width="{1.5*s:.1f}"/></g>'
        f'<g><animateTransform attributeName="transform" type="translate" '
        f'values="0 {hh};0 {hh};0 0;0 {hh};0 {hh};0 0;0 {hh};0 0;0 {hh};0 {hh}" '
        f'keyTimes="{blink_k}" dur="9s" repeatCount="indefinite"/>'
        f'<rect x="{L[0]}" y="{ey}" width="{2*hw}" height="{hh}" fill="#120a0a"/></g>'
        f'</g>')
    # lid rims and lashes
    out.append(f'<path d="M{L[0]} {ey} Q{ex} {ey-hh} {R[0]} {ey}" fill="none" stroke="{C["paper"]}" stroke-width="{2.2*s:.1f}" stroke-linecap="round"/>')
    out.append(f'<path d="M{L[0]} {ey} Q{ex} {ey+hh} {R[0]} {ey}" fill="none" stroke="{C["text"]}" stroke-width="{1.1*s:.1f}" opacity=".8"/>')
    lashes = []
    for k in range(26):
        t = .06 + k * .88 / 25
        px, py = _qpt(L, T, R, t)
        tx, ty = 2 * ((1 - t) * (T[0] - L[0]) + t * (R[0] - T[0])), 2 * ((1 - t) * (T[1] - L[1]) + t * (R[1] - T[1]))
        n = math.hypot(tx, ty)
        nx, ny = ty / n, -tx / n
        lean = (t - .5) * 1.6
        ln = (3 + 9 * t * t + rng.uniform(-1, 2)) * s
        bend = rng.uniform(.6, 1.2)
        lashes.append(f'M{px:.1f} {py:.1f} q{(nx*.6)*ln:.1f} {ny*ln*.7:.1f} {(nx+lean*bend)*ln:.1f} {ny*ln*.55:.1f}')
    low = []
    for k in range(7):
        t = .55 + k * .35 / 6
        px, py = _qpt(L, B, R, t)
        ln = (2 + rng.uniform(0, 2.5)) * s
        low.append(f'M{px:.1f} {py:.1f} l{(t-.5)*ln*1.5:.1f} {ln:.1f}')
    out.append(f'<path d="{" ".join(lashes)}" fill="none" stroke="#1a1414" stroke-width="{1.5*s:.2f}" stroke-linecap="round"/>')
    out.append(f'<path d="{" ".join(lashes)}" fill="none" stroke="{C["muted"]}" stroke-width="{.75*s:.2f}" stroke-linecap="round"/>')
    out.append(f'<path d="{" ".join(low)}" fill="none" stroke="{C["dim"]}" stroke-width="{.6*s:.2f}" stroke-linecap="round"/>')
    # a tear of blood from the lower lid, slowly running down the cheek
    tx0, ty0 = _qpt(L, B, R, .3)
    trail = f"M{tx0:.1f} {ty0:.1f} q{-2*s:.1f} {18*s:.1f} {1*s:.1f} {34*s:.1f} t{-1*s:.1f} {30*s:.1f}"
    ln = 70 * s
    out.append(f'<path d="{trail}" fill="none" stroke="{C["red"]}" stroke-width="{2.4*s:.1f}" stroke-linecap="round" '
               f'stroke-dasharray="{ln:.0f} {ln:.0f}" stroke-dashoffset="{ln*.55:.0f}">'
               f'<animate attributeName="stroke-dashoffset" values="{ln*.55:.0f};0;0;{ln*.55:.0f}" keyTimes="0;.6;.9;1" dur="16s" repeatCount="indefinite"/>'
               f'<animate attributeName="opacity" values="1;1;0;1" keyTimes="0;.85;.99;1" dur="16s" repeatCount="indefinite"/></path>')
    eye_svg = "".join(out)
    # an occasional twitch of the whole eye
    eye_svg = (f'<g>{eye_svg}<animateTransform attributeName="transform" type="translate" '
               f'values="0 0;0 0;{1.5*s:.1f} {-1*s:.1f};{-1.2*s:.1f} {1*s:.1f};{.8*s:.1f} 0;0 0;0 0" '
               f'keyTimes="0;.61;.615;.62;.625;.63;1" dur="13s" repeatCount="indefinite"/></g>')
    return defs, eye_svg


def footer_card(mobile=False):
    depth, layer = LAYERS[6]
    if mobile:
        W, H = 480, 420
        defs, eye = kakugan(240, 130, 1.35)
        body = [
            wires(W, 10, ".4"), eye,
            text(W / 2, 282, "El Psy Kongroo.", "play", 32, C["paper"], "middle"),
            f'<g transform="rotate(180 240 316)">' + text(240, 321, "CLOSE THE WORLD, OPEN THE NEXT", "bebas", 18, C["muted"], "middle", ls=3) + "</g>",
            text(W / 2, 360, f"LAYER:07  ·  {layer}", "plex", 11.5, C["dim"], "middle", ls=2),
            text(W / 2, 378, f"DEPTH {depth}  ·  NO ASCENT WITHOUT A PRICE", "plex", 11, C["dim"], "middle", ls=1),
            f'<line x1="90" y1="398" x2="390" y2="398" stroke="{C["line"]}"/>',
            f'<rect x="236" y="395" width="8" height="6" fill="{C["red"]}"/>',
        ]
        return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), defs, title="El Psy Kongroo. Close the world, open the next.")
    W, H = 1000, 370
    defs, eye = kakugan(500, 132, 1.6)
    body = [
        wires(W, 10, ".4"), eye,
        text(W / 2, 270, "El Psy Kongroo.", "play", 28, C["paper"], "middle"),
        f'<g transform="rotate(180 500 298)">' + text(500, 303, "CLOSE THE WORLD, OPEN THE NEXT", "bebas", 15, C["muted"], "middle", ls=4) + "</g>",
        text(W / 2, 334, f"LAYER:07  ·  {layer}  ·  DEPTH {depth}  ·  NO ASCENT WITHOUT A PRICE", "plex", 9, C["dim"], "middle", ls=2),
        f'<line x1="300" y1="350" x2="700" y2="350" stroke="{C["line"]}"/>',
        f'<rect x="496" y="347" width="8" height="6" fill="{C["red"]}"/>',
    ]
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), defs, title="El Psy Kongroo. Close the world, open the next.")


# --------------------------------------------------------------------------- #
# Contact: one small SVG per link, so each one can be clicked
# --------------------------------------------------------------------------- #
CONTACT = [
    ("website", "WEB", "harshulkala.dpdns.org", "SEND D-MAIL"),
    ("linkedin", "LINKEDIN", "haru-l41n-pr0t0", "OPEN CHANNEL"),
    ("discord", "DISCORD", "lain_0x00.navi", "ADD ON DISCORD"),
]
RING = [("ring-prev", "← PREV"), ("ring-home", "OCTO RING"), ("ring-random", "RANDOM"), ("ring-next", "NEXT →")]


def contact_button(label, value, verb):
    W, H = max(300, int(len(value) * 9.6 + 70)), 64
    body = [
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="6" fill="{C["ink"]}" stroke="{C["line"]}" stroke-width="1.5"/>',
        f'<rect x="1" y="1" width="5" height="{H-2}" fill="{C["red"]}"/>',
        text(20, 24, f"> {verb}", "plex", 10, C["muted"], ls=2),
        text(W - 14, 24, label, "bebas", 15, C["red_hi"], "end", ls=3),
        f'<text x="20" y="48" class="plex" font-size="16"><tspan fill="{C["red_hi"]}">$ </tspan>'
        f'<tspan fill="{C["paper"]}">{esc(value)}</tspan></text>',
        f'<rect x="{20 + (len(value) + 2) * 9.6 + 3:.0f}" y="35" width="9" height="16" fill="{C["paper"]}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" repeatCount="indefinite"/></rect>',
    ]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="{esc(label)}: {esc(value)}"><title>{esc(label)}: {esc(value)}</title>'
            f'<style>{font_css(("Bebas", "Plex"))}{BASE_CSS}</style>' + "".join(body) + "</svg>\n")


def ring_button(label):
    W, H = int(len(label) * 9 + 36), 40
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="{esc(label)}"><title>{esc(label)}</title><style>{font_css(("Plex",))}{BASE_CSS}</style>'
            f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="20" fill="{C["ink"]}" stroke="{C["line"]}" stroke-width="1.5"/>'
            + text(W / 2, 25, label, "plex", 13, C["text"], "middle", ls=1.5) + "</svg>\n")


# --------------------------------------------------------------------------- #
# Phone versions. A 1000-wide card squeezed onto a 390 px screen turns 9 px text
# into 3.5 px. These are drawn 480 wide with body text at 13 or more, so text
# lands at 10 px or bigger. README swaps them in with <picture media=...>.
# --------------------------------------------------------------------------- #
MW = 480


def hero_m(st, stats):
    p = st.get("profile", {})
    sysd = st.get("system", {})
    img = ASSETS / "img"
    W = MW
    defs = f"""<filter id="duo" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .07 .72 .9"/><feFuncG type="table" tableValues=".04 .07 .71 .89"/>
<feFuncB type="table" tableValues=".04 .07 .69 .87"/></feComponentTransfer></filter>
<clipPath id="pclip"><polygon points="40,20 460,20 440,330 20,330"/></clipPath>
<linearGradient id="fadeB" x1="0" y1="0" x2="0" y2="1"><stop offset=".5" stop-color="{C['ink']}" stop-opacity="0"/>
<stop offset="1" stop-color="{C['ink']}" stop-opacity=".95"/></linearGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".55"/></pattern>
<filter id="pulse" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="0">
<animate attributeName="stdDeviation" values="0;1.3;0" dur="3s" repeatCount="indefinite"/></feGaussianBlur></filter>"""
    b = [f'<g clip-path="url(#pclip)"><image x="20" y="-170" width="440" height="782" preserveAspectRatio="xMidYMin slice" '
         f'xlink:href="{b64(img / "portrait.jpg", "image/jpeg")}" filter="url(#duo)"/>'
         f'<rect x="20" y="20" width="440" height="310" fill="url(#scan)" opacity=".35"/>'
         f'<rect x="20" y="20" width="440" height="310" fill="url(#fadeB)"/></g>',
         f'<polygon points="40,20 460,20 440,330 20,330" fill="none" stroke="{C["paper"]}" stroke-width="1.5"/>',
         wires(W, 14, ".55"),
         text(56, 58, "PRESENT DAY", "bebas", 26, C["paper"], ls=1.5),
         text(56, 84, "PRESENT TIME", "bebas", 26, C["paper"], ls=1.5),
         text(W / 2, 312, clean(p.get("quote", "")), "play", 18, C["paper"], "middle", extra='filter="url(#pulse)"')]
    b.append(f'<g transform="rotate(-6 240 262)"><rect x="10" y="246" width="460" height="32" fill="{C["red"]}" opacity=".92"/>'
             + text(240, 268, clean(p.get("name", "")).upper(), "cut", 18, C["paper"], "middle", ls=3) + "</g>")
    y = 372
    b.append(text(20, y, f"@{p.get('handle', USER).upper()}  //  LAYER:01", "plex", 12, C["muted"], ls=2))
    first, _, rest = clean(p.get("name", "")).partition("|")
    b.append(f'<text x="20" y="{y+46}" class="bebas" font-size="46" letter-spacing="1"><tspan fill="{C["paper"]}">{esc(first.strip().upper())}</tspan>'
             + (f'<tspan fill="{C["red_hi"]}"> | {esc(rest.strip().upper())}</tspan>' if rest else "") + "</text>")
    b.append(text(20, y + 72, clean(p.get("tagline", "")).upper(), "plex", 13, C["text"], ls=1.5))
    b.append(text(20, y + 98, clean(p.get("school_line", "")).upper(), "bebas", 19, C["red_hi"], ls=2))
    os_short = clean(sysd.get("os", "Linux")).split(" ")[0]
    de_short = re.sub(r"\s*[\d.]+.*$", "", clean(sysd.get("desktop", "")))
    sh_short = clean(sysd.get("shell", "")).split(" ")[0]
    b.append(text(20, y + 120, " · ".join(x for x in [os_short, de_short, sh_short] if x).upper(), "plex", 12, C["muted"], ls=2))
    y += 146
    b.append(f'<line x1="20" y1="{y}" x2="460" y2="{y}" stroke="{C["line"]}"/>')
    y += 30
    for line in wrap(clean(p.get("bio", "")), 50, 8):
        b.append(text(20, y, line, "plex", 14, C["text"]))
        y += 22
    y += 14
    dv = str(st.get("signal", {}).get("divergence", "1.048596"))[:8]
    rank, cleared = whistle_rank(stats.get("contributions"))
    b.append(f'<text x="20" y="{y}" class="plex" font-size="12" letter-spacing="1.5"><tspan fill="{C["muted"]}">DIVERGENCE </tspan>'
             f'<tspan fill="{C["nixie"]}">{esc(dv)}</tspan><tspan fill="{C["muted"]}">  ·  WHISTLE </tspan>'
             f'<tspan fill="{C["red_hi"]}">{rank.upper()}</tspan></text>')
    y += 22
    b.append(text(20, y, f"{clean(p.get('location','')).upper()}  ·  {p.get('timezone','')}", "plex", 12, C["dim"], ls=2))
    H = y + 26
    title = f"{p.get('name','')} ({USER}): {clean(p.get('bio',''))}"
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex", "Playfair", "Cutive"), defs, title)


def section_header_m(n):
    W, H = MW, 112
    depth, layer = LAYERS[n - 1]
    title, kicker = SECTIONS[n - 1]
    stitches = " ".join(f"M{x} 94l6 10" for x in range(22, 458, 13))
    body = [
        text(20, 34, f"LAYER:{n:02d}", "bebas", 22, C["red_hi"], ls=4),
        text(460, 33, f"{n:02d} / {len(SECTIONS):02d}  ·  {kicker}", "plex", 11, C["text"], "end", ls=1.5),
        text(20, 70, title, "play", 30, C["paper"]),
        text(460, 70, depth, "plex", 11, C["muted"], "end", ls=1),
        f'<path d="M20 98H460" stroke="{C["line"]}" stroke-width="1.5"/>',
        f'<path d="{stitches}" stroke="{C["dim"]}" stroke-width="1.3" stroke-linecap="round"/>',
        f'<rect x="20" y="96" width="{30 + n*14}" height="4" fill="{C["red"]}"/>',
    ]
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), title=f"Layer {n:02d}: {title} ({kicker.lower()}), {layer.lower()}")


def about_m(st):
    a = st.get("about", {})
    W, b, y = MW, [], 52
    for line in wrap(clean(a.get("statement", "")), 34):
        b.append(text(20, y, line, "play", 23, C["paper"]))
        y += 32
    y += 8
    for line in wrap(clean(a.get("detail", "")), 50):
        b.append(text(20, y, line, "plex", 14, C["text"]))
        y += 22
    y += 18
    for key, label in [("based_in", "BASED IN"), ("studying", "STUDYING"), ("now", "NOW SOLVING"),
                       ("research", "RESEARCH"), ("exploring", "EXPLORING")]:
        if not a.get(key):
            continue
        b.append(f'<line x1="20" y1="{y-6}" x2="460" y2="{y-6}" stroke="{C["line"]}" stroke-dasharray="2 4"/>')
        y += 16
        b.append(text(20, y, label, "plex", 11.5, C["red_hi"], ls=3))
        y += 22
        for line in wrap(clean(a[key]), 50):
            b.append(text(20, y, line, "plex", 14, C["paper"]))
            y += 21
        y += 12
    backlog = st.get("backlog", []) or []
    if backlog:
        y += 8
        b.append(text(20, y, "STAGED PROTOCOLS / BACKLOG", "plex", 11.5, C["red_hi"], ls=3))
        y += 24
        for item in backlog:
            for j, line in enumerate(wrap(clean(item), 46)):
                if j == 0:
                    b.append(text(20, y, "—", "plex", 14, C["red"]))
                b.append(text(44, y, line, "plex", 14, C["text"]))
                y += 21
            y += 4
    H = y + 14
    desc = " ".join(clean(a.get(k, "")) for k in ("statement", "detail", "based_in", "studying", "now", "research", "exploring"))
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex", "Playfair"), title=f"About: {desc}")


def toolkit_m(st):
    groups = st.get("toolkit", {})
    W, b, y = MW, [], 40
    for gi, (group, items) in enumerate(groups.items()):
        b.append(text(20, y, clean(group).upper(), "bebas", 20, C["red_hi"], ls=3))
        b.append(text(460, y, f"0{gi+1}", "plex", 11, C["dim"], "end", ls=2))
        y += 34
        x = 20
        for it in items or []:
            primary = it.endswith("*")
            it = clean(it.rstrip("*"))
            w = len(it) * 8.4 + 26
            if x + w > 460:
                x = 20
                y += 40
            stroke = C["red_hi"] if primary else C["line"]
            b.append(f'<rect x="{x}" y="{y-20}" width="{w:.0f}" height="30" rx="3" fill="{C["panel"]}" stroke="{stroke}"/>')
            b.append(text(x + w / 2, y, it, "plex", 14, C["paper"] if primary else C["text"], "middle"))
            x += w + 8
        y += 46
    H = y + 4
    b.append(text(460, H - 16, "OUTLINED = PRIMARY", "plex", 10, C["dim"], "end", ls=2))
    flat = "; ".join(f"{g}: " + ", ".join(i.rstrip('*') for i in v) for g, v in groups.items())
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex"), title=f"Toolkit. {flat}")


def system_m(st):
    s = st.get("system", {})
    rows = [(k, s.get(v)) for k, v in [("OS", "os"), ("KERNEL", "kernel"), ("MACHINE", "machine"), ("DESKTOP", "desktop"),
                                         ("SHELL", "shell"), ("TERMINAL", "terminal"), ("CPU", "cpu"), ("GPU", "gpu"),
                                         ("MEMORY", "memory"), ("FILESYSTEM", "filesystem")] if s.get(v)]
    W = MW
    b = [f'<circle cx="70" cy="70" r="44" fill="none" stroke="{C["line"]}"/>',
         f'<circle cx="70" cy="70" r="49" fill="none" stroke="{C["red"]}" stroke-dasharray="1 5"/>',
         f'<image x="32" y="32" width="76" height="76" xlink:href="{b64(ASSETS / "img" / "navi.png", "image/png")}" filter="url(#duo2)"/>',
         f'<text x="140" y="64" class="plex" font-size="17"><tspan fill="{C["red_hi"]}">{esc(s.get("user",""))}</tspan>'
         f'<tspan fill="{C["dim"]}">@</tspan><tspan fill="{C["paper"]}">{esc(s.get("host",""))}</tspan></text>',
         text(140, 90, "NAVI  ·  COPLAND OS ENTERPRISE", "plex", 11, C["dim"], ls=1.5)]
    y = 150
    for k, v in rows:
        b.append(f'<line x1="20" y1="{y-20}" x2="460" y2="{y-20}" stroke="{C["line"]}" stroke-dasharray="2 4"/>')
        b.append(text(20, y, k, "bebas", 17, C["red"], ls=3))
        lines = wrap(clean(v), 34, 2)
        for j, line in enumerate(lines):
            b.append(text(140, y + j * 20, line, "plex", 14, C["paper"]))
        y += 20 * len(lines) + 20
    for i, col in enumerate([C["ink"], C["dim"], C["red"], C["red_hi"], C["muted"], C["text"], C["paper"], C["nixie"]]):
        b.append(f'<rect x="{20 + i*30}" y="{y-8}" width="26" height="12" fill="{col}" stroke="{C["line"]}"/>')
    y += 34
    b.append(text(20, y, "SPECS READ FROM FASTFETCH · " + clean(s.get("synced", "")), "plex", 10.5, C["dim"], ls=1.5))
    H = y + 22
    duo = f"""<filter id="duo2" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/>
<feComponentTransfer><feFuncR type="table" tableValues=".04 .95"/><feFuncG type="table" tableValues=".04 .15"/>
<feFuncB type="table" tableValues=".04 .25"/></feComponentTransfer></filter>"""
    title = "System. " + "; ".join(f"{k.title()}: {v}" for k, v in rows)
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex"), duo, title)


def project_m(i, r, tagline, summary, title):
    W = MW
    b = [text(20, 36, f"PINNED · {i:02d}", "bebas", 18, C["red_hi"], ls=4),
         text(460, 35, f"WORLD LINE {world_line(r['name'])}", "plex", 11, C["nixie"], "end", ls=1.5)]
    name_fs = 40 if len(r["name"]) <= 18 else 34
    b.append(text(20, 80, r["name"], "bebas", name_fs, C["paper"], ls=1))
    y = 110
    for line in wrap(tagline, 40, 2):
        b.append(text(20, y, line, "play", 18, C["text"]))
        y += 24
    y += 4
    for line in (wrap(summary, 52, 4) if summary else []):
        b.append(text(20, y, line, "plex", 13, C["muted"]))
        y += 20
    if r.get("topics"):
        x, y = 20, y + 14
        for t in r["topics"][:6]:
            t = clean(t)
            w = len(t) * 7.2 + 18
            if x + w > 460:
                x, y = 20, y + 32
            b.append(f'<rect x="{x}" y="{y-16}" width="{w:.0f}" height="24" rx="2" fill="none" stroke="{C["line"]}"/>')
            b.append(text(x + w / 2, y, t, "plex", 12, C["text"], "middle"))
            x += w + 8
        y += 16
    y += 18
    b.append(f'<line x1="20" y1="{y}" x2="460" y2="{y}" stroke="{C["line"]}"/>')
    y += 28
    b.append(text(20, y, "COMPOSITION", "plex", 11, C["muted"], ls=3))
    b.append(text(460, y, (r.get("pushed") or "")[:10], "plex", 11, C["text"], "end", ls=1.5))
    y += 12
    langs = r.get("languages") or []
    x = 20
    for j, (name, frac) in enumerate(langs):
        w = max(2, 440 * frac)
        b.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="8" fill="{RAMP[j % 5]}"/>')
        x += w
    if not langs:
        b.append(f'<rect x="20" y="{y}" width="440" height="8" fill="{C["line"]}"/>')
    y += 34
    for j, (name, frac) in enumerate(langs[:4]):
        lx, ly = 20 + (j % 2) * 220, y + (j // 2) * 24
        b.append(f'<rect x="{lx}" y="{ly-10}" width="10" height="10" fill="{RAMP[j % 5]}"/>')
        b.append(text(lx + 18, ly, f"{clean(name)} {frac*100:.1f}%", "plex", 13, C["text"]))
    y += 24 * ((min(len(langs), 4) + 1) // 2) + 10
    b.append(text(20, y, f"STARS {r.get('stars',0)}  ·  FORKS {r.get('forks',0)}", "plex", 12, C["text"], ls=1.5))
    b.append(text(460, y, "OPEN →", "plex", 12, C["red_hi"], "end", ls=2))
    H = y + 24
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex", "Playfair"), title=title)


def abyss_mobile(rows, here, defs, mapb, tops, rank, cleared, cur, contrib, title):
    W = MW
    # the map spans x 30..500 of the desktop frame; shift it into the phone frame
    b = [text(20, 40, "HARSHUL'S DESCENT", "bebas", 32, C["paper"], ls=2),
         text(20, 60, "ONE LAYER PER STEP OF THE WAY DOWN", "plex", 11, C["muted"], ls=1),
         f'<g transform="translate(-25 50)">' + "".join(mapb) + "</g>"]
    y = 800
    for i, (depth, layer) in enumerate(LAYERS):
        step, when, cost = rows[i]
        on = here == i + 1
        b.append(f'<line x1="20" y1="{y-24}" x2="460" y2="{y-24}" stroke="{C["red"] if on else C["line"]}" stroke-dasharray="2 4"/>')
        b.append(text(20, y, f"L{i+1}", "bebas", 24, C["red_hi"], ls=1))
        b.append(text(58, y, layer, "bebas", 20, C["paper"], ls=1.5))
        b.append(text(460, y, (when or depth).upper(), "plex", 11, C["red_hi"] if on else C["muted"], "end", ls=1))
        y += 24
        for line in wrap(step, 48, 2):
            b.append(text(58, y, line, "plex", 14, C["paper"] if on else C["text"]))
            y += 21
        if cost:
            b.append(f'<text x="58" y="{y}" class="plex" font-size="12"><tspan fill="{C["dim"]}">COST  </tspan>'
                     f'<tspan fill="{C["muted"]}">{esc(clip(cost, 44))}</tspan></text>')
            y += 20
        y += 26
    b.append(f'<line x1="20" y1="{y-10}" x2="460" y2="{y-10}" stroke="{C["line"]}"/>')
    y += 18
    b.append(text(20, y, "WHISTLE RANK", "plex", 12, C["red_hi"], ls=3))
    y += 30
    b.append(text(20, y, f"{rank} whistle, {cleared}.", "play", 22, C["paper"]))
    y += 22
    b.append(text(20, y, f"From {contrib if contrib is not None else 'unknown'} contributions in 12 months.", "plex", 12, C["muted"]))
    y += 34
    for k, (name, need, _) in enumerate(WHISTLES):
        x, yy = 20 + (k % 3) * 150, y + (k // 3) * 64
        col = C["red"] if k == cur else (C["paper"] if k < cur else C["dim"])
        b.append(f'<circle cx="{x+6}" cy="{yy}" r="6" fill="none" stroke="{col}" stroke-width="1.6"/>')
        b.append(f'<rect x="{x+12}" y="{yy-6}" width="52" height="12" rx="6" fill="{C["red"] if k == cur else "none"}" stroke="{col}" stroke-width="1.6"/>')
        b.append(text(x, yy + 28, name.upper(), "bebas", 19, C["paper"] if k <= cur else C["dim"], ls=2))
        b.append(text(x + 62, yy + 28, f"{need}+", "plex", 11, C["muted"] if k <= cur else C["dim"]))
    H = y + 64 + 52
    return svg_doc(W, H, "\n".join(b), ("Bebas", "Plex", "Playfair"), defs, title)


# --------------------------------------------------------------------------- #
# README pinned block
# --------------------------------------------------------------------------- #
def picture(path, alt):
    """Phone card by default; wide screens opt into the desktop card. Viewers that ignore
    <source> (the GitHub app) then get the readable phone card, not a shrunken desktop one."""
    return (f'<picture><source media="(min-width: 701px)" srcset="assets/{path}">'
            f'<img src="assets/m/{path}" width="100%" alt="{alt}"></picture>')


def update_readme_pinned(pinned):
    if not README.exists():
        return
    src = README.read_text(encoding="utf-8")
    start, end = "<!--PINNED:START-->", "<!--PINNED:END-->"
    if start not in src or end not in src:
        print("  pinned markers missing in README.md")
        return
    if pinned:
        parts = [f'<a href="{r["url"]}">{picture(f"pinned/{r["name"]}.svg", f"{esc(r["name"])} repository card")}</a>'
                 for r in pinned]
        block = "\n" + "\n".join(parts) + "\n"
    else:
        block = "\n<sub>No pinned repositories right now.</sub>\n"
    new = re.sub(re.escape(start) + ".*?" + re.escape(end), lambda _: start + block + end, src, flags=re.S)
    if new != src:
        README.write_text(new, encoding="utf-8")
        print("  updated README.md pinned block")


# --------------------------------------------------------------------------- #
# --sync-system: read this machine into status.yml
# --------------------------------------------------------------------------- #
def sync_system():
    try:
        mods = {m["type"]: m.get("result") for m in json.loads(subprocess.check_output(
            ["fastfetch", "--format", "json", "-s", "os:kernel:host:de:wm:cpu:gpu:memory:disk:terminal"], text=True))}
    except Exception as e:
        sys.exit(f"fastfetch failed: {e}")
    import pwd
    import socket

    pw = pwd.getpwuid(os.getuid())
    login_shell = pw.pw_shell
    shell = os.path.basename(login_shell)
    try:
        ver = subprocess.check_output([login_shell, "--version"], text=True).splitlines()[0]
        m = re.search(r"(\d+\.\d+(\.\d+)?)", ver)
        if m:
            shell = f"{shell} {m.group(1)}"
    except Exception:
        pass
    osr, ker, host = mods.get("OS") or {}, mods.get("Kernel") or {}, mods.get("Host") or {}
    de, wm, cpu = mods.get("DE") or {}, mods.get("WM") or {}, mods.get("CPU") or {}
    gpus = mods.get("GPU") or []
    mem = (mods.get("Memory") or {}).get("total", 0)
    root = next((d for d in (mods.get("Disk") or []) if d.get("mountpoint") == "/"), {})
    term = mods.get("Terminal") or {}
    cores = cpu.get("cores", {})
    cpu_name = re.sub(r"\((R|TM)\)|\d+th Gen ", "", cpu.get("cpu", "")).strip()
    cpu_name = re.sub(r"\s+", " ", cpu_name)
    fields = {
        "user": pw.pw_name,
        "host": socket.gethostname(),
        "os": f"{osr.get('prettyName','')} {ker.get('architecture','')}".strip(),
        "kernel": f"{ker.get('name','')} {ker.get('release','')}".strip(),
        "machine": f"{host.get('vendor','').title()} {host.get('family','')}".strip(),
        "desktop": f"{de.get('prettyName','')} {de.get('version','')} ({wm.get('protocolName','')})".replace(" ()", ""),
        "shell": shell,
        "cpu": f"{cpu_name} ({cores.get('physical', '?')}C/{cores.get('logical', '?')}T)",
        "gpu": " + ".join(re.sub(r"GeForce |Raptor Lake-S |Alder Lake-\w+ ", "", f"{g.get('vendor','')} {g.get('name','')}").strip()
                          for g in gpus),
        "memory": f"{round(mem / 2**30)} GiB" if mem else "",
        "filesystem": root.get("filesystem", ""),
        "synced": dt.date.today().isoformat(),
    }
    tname = term.get("prettyName", "")
    if tname and tname not in ("claude", "bash", "fish", "zsh", "sh") and "code" not in tname.lower():
        fields["terminal"] = f"{tname} {term.get('version','')}".strip()
    else:
        old = load_status().get("system", {}).get("terminal")
        if old:
            fields["terminal"] = old

    lines = STATUS.read_text(encoding="utf-8").splitlines() if STATUS.exists() else []
    block = ["system:  # written by `python build.py --sync-system`"] + [f'  {k}: "{v}"' for k, v in fields.items() if v]
    out, i, done = [], 0, False
    while i < len(lines):
        if re.match(r"^system:", lines[i]):
            out += block
            done = True
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                i += 1
            out.append("")
            continue
        out.append(lines[i])
        i += 1
    if not done:
        out += [""] + block
    STATUS.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print("status.yml system block updated:")
    for k, v in fields.items():
        print(f"  {k:<11} {v}")


# --------------------------------------------------------------------------- #
def main():
    if "--sync-system" in sys.argv:
        sync_system()
    st = load_status()
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    print("fetching GitHub data" + (" (skipped, offline)" if OFFLINE else ""))
    stats, pinned = fetch_github()

    print("rendering cards")
    M = ASSETS / "m"
    write(ASSETS / "hero.svg", hero(st, stats, today))
    write(M / "hero.svg", hero_m(st, stats))
    write(ASSETS / "abyss.svg", abyss_card(st, stats))
    write(M / "abyss.svg", abyss_card(st, stats, mobile=True))
    for n in range(1, len(SECTIONS) + 1):
        write(ASSETS / f"layer-{n:02d}.svg", section_header(n))
        write(M / f"layer-{n:02d}.svg", section_header_m(n))
    write(ASSETS / "about.svg", about_card(st))
    write(M / "about.svg", about_m(st))
    write(ASSETS / "toolkit.svg", toolkit_card(st))
    write(M / "toolkit.svg", toolkit_m(st))
    write(ASSETS / "system.svg", system_card(st))
    write(M / "system.svg", system_m(st))
    write(ASSETS / "signal.svg", signal_card(st, stats, today))
    write(M / "signal.svg", signal_card(st, stats, today, mobile=True))
    write(ASSETS / "footer.svg", footer_card())
    write(M / "footer.svg", footer_card(mobile=True))
    for name, label, value, verb in CONTACT:
        write(ASSETS / "contact" / f"{name}.svg", contact_button(label, value, verb))
    for name, label in RING:
        write(ASSETS / "contact" / f"{name}.svg", ring_button(label))

    if pinned is not None:
        overrides = st.get("pinned_overrides", {}) or {}
        keep = set()
        for i, r in enumerate(pinned, 1):
            ov = overrides.get(r["name"], {}) or {}
            write(PINNED_DIR / f"{r['name']}.svg", project_card(i, r, ov))
            write(ASSETS / "m" / "pinned" / f"{r['name']}.svg", project_card(i, r, ov, mobile=True))
            keep.add(f"{r['name']}.svg")
        for d in (PINNED_DIR, ASSETS / "m" / "pinned"):
            for f in (d.glob("*.svg") if d.exists() else []):
                if f.name not in keep:
                    f.unlink()
                    print(f"  removed stale {f.relative_to(ROOT)}")
        update_readme_pinned(pinned)
    print("done")


if __name__ == "__main__":
    main()
