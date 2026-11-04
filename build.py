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


def abyss_card(stats):
    """An original cross-section of the Abyss; each layer maps to a README section."""
    W, H = 1000, 800
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

    # Right side: the layer log
    b.append(text(540, 54, "THE ABYSS", "bebas", 32, C["paper"], ls=3))
    b.append(text(964, 46, "DESCENT MAP", "plex", 9, C["red_hi"], "end", ls=3))
    b.append(text(964, 62, "EACH SECTION BELOW IS ONE LAYER DEEPER", "plex", 8.5, C["muted"], "end", ls=1))
    for i, (depth, layer) in enumerate(LAYERS):
        y0 = tops[i] + 22
        target = f"{i+1:02d}  {SECTIONS[i][0].upper()}" if i < len(SECTIONS) else "END OF PAGE"
        b.append(f'<path d="M504 {y0-5}H532" stroke="{C["line"]}" stroke-dasharray="2 3"/>')
        b.append(text(540, y0, f"L{i+1}", "bebas", 20, C["red_hi"], ls=1))
        b.append(text(574, y0, layer, "bebas", 17, C["paper"], ls=2))
        b.append(text(964, y0, depth, "plex", 9, C["muted"], "end", ls=1))
        b.append(f'<text x="574" y="{y0+17}" class="plex" font-size="9.5"><tspan fill="{C["dim"]}">ASCENT  </tspan>'
                 f'<tspan fill="{C["text"]}">{esc(CURSE[i])}</tspan></text>')
        b.append(text(574, y0 + 33, f"→ {target}", "plex", 9, C["red_hi"], ls=1))

    # Whistle ranks
    contrib = stats.get("contributions")
    rank, cleared = whistle_rank(contrib)
    b.append(f'<line x1="36" y1="700" x2="964" y2="700" stroke="{C["line"]}"/>')
    b.append(text(36, 728, "WHISTLE RANK", "plex", 9, C["red_hi"], ls=3))
    b.append(text(36, 752, f"{rank} whistle, {cleared}.", "play", 17, C["paper"]))
    b.append(text(36, 774, f"Earned from {contrib if contrib is not None else 'unknown'} contributions in 12 months.",
                  "plex", 9, C["muted"]))
    cur = [w[0] for w in WHISTLES].index(rank)
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

    title = ("The Abyss, a descent map. " + "; ".join(f"Layer {i+1}, {l.title()}, {d}: ascent causes {CURSE[i]}"
             for i, (d, l) in enumerate(LAYERS)) + f". Whistle rank: {rank}.")
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


def project_card(i, r, override):
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


