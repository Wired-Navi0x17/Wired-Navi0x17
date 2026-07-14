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
    Reads the minified terminal SVG from the filesystem.
    """
    with open("terminal.svg", "r", encoding="utf-8") as f:
        return f.read()


def generate_divergence_meter_svg():
    """
    Reads the Nixie Divergence Meter SVG from the filesystem.
    """
    with open("divergence_meter.svg", "r", encoding="utf-8") as f:
        return f.read()



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
  <picture>
    <img src="terminal.svg?v=6" width="850" alt="Lain-themed NAVI terminal showing system parameters and technical skills" style="max-width: 100%; height: auto;" />
  </picture>
</div>

<br />

<div align="center">
  <picture>
    <img src="divergence_meter.svg?v=6" width="680" alt="Steins;Gate Nixie Tube World Line Divergence Meter displaying 1.048596%" style="max-width: 100%; height: auto;" />
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

I am a **Computer Science & Engineering (CSE)** student at **RV University** (Bengaluru, India), specializing in Artificial Intelligence, Machine Learning, and low-level system logic. I build systems where neural algorithms interface with physical data layers.

*   🔭 **Current Project & Research:** Developing **Synapse Notes**, a dynamic markdown-based knowledge management web app featuring **Three.js** 3D force-directed node-link graph mapping.
*   🤖 **Predictive Agent Systems:** Engineering **Bayesian MPC Predictive Agents** for autonomous driving environments, implementing trajectory prediction GMM heads, Monte Carlo dropout, and **ROS2** control workflows.
*   🦾 **Academic Pursuits:** Pursuing my B.Tech (Hons.) in Artificial Intelligence & Machine Learning (2025 – Present), specializing in AI robustness, data structures, and real-time inference.

---

### 🧠 CORE SYSTEM SPECS (TECH STACK)

*   **Programming Languages:** `Python`, `C`, `C++`, `HTML5`, `CSS3`, `JavaScript`
*   **Frameworks & Libraries:** `TensorFlow`, `PyTorch`, `Pandas`, `NumPy`, `FastAPI`, `Flask`, `Three.js`
*   **Tools & Environments:** `Git`, `GitHub`, `Linux`, `ROS2`, `VS Code`, `Jupyter`

---

### 🕸️ ACTIVE PROJECT NODES (FEATURED PROJECTS)

*   ⚡ **[Synapse Notes Web Application](https://github.com/Wired-Navi0x1F/synapse-notes)**
    *   *A markdown-based note editing system with live preview and 3D relationship mapping.*
    *   **Features:** Developed guest authentication, archive vaulting, markdown rendering, and "The Wired" (an interactive **Three.js** 3D note network mapping notes' relationships).
    *   **Technologies:** Flask, MySQL, JavaScript, Three.js, Python.
*   🚘 **[Bayesian MPC Predictive Agent](https://github.com/Wired-Navi0x1F/Enigmaa)**
    *   *Trajectory prediction and active collision prevention agent for autonomous vehicles.*
    *   **Features:** Implemented a GMM-based Bayesian trajectory prediction model, Monte Carlo dropout, Hard Shield AEB safety modules, and **ROS2** vehicle simulation control workflows.
    *   **Technologies:** PyTorch, highway-env, Gymnasium, ROS2.

---

### ⚙️ SYSTEM STATE (`/dev/status`)

```
[SYSTEM PARAMETERS]
> CURRENT_PROJECT:  Synapse Notes (Flask + MySQL + Three.js 3D graph)
> CURRENT_RESEARCH: Bayesian MPC Predictive Agent (PyTorch + ROS2)
> COMPILER_TARGET:  Real-time trajectory prediction with GMM and Monte Carlo dropout
```

---

### 🎙️ Transmission Received

<table width="100%" border="0" cellspacing="0" cellpadding="10" style="border: none;">
  <tr>
    <td width="30%" align="center" valign="middle" style="border: none;">
      <img src="lain-wired.gif" width="180" alt="Lain connected to the Wired" style="border-radius: 4px;" />
    </td>
    <td width="70%" valign="middle" style="border: none; font-family: monospace; line-height: 1.6;">
      <p><i>"No matter where you are, everyone is always connected. Even if you die, your consciousness remains in the Wired."</i><br>
      <strong>— Serial Experiments Lain</strong></p>
      <br>
      <p><i>"This is the choice of Steins;Gate. The world line can be rewritten. El Psy Kongroo."</i><br>
      <strong>— Okabe Rintaro (Steins;Gate)</strong></p>
    </td>
  </tr>
</table>

---

<div align="center">
  <p align="center" style="font-family: monospace; color: #5d4370; font-size: 11px;">
    WIRED PROTOCOL INITIATED // IP STATE: SECURE // CLOSE THE WORLD, OPEN THE NEXT.
  </p>
</div>
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Success! Profile files generated.")

if __name__ == "__main__":
    main()
