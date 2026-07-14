#!/usr/bin/env python3
import os
import sys
import datetime
import json
import requests

# Theme parameters matching lainPfp.jpg (bronze-brown hair, silver-rimmed glasses, dark halter top)
THEME = {
    "bg": "#0c0810",               # Deepest dark violet-black
    "fg": "#eeddfc",               # Bright soft lavender/cream
    "border_active": "#b392ac",    # Soft lavender/silver active accent
    "border_inactive": "#311840",  # Muted deep purple
    "cyan": "#a5c2d8",             # Slate blue/silver (glasses glint)
    "cursor": "#b392ac",           # Soft lavender cursor
    "gold": "#dfb15b",             # Warm gold
    "pink": "#ff66cc",             # Magenta pink
    "gray": "#5d4370",             # Dark muted purple/gray
    "orange": "#ff5500",           # Nixie Orange
    "light_orange": "#ffcc66"      # Nixie Filament
}

def fetch_github_stats(username):
    """
    Fetches real public metadata from GitHub API for dynamic display.
    """
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        
    stats = {
        "repos": 8,
        "stars": 0,
        "followers": 1,
        "last_sync": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "sync_pct": "98.4%"
    }
    
    try:
        user_res = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=5)
        if user_res.status_code == 200:
            user_data = user_res.json()
            stats["repos"] = user_data.get("public_repos", stats["repos"])
            stats["followers"] = user_data.get("followers", stats["followers"])
            
        repos_res = requests.get(f"https://api.github.com/users/{username}/repos?per_page=100", headers=headers, timeout=5)
        if repos_res.status_code == 200:
            repos_data = repos_res.json()
            total_stars = sum(repo.get("stargazers_count", 0) for repo in repos_data)
            stats["stars"] = total_stars
            
        hour = datetime.datetime.now(datetime.timezone.utc).hour
        sync_val = 95.0 + (hour * 0.2)
        stats["sync_pct"] = f"{sync_val:.1f}%"
        
    except Exception as e:
        print(f"Error fetching GitHub stats: {e}.", file=sys.stderr)
        
    return stats