def signal_card(st, stats, today):
    W, H = 1000, 320
    dv = str(st.get("signal", {}).get("divergence", "1.048596"))[:8]
    defs = f"""<filter id="nglow" x="-60%" y="-30%" width="220%" height="160%"><feGaussianBlur stdDeviation="4" result="a"/>
<feGaussianBlur in="SourceGraphic" stdDeviation="1" result="b"/><feMerge><feMergeNode in="a"/><feMergeNode in="a"/>
<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".09"/>
<stop offset=".25" stop-color="#fff" stop-opacity=".02"/><stop offset=".8" stop-color="#fff" stop-opacity="0"/>
<stop offset="1" stop-color="#fff" stop-opacity=".06"/></linearGradient>
<radialGradient id="warm" cx=".5" cy=".55" r=".6"><stop offset="0" stop-color="{C['nixie']}" stop-opacity=".22"/>
<stop offset="1" stop-color="{C['nixie']}" stop-opacity="0"/></radialGradient>
<pattern id="mesh" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 3h6M3 0v6" stroke="#ff9070" stroke-width=".4" opacity=".25"/></pattern>"""
    body = [wires(W, 6, ".35", signal=False)]
    tw, gap = 66, 12
    total = len(dv) * tw + (len(dv) - 1) * gap
    x0 = (W - total) / 2
    for i, ch in enumerate(dv):
        x = x0 + i * (tw + gap)
        body.append(f'<rect x="{x}" y="34" width="{tw}" height="128" rx="30" fill="#120706" stroke="#4a2018" stroke-width="1.5"/>')
        body.append(f'<rect x="{x}" y="34" width="{tw}" height="128" rx="30" fill="url(#warm)"/>')
        if ch != ".":
            for g in "0123456789":
                body.append(f'<text x="{x+tw/2}" y="128" class="cut" font-size="82" fill="none" stroke="#6a2a1c" stroke-width=".7" text-anchor="middle" opacity=".35">{g}</text>')
        flick = ""
        if i in (1, 4, 7):
            flick = (f'<animate attributeName="opacity" values="1;.35;1;.9;1" keyTimes="0;.03;.06;.5;1" dur="{5+i*1.3:.1f}s" '
                     f'repeatCount="indefinite"/>')
        body.append(f'<text x="{x+tw/2}" y="128" class="cut" font-size="82" fill="{C["nixie_core"]}" stroke="{C["nixie"]}" stroke-width="1.6" '
                    f'text-anchor="middle" filter="url(#nglow)">{esc(ch)}{flick}</text>')
        body.append(f'<rect x="{x+4}" y="40" width="{tw-8}" height="116" rx="26" fill="url(#mesh)"/>')
        body.append(f'<rect x="{x}" y="34" width="{tw}" height="128" rx="30" fill="url(#glass)"/>')
        body.append(f'<rect x="{x-3}" y="162" width="{tw+6}" height="12" rx="2" fill="#1a1612" stroke="#2e2820"/>')
        body.append(f'<rect x="{x+tw/2-2}" y="174" width="4" height="6" fill="#2e2820"/>')
    body.append(text(W / 2, 206, "WORLD LINE DIVERGENCE  ·  STEINS;GATE  ·  ATTRACTOR FIELD: NONE", "plex", 8.5, C["muted"], "middle", ls=3))
    body.append(f'<line x1="36" y1="226" x2="964" y2="226" stroke="{C["line"]}"/>')
    cells = [("PUBLIC REPOS", stats.get("repos")), ("STARS EARNED", stats.get("stars")), ("FOLLOWERS", stats.get("followers")),
             ("CONTRIBUTIONS / 12 MO", stats.get("contributions")), ("LAST SYNC", today)]
    cw = (W - 72) / len(cells)
    for i, (k, v) in enumerate(cells):
        cx = 36 + i * cw
        if i:
            body.append(f'<line x1="{cx}" y1="244" x2="{cx}" y2="296" stroke="{C["line"]}"/>')
        size = 22 if k == "LAST SYNC" else 36
        body.append(text(cx + 20, 280, "—" if v is None else v, "bebas", size, C["paper"], ls=1))
        body.append(text(cx + 20, 298, k, "plex", 7.5, C["muted"], ls=2))
    title = f"World line divergence {dv}. " + ", ".join(f"{k.lower()} {v}" for k, v in cells if v is not None)
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Cutive"), defs, title)


