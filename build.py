#!/usr/bin/env python3
import os
import sys
import datetime
import json
import requests

# Default configuration matching the user's terminal theme (inspired by lainPfp.jpg)
THEME = {
    "bg": "#120e16",               # Very dark charcoal-violet background
    "fg": "#e6dcf0",               # Soft lavender-grey foreground
    "border_active": "#8c6e5e",    # Warm bronze-brown border (Lain's hair color)
    "border_inactive": "#2d2238",  # Muted dark purple-grey
    "cyan": "#a5c2d8",             # Soft slate-blue/silver (glasses reflection/sky hue)
    "cursor": "#8c6e5e",           # Bronze-brown cursor
    "gold": "#dfb15b",             # Warm gold (representing Nixie tube light / warm amber)
    "pink": "#cfa5df",             # Soft dusty pink
    "gray": "#6c5d77"              # Slate violet-grey
}

def generate_terminal_svg(username, stats):
    """
    Generates a retro terminal SVG showcasing NAVI OS status and coding parameters.
    Includes a blinking cursor, subtle CRT grid, and scanlines.
    """
    # Format system diagnostic time
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Render ASCII art logo safely for XML
    ascii_art = r"""
   _  _  __   _  _  ____   ___    _  _   __   _  _  ____
  ( \/ )/  \ ( \/ )(_  _) / __)  ( \( ) /__\ ( \/ )(_  _)
   \  /(  O ) \  /  _)(_ ( (__    )  ( /(__)\ \  /   )(  
    \/  \__/   \/  (____) \___)  (_)\_)(__)(__) \/   (__)
    """
    # Clean ASCII art lines
    ascii_lines = [line for line in ascii_art.split("\n") if line.strip()]
    ascii_svg_lines = ""
    y_start = 110
    for idx, line in enumerate(ascii_lines):
        # Escape any special XML characters
        escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ascii_svg_lines += f'<text x="50" y="{y_start + idx*16}" fill="{THEME["border_active"]}" font-family="monospace" font-size="12" font-weight="bold">{escaped_line}</text>\n'

    # Prepare stats representation
    skills = [
        {"lang": "Java", "level": 90, "color": THEME["cyan"]},
        {"lang": "Python", "level": 85, "color": THEME["pink"]},
        {"lang": "Linux / Bash", "level": 80, "color": THEME["gold"]},
        {"lang": "Rust", "level": 60, "color": THEME["border_active"]}
    ]
    
    skills_svg = ""
    skills_y = 230
    for idx, skill in enumerate(skills):
        filled_blocks = skill["level"] // 10
        empty_blocks = 10 - filled_blocks
        bar = "■" * filled_blocks + "□" * empty_blocks
        skills_svg += f"""
        <text x="50" y="{skills_y + idx*25}" fill="{THEME["fg"]}" font-family="monospace" font-size="14">
            <tspan fill="{THEME["gray"]}">&gt; </tspan>{skill["lang"].ljust(15)}: 
            <tspan fill="{skill["color"]}">{bar}</tspan> {skill["level"]}%
        </text>
        """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 480" width="100%" height="auto">
    <style>
        .terminal-bg {{
            fill: {THEME["bg"]};
            stroke: {THEME["border_active"]};
            stroke-width: 2.5;
        }}
        .scanlines {{
            fill: url(#scanline-pattern);
            opacity: 0.15;
        }}
        .title-text {{
            fill: {THEME["fg"]};
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 13px;
        }}
        .console-text {{
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 14px;
        }}
        .glow {{
            filter: url(#crt-glow);
        }}
        @keyframes blink {{
            0%, 49% {{ opacity: 1; }}
            50%, 100% {{ opacity: 0; }}
        }}
        .cursor {{
            animation: blink 1s infinite;
            fill: {THEME["cursor"]};
        }}
        @keyframes scanline-anim {{
            0% {{ transform: translateY(0); }}
            100% {{ transform: translateY(8px); }}
        }}
        .scanline-pattern-rect {{
            animation: scanline-anim 4s linear infinite;
        }}
    </style>

    <defs>
        <!-- CRT Glow Filter -->
        <filter id="crt-glow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        
        <!-- Scanline Pattern -->
        <pattern id="scanline-pattern" width="820" height="8" patternUnits="userSpaceOnUse">
            <rect width="820" height="4" fill="#000" />
            <rect y="4" width="820" height="4" fill="transparent" />
        </pattern>
    </defs>

    <!-- Terminal Window Frame -->
    <rect class="terminal-bg" width="820" height="480" rx="8" />
    
    <!-- CRT Effect Scanlines -->
    <rect class="scanlines" width="820" height="480" rx="8" pointer-events="none" />
    
    <!-- Header Bar -->
    <rect x="0" y="0" width="820" height="35" rx="8" fill="{THEME["border_inactive"]}" />
    <!-- Window buttons -->
    <circle cx="20" cy="18" r="6" fill="{THEME["pink"]}" />
    <circle cx="40" cy="18" r="6" fill="{THEME["gold"]}" />
    <circle cx="60" cy="18" r="6" fill="{THEME["cyan"]}" />
    
    <!-- Header Title -->
    <text x="410" y="22" class="title-text" text-anchor="middle" font-weight="bold">Wired-Navi0x1F@NAVI-Terminal:~ (Protocol: Copula-0x1F)</text>
    
    <!-- System Diagnostics -->
    <g class="console-text glow">
        <!-- Diagnostic Block (Right Side) -->
        <rect x="520" y="70" width="250" height="135" rx="4" fill="{THEME["bg"]}" stroke="{THEME["border_inactive"]}" stroke-width="1.5" />
        <text x="535" y="95" fill="{THEME["cyan"]}" font-family="monospace" font-size="12" font-weight="bold">[SYSTEM DIAGNOSTICS]</text>
        <text x="535" y="120" fill="{THEME["fg"]}" font-family="monospace" font-size="11">NODE: Wired-Navi0x1F</text>
        <text x="535" y="140" fill="{THEME["fg"]}" font-family="monospace" font-size="11">COGNITIVE SYNC: 98.4%</text>
        <text x="535" y="160" fill="{THEME["fg"]}" font-family="monospace" font-size="11">WIRED CONNECT: SYNCED</text>
        <text x="535" y="180" fill="{THEME["fg"]}" font-family="monospace" font-size="10" fill-opacity="0.7">UPTIME: 1048596s</text>
        
        <!-- Welcome Messages (Left Side) -->
        <text x="50" y="75" fill="{THEME["cyan"]}" font-family="monospace" font-size="14" font-weight="bold">&gt; Initializing NAVI-OS v7.25...</text>
        
        <!-- ASCII Logo -->
        {ascii_svg_lines}
        
        <!-- Divider -->
        <line x1="50" y1="205" x2="770" y2="205" stroke="{THEME["border_inactive"]}" stroke-width="1.5" stroke-dasharray="5 5" />
        
        <!-- Skills Header -->
        <text x="50" y="225" fill="{THEME["gold"]}" font-family="monospace" font-size="14" font-weight="bold">&gt;_ core_modules_loaded</text>
        
        <!-- Skills/Languages List -->
        {skills_svg}
        
        <!-- Terminal Prompt & Command Line -->
        <text x="50" y="355" fill="{THEME["fg"]}" font-family="monospace" font-size="14">
            <tspan fill="{THEME["cyan"]}">Wired-Navi0x1F@wired</tspan>:<tspan fill="{THEME["pink"]}">~</tspan>$ cat thoughts.txt
        </text>
        
        <!-- thoughts.txt output -->
        <text x="50" y="385" fill="{THEME["gray"]}" font-family="monospace" font-size="13" font-style="italic">
            &quot;No matter where you are, everyone is always connected.&quot;
        </text>
        <text x="50" y="405" fill="{THEME["gray"]}" font-family="monospace" font-size="13" font-style="italic">
            &quot;There is no barrier between the Wired and the Real.&quot;
        </text>
        
        <!-- Blinking Prompt -->
        <text x="50" y="445" fill="{THEME["fg"]}" font-family="monospace" font-size="14">
            <tspan fill="{THEME["cyan"]}">Wired-Navi0x1F@wired</tspan>:<tspan fill="{THEME["pink"]}">~</tspan>$ <tspan fill="{THEME["fg"]}">El_Psy_Kongroo</tspan>
        </text>
        <rect x="298" y="432" width="8" height="15" class="cursor" />
    </g>
</svg>
"""
    return svg_content


def generate_divergence_meter_svg():
    """
    Generates a Steins;Gate Divergence Meter SVG using glowing Nixie Tubes.
    Visualizes the Steins;Gate World Line divergence target: 1.048596%.
    """
    digits = ["1", ".", "0", "4", "8", "5", "9", "6"]
    
    # Custom Nixie Tube representation
    nixie_tubes = ""
    tube_width = 65
    tube_gap = 12
    start_x = 40
    
    for idx, digit in enumerate(digits):
        x = start_x + idx * (tube_width + tube_gap)
        
        # Decide if it's a dot or a digit
        if digit == ".":
            nixie_tubes += f"""
            <!-- Nixie Dot Tube -->
            <g transform="translate({x}, 0)">
                <!-- Glass Outer Tube -->
                <rect x="20" y="25" width="25" height="100" rx="12.5" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" opacity="0.8" />
                <rect x="22" y="27" width="21" height="96" rx="10.5" fill="url(#glass-gradient)" opacity="0.1" />
                <!-- Glowing Nixie Dot -->
                <circle cx="32" cy="105" r="4" fill="{THEME["gold"]}" filter="url(#nixie-glow)" />
                <circle cx="32" cy="105" r="2" fill="#fff" />
            </g>
            """
        else:
            nixie_tubes += f"""
            <!-- Nixie Digit Tube for '{digit}' -->
            <g transform="translate({x}, 0)">
                <!-- Back Grid Metal Mesh (Nixie characteristic) -->
                <rect x="5" y="15" width="55" height="120" rx="10" fill="url(#grid-mesh)" opacity="0.25" stroke="{THEME["gray"]}" stroke-width="0.5" />
                
                <!-- Glass Envelope -->
                <rect x="2" y="10" width="61" height="130" rx="15" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" opacity="0.8" />
                <rect x="5" y="13" width="55" height="124" rx="12" fill="url(#glass-gradient)" opacity="0.1" />
                
                <!-- Inactive digits background silhouette (gives a realistic Nixie feel) -->
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="#ff5500" opacity="0.04">8</text>
                
                <!-- Active Glowing Digit -->
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="{THEME["gold"]}" filter="url(#nixie-glow)">{digit}</text>
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="#fff" opacity="0.8">{digit}</text>
                
                <!-- Base Mount -->
                <rect x="2" y="135" width="61" height="12" rx="2" fill="#1f1130" stroke="{THEME["border_inactive"]}" stroke-width="1" />
            </g>
            """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 170" width="100%" height="auto">
    <style>
        .meter-bg {{
            fill: #08030d;
            stroke: {THEME["border_inactive"]};
            stroke-width: 2;
        }}
        .label-text {{
            fill: {THEME["gray"]};
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 11px;
            letter-spacing: 2px;
        }}
        .divergence-glow {{
            filter: url(#panel-glow);
        }}
    </style>
    
    <defs>
        <!-- Nixie Glow (High Intensity Warm Amber) -->
        <filter id="nixie-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3.5" result="blur1" />
            <feGaussianBlur stdDeviation="8" result="blur2" />
            <feMerge>
                <feMergeNode in="blur2" />
                <feMergeNode in="blur1" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        
        <!-- Panel Subtle Glow -->
        <filter id="panel-glow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feComponentTransfer in="blur" result="glow">
                <feFuncA type="linear" slope="0.3"/>
            </feComponentTransfer>
            <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>

        <!-- Glass Reflection Gradient -->
        <linearGradient id="glass-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.3"/>
            <stop offset="25%" stop-color="#ffffff" stop-opacity="0.05"/>
            <stop offset="50%" stop-color="#ffffff" stop-opacity="0.0"/>
            <stop offset="85%" stop-color="#ffffff" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="#ffffff" stop-opacity="0.25"/>
        </linearGradient>

        <!-- Metal Grid Mesh Pattern -->
        <pattern id="grid-mesh" width="4" height="4" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="4" y2="0" stroke="#ff5500" stroke-width="0.3" opacity="0.3"/>
            <line x1="0" y1="0" x2="0" y2="4" stroke="#ff5500" stroke-width="0.3" opacity="0.3"/>
        </pattern>
    </defs>

    <!-- Meter Back Panel Chassis -->
    <rect class="meter-bg" width="680" height="170" rx="6" />
    
    <!-- Vent grills (retro details) -->
    <rect x="40" y="6" width="600" height="4" rx="2" fill="#000" opacity="0.6"/>
    <rect x="40" y="160" width="600" height="4" rx="2" fill="#000" opacity="0.6"/>
    
    <!-- Nixie Tubes Group -->
    <g class="divergence-glow" transform="translate(10, 5)">
        {nixie_tubes}
    </g>
    
    <!-- Panel label -->
    <text x="640" y="152" class="label-text" text-anchor="end">WORLD LINE DIVERGENCE METER</text>
</svg>
"""
    return svg_content


def main():
    username = "Wired-Navi0x1F"
    stats = {}
    
    # Try fetching Github Stats if running on CI or token is set
    # (Just basic configuration; default layout relies on beautiful SVG generation)
    print("Generating retro terminal card...")
    terminal_svg = generate_terminal_svg(username, stats)
    with open("terminal.svg", "w", encoding="utf-8") as f:
        f.write(terminal_svg)
        
    print("Generating Nixie Divergence Meter...")
    divergence_svg = generate_divergence_meter_svg()
    with open("divergence_meter.svg", "w", encoding="utf-8") as f:
        f.write(divergence_svg)

    print("Generating README.md...")
    # Generate the Markdown file structure
    readme_content = f"""# 🌐 Wired-Navi0x1F

<div align="center">
  <!-- Waving Gradient Banner matching Lain's palette -->
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:120e16,50:8c6e5e,100:cfa5df&height=180&section=header&text=Wired-Navi0x1F&fontColor=e6dcf0&fontSize=45&animation=fadeIn&fontAlignY=35&desc=Close%20the%20world,%20open%20the%20nExt%20//%20Layer%2007%20Wired%20Node&descAlignY=55&descSize=16" width="100%" alt="Wired Header" />
</div>

<br />

<div align="center">
  <table border="0" cellpadding="10" cellspacing="0" width="100%">
    <tr>
      <!-- Column 1: Terminal Status -->
      <td width="60%" valign="top" align="center">
        <img src="terminal.svg" width="100%" alt="NAVI Terminal Core" style="border-radius: 8px; border: 2px solid {THEME["border_active"]};" />
      </td>
      <!-- Column 2: Profile & Typing -->
      <td width="40%" valign="top" align="center">
        <div style="border: 2px solid {THEME["border_active"]}; border-radius: 8px; background: {THEME["bg"]}; padding: 15px; text-align: center;">
          <img src="lainPfp.jpg" width="100%" style="border-radius: 6px; border: 1px solid {THEME["gray"]};" alt="System Avatar" />
          <br /><br />
          <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=16&duration=2500&pause=1000&color=cfa5df&center=true&vCenter=true&width=280&lines=Connected+to+the+Wired...;Layer+07+System+Node;Cognitive+Sync+98.4%25;El+Psy+Kongroo" alt="Typing Status" />
          <hr style="border: 0; border-top: 1px dashed {THEME["gray"]}; margin: 15px 0;" />
          <table width="100%" style="font-family: monospace; font-size: 13px; color: {THEME["fg"]}; text-align: left;">
            <tr><td><strong>Presence:</strong></td><td><code style="color: #22c55e;">🟢 SYNCHRONIZED</code></td></tr>
            <tr><td><strong>Host OS:</strong></td><td><code>NAVI Copula Kernel 7.25</code></td></tr>
            <tr><td><strong>Node Status:</strong></td><td><code style="color: {THEME["gold"]};">📡 LISTENING</code></td></tr>
            <tr><td><strong>Divergence:</strong></td><td><code style="color: {THEME["gold"]};">1.048596%</code></td></tr>
          </table>
        </div>
      </td>
    </tr>
  </table>
</div>

<br />

## ─── 📡 PHYSICAL PARAMETERS & WIRED STATE ───

<div align="center">
  <table border="0" cellpadding="8" cellspacing="0" width="100%">
    <tr>
      <!-- Left side: Directives -->
      <td width="50%" valign="top">
        <h3>🧠 Core Directives & Technologies</h3>
        <ul>
          <li>☕ <strong>Java & Object-Oriented Engineering</strong>: Architecting heavy enterprise layers, protocol decoders, and structured logic modules.</li>
          <li>🐍 <strong>Python & Automation Scripts</strong>: Parsing system telemetry, handling neural-net integration data, and automated node scripts.</li>
          <li>🐧 <strong>Linux Terminal & Systems</strong>: Ricing, shell automation, and configuring custom desktop environments with a serial aesthetic.</li>
        </ul>
      </td>
      <!-- Right side: Repos -->
      <td width="50%" valign="top">
        <h3>🕸️ Active Sub-nodes</h3>
        <ul>
          <li>📂 <strong><a href="https://github.com/Wired-Navi0x1F/LainOS-Wired">LainOS-Wired</a></strong>: Config files & dotfiles for Hyprland rices reflecting the retro-cyber aesthetics of Serial Experiments Lain.</li>
          <li>📂 <strong><a href="https://github.com/Wired-Navi0x1F/Copula-Core">Copula-Core</a></strong>: Java system protocols and data structures modeled after retro NAVI systems.</li>
          <li>📂 <strong><a href="https://github.com/Wired-Navi0x1F/Nixie-Divergence">Nixie-Divergence</a></strong>: Python-based world line calculation and simulation modules.</li>
        </ul>
      </td>
    </tr>
  </table>
</div>

<br />

## ─── 🕹️ INTERACTIVE WORLD LINE ARCADE ───

<div align="center">
  <!-- Nixie Divergence Meter -->
  <img src="divergence_meter.svg" width="90%" alt="World Line Divergence Meter" />
</div>

<br />

<div align="center">
  <table border="0" cellpadding="10" cellspacing="0" width="100%">
    <tr>
      <!-- Pokemon Game -->
      <td width="55%" valign="top" align="center">
        <h4 align="center">🎮 Let's Play Pokémon Together</h4>
        <table border="0" cellpadding="5" cellspacing="0">
          <tr>
            <td align="right" valign="middle">
              <table border="0" cellpadding="2">
                <tr>
                  <td></td>
                  <td><a href="https://toy.cloudreve.org/control?button=2&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/up.png" width="28" alt="Up"/></a></td>
                  <td></td>
                </tr>
                <tr>
                  <td><a href="https://toy.cloudreve.org/control?button=1&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/left.png" width="28" alt="Left"/></a></td>
                  <td></td>
                  <td><a href="https://toy.cloudreve.org/control?button=0&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/right.png" width="28" alt="Right"/></a></td>
                </tr>
                <tr>
                  <td></td>
                  <td><a href="https://toy.cloudreve.org/control?button=3&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/down.png" width="28" alt="Down"/></a></td>
                  <td></td>
                </tr>
              </table>
            </td>
            <td align="center" valign="middle">
              <img src="https://toy.cloudreve.org/image" width="220" style="border: 2px solid {THEME["border_active"]}; border-radius: 4px;" alt="Pokemon Game State"/>
            </td>
            <td align="left" valign="middle">
              <table border="0" cellpadding="4">
                <tr>
                  <td><a href="https://toy.cloudreve.org/control?button=5&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/B.png" width="30" alt="B"/></a></td>
                  <td><a href="https://toy.cloudreve.org/control?button=4&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/A.png" width="30" alt="A"/></a></td>
                </tr>
                <tr>
                  <td colspan="2" align="center">
                    <a href="https://toy.cloudreve.org/control?button=6&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/select.png" width="60" alt="Select"/></a>
                    <a href="https://toy.cloudreve.org/control?button=7&callback=https://github.com/Wired-Navi0x1F"><img src="https://raw.githubusercontent.com/HFO4/HFO4/master/img/start.png" width="60" alt="Start"/></a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
      <!-- Contribution Snake Game -->
      <td width="45%" valign="top" align="center">
        <h4 align="center">🐍 Contributions Snake</h4>
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="github-contribution-grid-snake-dark.svg" />
          <source media="(prefers-color-scheme: light)" srcset="github-contribution-grid-snake.svg" />
          <img alt="Snake eating contributions" src="github-contribution-grid-snake.svg" width="100%" />
        </picture>
      </td>
    </tr>
  </table>
</div>

<br />

## ─── 🌀 THE OCTO RING WEB NETWORK ───

<div align="center">
  <table border="0" cellpadding="10" cellspacing="0" style="border: 2.5px solid {THEME["border_active"]}; border-radius: 8px; background: {THEME["bg"]}; max-width: 420px; width: 100%;">
    <tbody>
      <tr>
        <td align="center">
          <a href="https://octo-ring.com/"><img src="https://octo-ring.com/static/img/widget/top.png" width="100%" alt="Octo Ring logo" align="top"></a>
          <br />
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/prev"><img src="https://octo-ring.com/static/img/widget/prev.png" width="32%" alt="previous" align="top" title="previous profile"></a>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/random"><img src="https://octo-ring.com/static/img/widget/random.png" width="32%" alt="random" align="top" title="random profile"></a>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/next"><img src="https://octo-ring.com/static/img/widget/next.png" width="32%" alt="next" align="top" title="next profile"></a>
          <br />
          <a href="https://octo-ring.com/"><img src="https://octo-ring.com/static/img/widget/bottom.png" width="100%" alt="check out other GitHub profiles in the Octo Ring" align="top"></a>
        </td>
      </tr>
      <tr>
        <td align="center" style="font-family: monospace; font-size: 13px; padding-top: 10px;">
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/prev" style="color: {THEME["pink"]}; text-decoration: none; font-weight: bold;">&larr; Prev</a>
          <span style="color: {THEME["gray"]};"> | </span>
          <a href="https://octo-ring.com" style="color: {THEME["fg"]}; text-decoration: none; font-weight: bold;">Octo Ring Hub</a>
          <span style="color: {THEME["gray"]};"> | </span>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/random" style="color: {THEME["gold"]}; text-decoration: none;">🎲 Random</a>
          <span style="color: {THEME["gray"]};"> | </span>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/next" style="color: {THEME["pink"]}; text-decoration: none; font-weight: bold;">Next &rarr;</a>
        </td>
      </tr>
    </tbody>
  </table>
</div>

<br />

---

<div align="center">
  <p align="center" style="font-family: monospace; color: {THEME["gray"]};">
    WIRED PROTOCOL INITIATED // IP STATE: SECURE // CLOSE THE WORLD, OPEN THE NEXT.
  </p>
</div>
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Success! Profile files generated.")

if __name__ == "__main__":
    main()
