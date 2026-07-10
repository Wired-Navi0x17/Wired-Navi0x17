#!/usr/bin/env python3
import os
import sys
import datetime
import json
import requests

# Default configuration matching the user's terminal theme
THEME = {
    "bg": "#0e0616",               # Very dark violet
    "fg": "#e9dcf5",               # Soft lavender
    "border_active": "#c084fc",    # Purplish pink
    "border_inactive": "#3b1f4a",  # Dark muted purple
    "cyan": "#00f0ff",             # Cyan
    "cursor": "#c084fc",           # Purplish pink
    "gold": "#eab308",             # Warm gold
    "pink": "#ff66cc",             # Magenta pink
    "gray": "#6b4f80"              # Muted purple
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
  <img src="terminal.svg" width="820" alt="NAVI Terminal System Core" style="max-width: 100%; height: auto;" />
</div>

<br />

<div align="center">
  <img src="divergence_meter.svg" width="680" alt="World Line Divergence Meter" style="max-width: 100%; height: auto;" />
</div>

<br />

## ─── 📡 PHYSICAL PARAMETERS & WIRED STATE ───

```
[SYSTEM IDENTITY]
Username:   Wired-Navi0x1F
System OS:  NAVI Copula Kernel 7.25
Presence:   Connected to the Wired
Location:   Layer 07 // The Wired
```

### 🧠 Core Directives & Technologies

- ☕ **Java & Object-Oriented Engineering**: Architecting heavy enterprise layers, protocol decoders, and structured logic modules.
- 🐍 **Python & Automation Scripts**: Parsing system telemetry, handling neural-net integration data, and automated node scripts.
- 🐧 **Linux Terminal & Systems**: Ricing, shell automation, and configuring custom desktop environments with a serial aesthetic.

---

### 🕸️ Project Sub-nodes (System Repos)

Here are the active operational modules currently synchronized on the local node:

1. **[LainOS-Wired](https://github.com/Wired-Navi0x1F/LainOS-Wired)** *(Config files & dotfiles for Hyprland rices reflecting the retro-cyber aesthetics of Serial Experiments Lain)*
2. **[Copula-Core](https://github.com/Wired-Navi0x1F/Copula-Core)** *(Java system protocols and data structures modeled after retro NAVI systems)*
3. **[Nixie-Divergence](https://github.com/Wired-Navi0x1F/Nixie-Divergence)** *(Python-based world line calculation and simulation modules)*

---

### 🎙️ Transmission Received

> "No matter where you are, everyone is always connected."
> 
> *— Serial Experiments Lain*

> "This is the choice of Steins;Gate. El Psy Kongroo."
> 
> *— Okabe Rintaro (Steins;Gate)*

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
