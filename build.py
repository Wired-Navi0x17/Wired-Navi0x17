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
    "gray": "#6b4f80",             # Muted purple
    "orange": "#ff5500",           # Nixie Orange
    "light_orange": "#ffcc66"      # Nixie Filament
}

def generate_terminal_svg(username, stats):
    """
    Generates an animated, ultra-premium retro terminal SVG.
    Includes a sweeping scanline, custom cyber grid, rolling waveform animation,
    system diagnostic panel, and high-fidelity Unicode ASCII art.
    """
    # Clean ASCII art logo (WIRED NAVI)
    ascii_art = r"""
██╗    ██╗██╗██████╗ ███████╗██████╗     ███╗   ██╗█████╗ ██╗   ██╗██╗
██║    ██║██║██╔══██╗██╔════╝██╔══██╗    ████╗  ██║██╔══██╗██║   ██║██║
██║ █╗ ██║██║██████╔╝█████╗  ██║  ██║    ██╔██╗ ██║███████║██║   ██║██║
██║███╗██║██║██╔══██╗██╔══╝  ██║  ██║    ██║╚██╗██║██╔══██║╚██╗ ██╔╝██║
╚███╔███╔╝██║██║  ██║███████╗██████╔╝    ██║ ╚████║██║  ██║ ╚████╔╝ ██║
 ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚══════╝╚═════╝     ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝  ╚═╝"""

    ascii_lines = [line for line in ascii_art.split("\n") if line.strip()]
    ascii_svg_lines = ""
    y_start = 100
    for idx, line in enumerate(ascii_lines):
        escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ascii_svg_lines += f'<text x="50" y="{y_start + idx*13}" fill="{THEME["border_active"]}" font-family="monospace" font-size="9" font-weight="bold" xml:space="preserve">{escaped_line}</text>\n'

    # Skill modules block
    skills = [
        {"lang": "Java Core", "level": 90, "color": THEME["cyan"]},
        {"lang": "Python Automation", "level": 85, "color": THEME["pink"]},
        {"lang": "Linux & Bash", "level": 80, "color": THEME["gold"]},
        {"lang": "Systems / C++", "level": 70, "color": THEME["border_active"]}
    ]
    
    skills_svg = ""
    skills_y = 230
    for idx, skill in enumerate(skills):
        filled_blocks = skill["level"] // 10
        empty_blocks = 10 - filled_blocks
        bar = "■" * filled_blocks + "□" * empty_blocks
        skills_svg += f"""
        <text x="50" y="{skills_y + idx*22}" fill="{THEME["fg"]}" font-family="monospace" font-size="13">
            <tspan fill="{THEME["gray"]}">&gt; </tspan>{skill["lang"].ljust(18)}: 
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
    </style>

    <defs>
        <!-- CRT Glow Filter -->
        <filter id="crt-glow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        
        <!-- Scanline Pattern -->
        <pattern id="scanline-pattern" width="820" height="6" patternUnits="userSpaceOnUse">
            <rect width="820" height="3" fill="#000" />
            <rect y="3" width="820" height="3" fill="transparent" />
        </pattern>
        
        <!-- Matrix Grid Pattern -->
        <pattern id="matrix-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="0.5" opacity="0.2" />
        </pattern>
    </defs>

    <!-- Terminal Window Frame -->
    <rect class="terminal-bg" width="820" height="480" rx="8" />
    
    <!-- Matrix Grid Layout -->
    <rect width="820" height="480" fill="url(#matrix-grid)" rx="8" />
    
    <!-- CRT Effect Scanlines -->
    <rect class="scanlines" width="820" height="480" rx="8" pointer-events="none" />
    
    <!-- Sweeping Laser Scanline (CRT feel) -->
    <rect x="2" y="35" width="816" height="2" fill="{THEME["cyan"]}" opacity="0.4" filter="url(#crt-glow)">
        <animate attributeName="y" from="35" to="475" dur="7s" repeatCount="indefinite" />
    </rect>
    
    <!-- Header Bar -->
    <rect x="0" y="0" width="820" height="35" rx="8" fill="{THEME["border_inactive"]}" />
    <!-- Window buttons -->
    <circle cx="20" cy="18" r="6" fill="{THEME["pink"]}" />
    <circle cx="40" cy="18" r="6" fill="{THEME["gold"]}" />
    <circle cx="60" cy="18" r="6" fill="{THEME["cyan"]}" />
    
    <!-- Header Title -->
    <text x="410" y="22" class="title-text" text-anchor="middle" font-weight="bold">Wired-Navi0x1F@NAVI-Terminal:~ (Protocol: Copula-0x1F)</text>
    
    <!-- System Diagnostics Block -->
    <g class="console-text glow">
        <!-- Diagnostic Block (Right Side) -->
        <rect x="525" y="70" width="245" height="135" rx="4" fill="{THEME["bg"]}" stroke="{THEME["border_inactive"]}" stroke-width="1.5" />
        <text x="540" y="95" fill="{THEME["cyan"]}" font-family="monospace" font-size="12" font-weight="bold">[SYSTEM DIAGNOSTICS]</text>
        <text x="540" y="120" fill="{THEME["fg"]}" font-family="monospace" font-size="11">NODE: Wired-Navi0x1F</text>
        <text x="540" y="140" fill="{THEME["fg"]}" font-family="monospace" font-size="11">COGNITIVE SYNC: 98.4%</text>
        <text x="540" y="160" fill="{THEME["fg"]}" font-family="monospace" font-size="11">WIRED CONNECT: SYNCED</text>
        <text x="540" y="180" fill="{THEME["fg"]}" font-family="monospace" font-size="10" fill-opacity="0.7">UPTIME: 1048596s</text>
        
        <!-- Welcome Messages -->
        <text x="50" y="75" fill="{THEME["cyan"]}" font-family="monospace" font-size="14" font-weight="bold">&gt; Initializing NAVI-OS v7.25...</text>
        
        <!-- ASCII Logo -->
        {ascii_svg_lines}
        
        <!-- Divider -->
        <line x1="50" y1="205" x2="770" y2="205" stroke="{THEME["border_inactive"]}" stroke-width="1.5" stroke-dasharray="5 5" />
        
        <!-- Skills Header -->
        <text x="50" y="215" fill="{THEME["gold"]}" font-family="monospace" font-size="13" font-weight="bold">&gt;_ system_parameters_loaded</text>
        
        <!-- Skills/Languages List -->
        {skills_svg}
        
        <!-- Terminal Prompt & Command Line -->
        <text x="50" y="325" fill="{THEME["fg"]}" font-family="monospace" font-size="13">
            <tspan fill="{THEME["cyan"]}">Wired-Navi0x1F@wired</tspan>:<tspan fill="{THEME["pink"]}">~</tspan>$ cat thoughts.txt
        </text>
        
        <!-- thoughts.txt output -->
        <text x="50" y="350" fill="{THEME["gray"]}" font-family="monospace" font-size="12" font-style="italic">
            &quot;No matter where you are, everyone is always connected.&quot;
        </text>
        <text x="50" y="368" fill="{THEME["gray"]}" font-family="monospace" font-size="12" font-style="italic">
            &quot;There is no barrier between the Wired and the Real.&quot;
        </text>
        
        <!-- Oscilloscope "Hum of the Wired" Waveform Animation -->
        <g>
            <path d="M 0 410 C 50 380, 100 440, 150 410 C 200 380, 250 440, 300 410 C 350 380, 400 440, 450 410 C 500 380, 550 440, 600 410 C 650 380, 700 440, 750 410 C 800 380, 850 440, 900 410 C 950 380, 1000 440, 1050 410" fill="none" stroke="{THEME["cyan"]}" stroke-width="1.5" opacity="0.4">
                <animateTransform attributeName="transform" type="translate" from="0,0" to="-300,0" dur="4s" repeatCount="indefinite" />
            </path>
            <path d="M 0 410 C 60 430, 120 390, 180 410 C 240 430, 300 390, 360 410 C 420 430, 480 390, 540 410 C 600 430, 660 390, 720 410 C 780 430, 840 390, 900 410 C 960 430, 1020 390, 1080 410" fill="none" stroke="{THEME["pink"]}" stroke-width="1" opacity="0.25">
                <animateTransform attributeName="transform" type="translate" from="0,0" to="-360,0" dur="6s" repeatCount="indefinite" />
            </path>
        </g>
        
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
    Generates a ultra-premium Steins;Gate Divergence Meter SVG using glowing Nixie Tubes.
    Features metallic chassis, detailed tube grids, filaments, and deep warmth glows.
    """
    digits = ["1", ".", "0", "4", "8", "5", "9", "6"]
    nixie_tubes = ""
    tube_width = 65
    tube_gap = 12
    start_x = 40
    
    for idx, digit in enumerate(digits):
        x = start_x + idx * (tube_width + tube_gap)
        
        if digit == ".":
            nixie_tubes += f"""
            <!-- Nixie Dot Tube -->
            <g transform="translate({x}, 0)">
                <!-- Glass Outer Envelope -->
                <rect x="20" y="25" width="25" height="100" rx="12.5" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" opacity="0.8" />
                <rect x="22" y="27" width="21" height="96" rx="10.5" fill="url(#glass-gradient)" opacity="0.12" />
                <!-- Glowing Nixie Dot -->
                <circle cx="32" cy="105" r="4.5" fill="{THEME["orange"]}" filter="url(#nixie-glow)" />
                <circle cx="32" cy="105" r="2.5" fill="{THEME["light_orange"]}" />
                <circle cx="32" cy="105" r="1" fill="#ffffff" />
            </g>
            """
        else:
            nixie_tubes += f"""
            <!-- Nixie Digit Tube for '{digit}' -->
            <g transform="translate({x}, 0)">
                <!-- Back Grid Metal Mesh -->
                <rect x="5" y="15" width="55" height="120" rx="10" fill="url(#grid-mesh)" opacity="0.3" stroke="{THEME["gray"]}" stroke-width="0.5" />
                
                <!-- Glass Envelope -->
                <rect x="2" y="10" width="61" height="130" rx="15" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" opacity="0.8" />
                <rect x="5" y="13" width="55" height="124" rx="12" fill="url(#glass-gradient)" opacity="0.12" />
                
                <!-- Inner metal support wires -->
                <line x1="12" y1="15" x2="12" y2="135" stroke="#331b40" stroke-width="0.8" opacity="0.7" />
                <line x1="52" y1="15" x2="52" y2="135" stroke="#331b40" stroke-width="0.8" opacity="0.7" />
                
                <!-- Inactive digits background silhouette -->
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="{THEME["orange"]}" opacity="0.04">8</text>
                
                <!-- Active Glowing Digit (Filament layered glows) -->
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="{THEME["orange"]}" filter="url(#nixie-glow)">{digit}</text>
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="{THEME["light_orange"]}" filter="url(#nixie-glow-inner)" opacity="0.9">{digit}</text>
                <text x="32" y="92" text-anchor="middle" font-family="'Courier New', monospace" font-size="75" font-weight="bold" fill="#ffffff" opacity="0.85">{digit}</text>
                
                <!-- Tube Base Mount -->
                <rect x="2" y="135" width="61" height="12" rx="2" fill="#150a21" stroke="{THEME["border_inactive"]}" stroke-width="1" />
                <rect x="8" y="137" width="49" height="2" fill="{THEME["border_inactive"]}" opacity="0.4" />
            </g>
            """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 170" width="100%" height="auto">
    <style>
        .meter-bg {{
            fill: #06020a;
            stroke: {THEME["border_inactive"]};
            stroke-width: 2.5;
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
        <!-- Nixie Filament Glow Filters -->
        <filter id="nixie-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4.5" result="blur1" />
            <feGaussianBlur stdDeviation="9.0" result="blur2" />
            <feMerge>
                <feMergeNode in="blur2" />
                <feMergeNode in="blur1" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        
        <filter id="nixie-glow-inner" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        
        <!-- Panel Glow -->
        <filter id="panel-glow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="12" result="blur" />
            <feComponentTransfer in="blur" result="glow">
                <feFuncA type="linear" slope="0.35"/>
            </feComponentTransfer>
            <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>

        <!-- Glass Reflection Gradient -->
        <linearGradient id="glass-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.35"/>
            <stop offset="20%" stop-color="#ffffff" stop-opacity="0.08"/>
            <stop offset="50%" stop-color="#ffffff" stop-opacity="0.0"/>
            <stop offset="80%" stop-color="#ffffff" stop-opacity="0.08"/>
            <stop offset="100%" stop-color="#ffffff" stop-opacity="0.3"/>
        </linearGradient>

        <!-- Metal Grid Mesh Pattern -->
        <pattern id="grid-mesh" width="3" height="3" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="3" y2="0" stroke="{THEME["orange"]}" stroke-width="0.25" opacity="0.35"/>
            <line x1="0" y1="0" x2="0" y2="3" stroke="{THEME["orange"]}" stroke-width="0.25" opacity="0.35"/>
        </pattern>
    </defs>

    <!-- Meter Back Panel Chassis -->
    <rect class="meter-bg" width="680" height="170" rx="6" />
    
    <!-- Metallic Bezel Lines -->
    <rect x="5" y="5" width="670" height="160" rx="4" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1" opacity="0.4" />
    
    <!-- Vent grills (retro details) -->
    <rect x="40" y="8" width="600" height="3" rx="1.5" fill="#000000" opacity="0.8"/>
    <rect x="40" y="159" width="600" height="3" rx="1.5" fill="#000000" opacity="0.8"/>
    
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