def footer_card():
    W, H = 1000, 250
    depth, layer = LAYERS[6]
    ex, ey = 500, 66
    defs = f"""<radialGradient id="iris" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{C['red_hi']}"/>
<stop offset=".7" stop-color="{C['red']}"/><stop offset="1" stop-color="{C['red_dk']}"/></radialGradient>
<clipPath id="eye"><path d="M{ex-62} {ey} Q{ex} {ey-40} {ex+62} {ey} Q{ex} {ey+40} {ex-62} {ey}Z"/></clipPath>"""
    veins = []
    for side in (-1, 1):
        x0 = ex + side * 62
        for dy, ln, bend in [(-14, 46, -10), (-4, 62, 6), (8, 50, 12), (18, 34, -6)]:
            veins.append(f'<path d="M{x0} {ey} q{side*ln*.5} {dy+bend} {side*ln} {dy}" fill="none" stroke="{C["red"]}" '
                         f'stroke-width="{1.4 if abs(dy) < 10 else .9}" stroke-linecap="round"/>')
    body = [
        wires(W, 10, ".4"),
        # Kakugan: black sclera, red iris, veins spreading from the corners
        "".join(veins),
        f'<path d="M{ex-62} {ey} Q{ex} {ey-40} {ex+62} {ey} Q{ex} {ey+40} {ex-62} {ey}Z" fill="#050505" stroke="{C["paper"]}" stroke-width="1.6"/>',
        f'<g clip-path="url(#eye)"><circle cx="{ex}" cy="{ey}" r="19" fill="url(#iris)">'
        f'<animate attributeName="cx" values="{ex};{ex-6};{ex};{ex+5};{ex}" dur="9s" repeatCount="indefinite"/></circle>'
        f'<circle cx="{ex}" cy="{ey}" r="6" fill="#050505"><animate attributeName="cx" values="{ex};{ex-6};{ex};{ex+5};{ex}" dur="9s" repeatCount="indefinite"/></circle>'
        f'<circle cx="{ex+6}" cy="{ey-6}" r="2.4" fill="{C["paper"]}"/></g>',
        text(W / 2, 148, "El Psy Kongroo.", "play", 26, C["paper"], "middle"),
        f'<g transform="rotate(180 500 176)">' + text(500, 181, "CLOSE THE WORLD, OPEN THE NEXT", "bebas", 15, C["muted"], "middle", ls=4) + "</g>",
        text(W / 2, 212, f"LAYER:07  \u00b7  {layer}  \u00b7  DEPTH {depth}  \u00b7  NO ASCENT WITHOUT A PRICE", "plex", 9, C["dim"], "middle", ls=2),
        f'<line x1="300" y1="228" x2="700" y2="228" stroke="{C["line"]}"/>',
        f'<rect x="496" y="225" width="8" height="6" fill="{C["red"]}"/>',
    ]
    return svg_doc(W, H, "\n".join(body), ("Bebas", "Plex", "Playfair"), defs, title="El Psy Kongroo. Close the world, open the next.")


# --------------------------------------------------------------------------- #
# README pinned block
# --------------------------------------------------------------------------- #
def update_readme_pinned(pinned):
    if not README.exists():
        return
    src = README.read_text(encoding="utf-8")
    start, end = "<!--PINNED:START-->", "<!--PINNED:END-->"
    if start not in src or end not in src:
        print("  pinned markers missing in README.md")
        return
    if pinned:
        parts = [f'<a href="{r["url"]}"><img src="assets/pinned/{r["name"]}.svg" width="100%" '
                 f'alt="{esc(r["name"])} repository card"></a>' for r in pinned]
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
    write(ASSETS / "hero.svg", hero(st, stats, today))
    write(ASSETS / "abyss.svg", abyss_card(stats))
    for n in range(1, len(SECTIONS) + 1):
        write(ASSETS / f"layer-{n:02d}.svg", section_header(n))
    write(ASSETS / "about.svg", about_card(st))
    write(ASSETS / "toolkit.svg", toolkit_card(st))
    write(ASSETS / "system.svg", system_card(st))
    write(ASSETS / "signal.svg", signal_card(st, stats, today))
    write(ASSETS / "footer.svg", footer_card())

    if pinned is not None:
        overrides = st.get("pinned_overrides", {}) or {}
        keep = set()
        for i, r in enumerate(pinned, 1):
            write(PINNED_DIR / f"{r['name']}.svg", project_card(i, r, overrides.get(r["name"], {}) or {}))
            keep.add(f"{r['name']}.svg")
        if PINNED_DIR.exists():
            for f in PINNED_DIR.glob("*.svg"):
                if f.name not in keep:
                    f.unlink()
                    print(f"  removed stale {f.relative_to(ROOT)}")
        update_readme_pinned(pinned)
    print("done")


if __name__ == "__main__":
    main()