def generate_terminal_svg(username, stats):
    """
    Generates a stunning, 3D CRT-style terminal SVG with deep purple/neon-cyan tones.
    Features a detailed glow-line vector art of Lain with glasses (matching lainPfp.jpg)
    on the right side of the screen.
    """
    # Clean ASCII art logo (WIRED NAVI)
    ascii_art = r"""
██╗    ██╗██╗██████╗ ███████╗██████╗
██║    ██║██║██╔══██╗██╔════╝██╔══██╗
██║ █╗ ██║██║██████╔╝█████╗  ██║  ██║
██║███╗██║██║██╔══██╗██╔══╝  ██║  ██║
╚███╔███╔╝██║██║  ██║███████╗██████╔╝
 ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚══════╝╚═════╝"""

    ascii_lines = [line for line in ascii_art.split("\n") if line.strip()]
    ascii_svg_lines = ""
    y_start = 85
    for idx, line in enumerate(ascii_lines):
        escaped_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ascii_svg_lines += f'<text x="50" y="{y_start + idx*12}" fill="{THEME["border_active"]}" font-family="monospace" font-size="8.5" font-weight="bold" xml:space="preserve">{escaped_line}</text>\n'

    # Technical Skills matching user resume (excluding ROS2)
    skills = [
        {"name": "Python / PyTorch", "desc": "ML Models, TensorFlow", "level": 90, "color": THEME["cyan"]},
        {"name": "C / C++ Systems", "desc": "Algorithms, Hardware", "level": 80, "color": THEME["gold"]},
        {"name": "Web (Three.js/Flask)", "desc": "Interactive 3D Graphics", "level": 85, "color": THEME["pink"]},
        {"name": "Java / Linux Systems", "desc": "Protocol Kernels, Dotfiles", "level": 75, "color": THEME["fg"]}
    ]
    
    skills_svg = ""
    skills_y = 215
    for idx, skill in enumerate(skills):
        filled_blocks = skill["level"] // 10
        empty_blocks = 10 - filled_blocks
        bar = "■" * filled_blocks + "□" * empty_blocks
        skills_svg += f"""
        <text x="50" y="{skills_y + idx*23}" fill="{THEME["fg"]}" font-family="monospace" font-size="12">
            <tspan fill="{THEME["gray"]}">&gt; </tspan><tspan font-weight="bold">{skill["name"].ljust(20)}</tspan> 
            <tspan fill="{THEME["gray"]}">[</tspan><tspan fill="{skill["color"]}">{bar}</tspan><tspan fill="{THEME["gray"]}">]</tspan>
            <tspan fill="{THEME["gray"]}" font-size="10.5"> // {skill["desc"]}</tspan>
        </text>
        """

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 510" width="100%" height="auto">
    <style>
        .terminal-bg {{
            fill: {THEME["bg"]};
        }}
        .scanlines {{
            fill: url(#scanline-pattern);
            opacity: 0.18;
        }}
        .title-text {{
            fill: {THEME["fg"]};
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 13px;
        }}
        .console-text {{
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 14px;
            text-shadow: 0 0 3px rgba(192, 132, 252, 0.45);
        }}
        .header-glow {{
            text-shadow: 0 0 4px rgba(0, 240, 255, 0.6);
        }}
        .lain-skin {{
            stroke: {THEME["fg"]};
            stroke-width: 1.4;
            fill: none;
            opacity: 0.85;
            filter: url(#neon-glow-filter);
        }}
        .lain-hair {{
            stroke: #8c6e5e;
            stroke-width: 1.6;
            fill: none;
            opacity: 0.95;
            filter: url(#neon-glow-filter);
        }}
        .lain-glasses {{
            stroke: #d0d5dd;
            stroke-width: 1.8;
            fill: none;
            opacity: 0.95;
            filter: url(#neon-glow-filter);
        }}
        .lain-collar {{
            stroke: {THEME["pink"]};
            stroke-width: 1.6;
            fill: none;
            opacity: 0.9;
            filter: url(#neon-glow-filter);
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
        <!-- Glow Filters for Vector Art -->
        <filter id="neon-glow-filter" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
        <filter id="neon-glow-filter-cyan" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>

        <!-- Scanline Pattern -->
        <pattern id="scanline-pattern" width="850" height="6" patternUnits="userSpaceOnUse">
            <rect width="850" height="3" fill="#000" />
            <rect y="3" width="850" height="3" fill="transparent" />
        </pattern>
        
        <!-- Diagonal Cyber Grid -->
        <pattern id="cyber-grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="0.7" opacity="0.15" />
        </pattern>

        <!-- Glass Reflection Gradient -->
        <linearGradient id="glass-reflection" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.12"/>
            <stop offset="30%" stop-color="#ffffff" stop-opacity="0.04"/>
            <stop offset="31%" stop-color="#ffffff" stop-opacity="0.0"/>
            <stop offset="100%" stop-color="#ffffff" stop-opacity="0.0"/>
        </linearGradient>

        <!-- Curvature Inner Radial Shadow -->
        <radialGradient id="screen-curve" cx="50%" cy="50%" r="50%">
            <stop offset="80%" stop-color="#000000" stop-opacity="0.0"/>
            <stop offset="95%" stop-color="#000000" stop-opacity="0.4"/>
            <stop offset="100%" stop-color="#000000" stop-opacity="0.75"/>
        </radialGradient>

        <!-- Bezel Metallic Border -->
        <linearGradient id="bezel-metallic" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#2d153d"/>
            <stop offset="50%" stop-color="#150820"/>
            <stop offset="100%" stop-color="#09030d"/>
        </linearGradient>
    </defs>

    <!-- Bezel Monitor Frame (3D Casing) -->
    <rect x="0" y="0" width="850" height="510" rx="14" fill="url(#bezel-metallic)" stroke="{THEME["border_active"]}" stroke-width="1.2" />
    <!-- Bezel Highlight line -->
    <rect x="6" y="6" width="838" height="498" rx="10" fill="none" stroke="#522a6b" stroke-width="1.5" opacity="0.6" />

    <!-- Screen Bezel Cutout -->
    <rect x="14" y="14" width="822" height="482" rx="8" class="terminal-bg" />
    
    <!-- Immersive Background Silhouette: Telephone Pole and Powerlines (Lain visual essence) -->
    <g opacity="0.2">
        <!-- Power Pole -->
        <line x1="720" y1="14" x2="720" y2="496" stroke="#251233" stroke-width="8" />
        <line x1="640" y1="100" x2="800" y2="100" stroke="#251233" stroke-width="4" />
        <line x1="660" y1="180" x2="780" y2="180" stroke="#251233" stroke-width="3" />
        <!-- Diagonal wires -->
        <path d="M 0 120 Q 400 280, 720 180" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.2" />
        <path d="M 0 160 Q 400 320, 720 180" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.2" />
        <path d="M 0 80 Q 350 200, 720 100" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" />
        <path d="M 0 40 Q 350 160, 720 100" fill="none" stroke="{THEME["border_inactive"]}" stroke-width="1.5" />
    </g>

    <!-- Diagonal Cyber Grid -->
    <rect x="14" y="14" width="822" height="482" fill="url(#cyber-grid)" rx="8" />
    
    <!-- CRT Effect Scanlines -->
    <rect x="14" y="14" width="822" height="482" class="scanlines" rx="8" pointer-events="none" />
    
    <!-- Sweeping Laser Scanline (CRT electron gun sweep) -->
    <rect x="15" y="35" width="820" height="2" fill="{THEME["cyan"]}" opacity="0.25" pointer-events="none">
        <animate attributeName="y" from="35" to="490" dur="8s" repeatCount="indefinite" />
    </rect>
    
    <!-- Header Bar inside screen -->
    <rect x="14" y="14" width="822" height="35" rx="8" fill="{THEME["border_inactive"]}" />
    <!-- Window buttons -->
    <circle cx="34" cy="32" r="5" fill="{THEME["pink"]}" />
    <circle cx="50" cy="32" r="5" fill="{THEME["gold"]}" />
    <circle cx="66" cy="32" r="5" fill="{THEME["cyan"]}" />
    
    <!-- Header Title -->
    <text x="425" y="36" class="title-text" text-anchor="middle" font-weight="bold">Wired-Navi0x1F@NAVI-Terminal:~ (Protocol: Layer_07_Active)</text>
    
    <!-- Vector Art of Lain with Glasses (lainPfp.jpg wireframe representation) -->
    <g transform="translate(180, 20)">
        <!-- Face Contour -->
        <path class="lain-skin" d="M 400 180 C 400 270, 420 310, 460 325 C 500 310, 520 270, 520 180" />
        
        <!-- Hair Outline (Signature Bob) -->
        <path class="lain-hair" d="M 370 180 C 360 120, 400 70, 460 70 C 520 70, 560 120, 550 180 C 550 230, 530 250, 530 280 C 530 290, 540 300, 545 320" />
        <path class="lain-hair" d="M 370 180 C 375 220, 390 240, 395 270" />
        
        <!-- Left Side Bangs & signature long strand with hairband -->
        <path class="lain-hair" d="M 390 120 C 385 150, 390 200, 390 250 C 390 270, 385 320, 395 360 C 400 380, 410 400, 405 440" />
        
        <!-- Glasses (Silver Rims) -->
        <path class="lain-glasses" d="M 412 195 L 452 203 L 452 220 L 412 212 Z" /> <!-- Left Rim -->
        <path class="lain-glasses" d="M 468 206 L 508 214 L 508 231 L 468 223 Z" /> <!-- Right Rim -->
        <path class="lain-glasses" d="M 452 207 Q 460 209, 468 211" /> <!-- Bridge -->
        <path class="lain-glasses" d="M 412 197 C 400 190, 395 180, 390 178" /> <!-- Left Temple -->
        <path class="lain-glasses" d="M 508 216 C 520 210, 525 200, 530 198" /> <!-- Right Temple -->
        
        <!-- Eyes (Quiet expression behind glasses) -->
        <path class="lain-skin" d="M 422 205 Q 432 202, 442 207" />
        <path class="lain-skin" d="M 478 214 Q 488 211, 498 216" />
        <circle cx="432" cy="209" r="2" fill="{THEME["border_active"]}" />
        <circle cx="488" cy="218" r="2" fill="{THEME["border_active"]}" />
        
        <!-- Mouth & Nose -->
        <path class="lain-skin" d="M 460 248 L 464 250" /> <!-- Nose -->
        <path class="lain-skin" d="M 455 285 Q 460 288, 465 285" /> <!-- Mouth -->
        
        <!-- Neck & Halter Top Collar -->
        <path class="lain-skin" d="M 440 320 L 440 360 C 430 380, 420 400, 410 430" /> <!-- Neck Left -->
        <path class="lain-skin" d="M 480 318 L 480 360 C 490 380, 500 400, 510 430" /> <!-- Neck Right -->
        <path class="lain-collar" d="M 432 360 Q 460 370, 488 360 C 495 380, 520 440, 530 460 M 428 360 C 420 380, 395 440, 385 460" /> <!-- Collar / Dress -->
    </g>

    <!-- System Diagnostics Block -->
    <g class="console-text">
        <!-- Diagnostic Block (Right Side) -->
        <rect x="525" y="70" width="280" height="110" rx="4" fill="{THEME["bg"]}" stroke="{THEME["border_inactive"]}" stroke-width="1.5" />
        <text x="540" y="92" fill="{THEME["cyan"]}" font-family="monospace" font-size="11" font-weight="bold" class="header-glow">[SYSTEM DIAGNOSTICS]</text>
        <text x="540" y="112" fill="{THEME["fg"]}" font-family="monospace" font-size="10.5">NODE: {username}</text>
        <text x="540" y="130" fill="{THEME["fg"]}" font-family="monospace" font-size="10.5">ACTIVE MODULES: {stats["repos"]}</text>
        <text x="540" y="148" fill="{THEME["fg"]}" font-family="monospace" font-size="10.5">SYNC RATE: {stats["sync_pct"]}</text>
        <text x="540" y="166" fill="{THEME["fg"]}" font-family="monospace" font-size="9.5" fill-opacity="0.7">LAST SYNC: {stats["last_sync"].split()[0]}</text>
        
        <!-- Welcome Messages -->
        <text x="50" y="75" fill="{THEME["cyan"]}" font-family="monospace" font-size="13" font-weight="bold" class="header-glow">&gt; Initializing NAVI-OS v7.25...</text>
        
        <!-- ASCII Logo -->
        {ascii_svg_lines}
        
        <!-- Divider -->
        <line x1="50" y1="200" x2="500" y2="200" stroke="{THEME["border_inactive"]}" stroke-width="1.5" stroke-dasharray="5 5" />
        
        <!-- Skills Header -->
        <text x="50" y="210" fill="{THEME["gold"]}" font-family="monospace" font-size="12" font-weight="bold">&gt;_ core_modules_loaded</text>
        
        <!-- Skills/Languages List -->
        {skills_svg}
        
        <!-- Connected Nodes Section -->
        <text x="50" y="325" fill="{THEME["cyan"]}" font-family="monospace" font-size="12" font-weight="bold" class="header-glow">&gt;_ connected_nodes</text>
        <text x="50" y="344" fill="{THEME["fg"]}" font-family="monospace" font-size="12">
            <tspan fill="{THEME["gray"]}">&gt; </tspan>Website: <tspan fill="{THEME["cyan"]}">https://pr0t0lain.dpdns.org</tspan>
        </text>
        <text x="50" y="362" fill="{THEME["fg"]}" font-family="monospace" font-size="12">
            <tspan fill="{THEME["gray"]}">&gt; </tspan>LinkedIn: <tspan fill="{THEME["cyan"]}">https://in.linkedin.com/in/haru-l41n-pr0t0</tspan>
        </text>
        
        <!-- Oscilloscope Waveform Animation -->
        <g>
            <path d="M 0 410 C 50 380, 100 440, 150 410 C 200 380, 250 440, 300 410 C 350 380, 400 440, 450 410 C 500 380, 550 440, 600 410 C 650 380, 700 440, 750 410" fill="none" stroke="{THEME["cyan"]}" stroke-width="1.5" opacity="0.3">
                <animateTransform attributeName="transform" type="translate" from="0,0" to="-300,0" dur="4.5s" repeatCount="indefinite" />
            </path>
            <path d="M 0 410 C 60 430, 120 390, 180 410 C 240 430, 300 390, 360 410 C 420 430, 480 390, 540 410 C 600 430, 660 390, 720 410" fill="none" stroke="{THEME["pink"]}" stroke-width="1" opacity="0.2">
                <animateTransform attributeName="transform" type="translate" from="0,0" to="-360,0" dur="6.5s" repeatCount="indefinite" />
            </path>
        </g>
        
        <!-- Blinking Prompt -->
        <text x="50" y="465" fill="{THEME["fg"]}" font-family="monospace" font-size="13">
            <tspan fill="{THEME["cyan"]}">Wired-Navi0x1F@wired</tspan>:<tspan fill="{THEME["pink"]}">~</tspan>$ <tspan fill="{THEME["fg"]}">close_world --open-next</tspan>
        </text>
        <rect x="424" y="452" width="8" height="15" class="cursor" />
    </g>

    <!-- Curvature shadow overlay -->
    <rect x="14" y="14" width="822" height="482" fill="url(#screen-curve)" rx="8" pointer-events="none" />

    <!-- Glass Reflection glare overlay -->
    <rect x="14" y="14" width="822" height="482" fill="url(#glass-reflection)" rx="8" pointer-events="none" />
</svg>
"""
    return svg_content


def generate_divergence_meter_svg():
    """
    Generates a high-fidelity Steins;Gate Divergence Meter SVG using glowing Nixie Tubes.
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
                
                <!-- Active Glowing Digit -->
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
            font-size: 9px;
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
    
    <!-- Nixie Tubes Group -->
    <g class="divergence-glow" transform="translate(10, 5)">
        {nixie_tubes}
    </g>
    
    <!-- Panel label -->
    <text x="640" y="152" class="label-text" text-anchor="end">TARGET DIVERGENCE: 1.048596% // STEINS;GATE WORLD LINE METER</text>
</svg>
"""
    return svg_content


def main():
    username = "Wired-Navi0x1F"
    
    print("Fetching live data from GitHub API...")
    stats = fetch_github_stats(username)
    
    print("Generating retro terminal card...")
    terminal_svg = generate_terminal_svg(username, stats)
    with open("terminal.svg", "w", encoding="utf-8") as f:
        f.write(terminal_svg)
        
    print("Generating Nixie Divergence Meter...")
    divergence_svg = generate_divergence_meter_svg()
    with open("divergence_meter.svg", "w", encoding="utf-8") as f:
        f.write(divergence_svg)

    print("Generating README.md...")
    # Generate the Markdown file structure with clean layout, exact resume facts, and lightbox click prevention
    readme_content = f"""# 🌐 Wired-Navi0x1F

<div align="center">
  <!-- Waving Gradient Banner matching Lain's palette -->
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:120e16,50:8c6e5e,100:cfa5df&height=180&section=header&text=Wired-Navi0x1F&fontColor=eeddfc&fontSize=45&animation=fadeIn&fontAlignY=35&desc=Close%20the%20world,%20open%20the%20nExt%20//%20Layer%2007%20Wired%20Node&descAlignY=55&descSize=16" width="100%" alt="Wired Header" />
</div>

<br />

<div align="center">
  <picture>
    <img src="terminal.svg?v=9" width="850" alt="Lain-themed NAVI terminal showing system parameters and technical skills" style="max-width: 100%; height: auto;" />
  </picture>
</div>

<br />

<div align="center">
  <picture>
    <img src="divergence_meter.svg?v=9" width="680" alt="Steins;Gate Nixie Tube World Line Divergence Meter displaying 1.048596%" style="max-width: 100%; height: auto;" />
  </picture>
</div>

<br />

<div align="center">
  <a href="https://pr0t0lain.dpdns.org" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/🌐_NODE_DOMAIN-pr0t0lain.dpdns.org-00f0ff?style=for-the-badge&logo=internet-explorer&logoColor=ffffff&labelColor=150a21" alt="Website Link" />
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://in.linkedin.com/in/haru-l41n-pr0t0" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/💼_GUILD_LINK-linkedin.com/in/haru--l41n--pr0t0-ff66cc?style=for-the-badge&logo=linkedin&logoColor=ffffff&labelColor=150a21" alt="LinkedIn Link" />
  </a>
</div>

<br />

## ─── 📡 BIOLOGICAL NODE PARAMETERS (ABOUT ME) ───

I am a Computer Science & Engineering student specializing in Artificial Intelligence, Machine Learning, and low-level system logic. I design and build secure environments where neural algorithms interface with physical data layers.

*   💬 **Areas of Interest & System Nodes:**
    *   **Deep Learning & Predictive Systems:** GMM-based trajectory prediction, uncertainty estimation (Monte Carlo dropout), and explainable AI pipelines.
    *   **3D Graphics & Data Visualization:** Node-link force-directed graphs, Three.js/WebGL network mapping, and dynamic knowledge interfaces.
    *   **Systems Customization & Ricing:** Hyprland window manager configurations, shell scripting, Linux kernel optimization, and retro terminal aesthetics.
    *   **Software Architecture:** Lightweight Python microservices, Java system protocol modules, and automated CI/CD synchronization nodes.

---

### 🧠 CORE SYSTEM SPECS (TECH STACK)

*   **Programming Languages:** `Python`, `C`, `C++`, `HTML5`, `CSS3`, `JavaScript`
*   **Frameworks & Libraries:** `TensorFlow`, `PyTorch`, `Pandas`, `NumPy`, `FastAPI`, `Flask`, `Three.js`
*   **Tools & Environments:** `Git`, `GitHub`, `Linux`, `VS Code`, `Jupyter`

---

### 🕸️ ACTIVE PROJECT NODES (FEATURED PROJECTS)

*   ⚡ **[Synapse Notes Web Application](https://github.com/Wired-Navi0x1F/synapse-notes)**
    *   *A markdown-based note editing system with live preview and 3D relationship mapping.*
    *   **Features:** Developed guest authentication, archive vaulting, markdown rendering, and "The Wired" (an interactive **Three.js** 3D note relationship graph).
    *   **Technologies:** Flask, MySQL, JavaScript, Three.js, Python.
*   🚘 **[Bayesian MPC Predictive Agent](https://github.com/Wired-Navi0x1F/Enigmaa)**
    *   *Trajectory prediction and active collision prevention agent for autonomous vehicles.*
    *   **Features:** Implemented a GMM-based Bayesian trajectory prediction model, Monte Carlo dropout, and Hard Shield AEB safety modules.
    *   **Technologies:** PyTorch, highway-env, Gymnasium, Python.

---

### 🕹️ CONSOLE CONTRIBUTION MATRIX (SNAKE GAME)

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="github-contribution-grid-snake-dark.svg?v=9" />
    <img src="github-contribution-grid-snake.svg?v=9" alt="NAVI Grid Contribution Snake Game" width="850" style="max-width: 100%; height: auto;" />
  </picture>
</div>

---

### 🕸️ THE WIRED WEBRING (OCTO RING)

<div align="center">
  <table border="0" cellpadding="10" cellspacing="0" style="border: 2.5px solid #311840; border-radius: 8px; background: #0b0512; max-width: 420px; width: 100%;">
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
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/prev" style="color: #ff66cc; text-decoration: none; font-weight: bold;">&larr; Prev</a>
          <span style="color: #5d4370;"> | </span>
          <a href="https://octo-ring.com" style="color: #eeddfc; text-decoration: none; font-weight: bold;">Octo Ring Hub</a>
          <span style="color: #5d4370;"> | </span>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/random" style="color: #eab308; text-decoration: none;">🎲 Random</a>
          <span style="color: #5d4370;"> | </span>
          <a href="https://octo-ring.com/p/Wired-Navi0x1F/next" style="color: #ff66cc; text-decoration: none; font-weight: bold;">Next &rarr;</a>
        </td>
      </tr>
    </tbody>
  </table>
</div>

---

### ⚙️ SYSTEM STATE (`/dev/status`)

```
[SYSTEM PARAMETERS]
> CURRENT_PROJECT:  Synapse Notes (Flask + MySQL + Three.js 3D graph)
> CURRENT_RESEARCH: Bayesian MPC Predictive Agent (PyTorch)
> COMPILER_TARGET:  Real-time trajectory prediction with GMM and Monte Carlo dropout
```

---

### 🎙️ Transmission Received

<table width="100%" border="0" cellspacing="0" cellpadding="10" style="border: none;">
  <tr>
    <td width="30%" align="center" valign="middle" style="border: none;">
      <img src="lain-wired.gif" width="180" alt="Lain connected to the Wired" style="border-radius: 4px;" />
    </td>
    <td width="70%" valign="middle" style="border: none; font-family: monospace; line-height: 1.6; color: #eeddfc;">
      <p><i>"No matter where you are, everyone is always connected. Even if you die, your consciousness remains in the Wired."</i><br>
      <strong>— Serial Experiments Lain</strong></p>
      <br />
      <p><i>"This is the choice of Steins;Gate. The world line can be rewritten. El Psy Kongroo."</i><br>
      <strong>— Okabe Rintaro (Steins;Gate)</strong></p>
    </td>
  </tr>
</table>

---

<div align="center">
  <p align="center" style="font-family: monospace; color: {THEME["gray"]}; font-size: 11px;">
    WIRED PROTOCOL INITIATED // IP STATE: SECURE // CLOSE THE WORLD, OPEN THE NEXT.
  </p>
</div>
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Success! Profile files generated.")

if __name__ == "__main__":
    main()
