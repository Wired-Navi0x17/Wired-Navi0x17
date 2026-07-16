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

def load_status_yml(filepath):
    """
    Parses status.yml to load user status parameters (supports scalars and list blocks).
    """
    data = {}
    if not os.path.exists(filepath):
        return data
    current_key = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("-"):
                # It's a list item under current_key
                item = stripped[1:].strip()
                if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                    item = item[1:-1]
                if current_key:
                    if not isinstance(data.get(current_key), list):
                        data[current_key] = []
                    data[current_key].append(item)
            elif ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if val == "":
                    data[key] = []
                else:
                    data[key] = val
                current_key = key
    return data


def update_terminal_svg(stats):
    """
    Updates telemetry parameters inside terminal.svg inline.
    """
    if not os.path.exists("terminal.svg"):
        print("terminal.svg not found. Skipping inline update.")
        return
        
    with open("terminal.svg", "r", encoding="utf-8") as f:
        svg_content = f.read()

    import re
    # Update public repos
    svg_content = re.sub(
        r"ACTIVE MODULES:\s*\d+",
        f"ACTIVE MODULES: {stats['repos']}",
        svg_content
    )
    # Update sync percentage
    svg_content = re.sub(
        r"SYNC RATE:\s*\d+(\.\d+)?%",
        f"SYNC RATE: {stats['sync_pct']}",
        svg_content
    )
    # Update last sync timestamp (keeping it clean with only date YYYY-MM-DD)
    date_str = stats['last_sync'].split()[0]
    svg_content = re.sub(
        r"LAST SYNC:\s*\d{4}-\d{2}-\d{2}",
        f"LAST SYNC: {date_str}",
        svg_content
    )

    with open("terminal.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("Updated terminal.svg telemetry.")


def update_readme_system_state(status):
    """
    Updates the /dev/status block inside README.md dynamically between markers.
    """
    if not os.path.exists("README.md"):
        print("README.md not found. Skipping inline update.")
        return

    with open("README.md", "r", encoding="utf-8") as f:
        readme_content = f.read()

    start_marker = "<!--SYSTEM_STATE:START-->"
    end_marker = "<!--SYSTEM_STATE:END-->"

    if start_marker in readme_content and end_marker in readme_content:
        import subprocess

        # Get OS dynamically
        try:
            os_name = subprocess.check_output("grep PRETTY_NAME /etc/os-release | cut -d'\"' -f2", shell=True, text=True).strip()
        except Exception:
            os_name = "CachyOS"

        # Get Kernel dynamically
        try:
            kernel_name = subprocess.check_output("uname -r", shell=True, text=True).strip()
        except Exception:
            kernel_name = "7.1.3-2-cachyos"

        # Get Shell dynamically
        shell_path = os.environ.get("SHELL")
        if not shell_path:
            try:
                import pwd
                shell_path = pwd.getpwuid(os.getuid()).pw_shell
            except Exception:
                shell_path = "/bin/bash"
        shell_name = os.path.basename(shell_path)

        new_block = f"""Wired-Navi0x1F@arch
-------------------
OS: {os_name}
Host: Layer 07 // The Wired
Kernel: {kernel_name}
Uptime: Always Connected
Shell: {shell_name}
Project: {status.get('current_project', '')}
Research: {status.get('current_research', '')}
Target: {status.get('compiler_target', '')}"""

        import re
        readme_content = re.sub(
            f"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
            f"{start_marker}\n```\n{new_block}\n```\n{end_marker}",
            readme_content,
            flags=re.DOTALL
        )

        with open("README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("Updated README.md /dev/status parameters.")
    else:
        print("Markers not found in README.md. Skipping.")


def update_readme_staged_ideas(status):
    """
    Updates the ideas backlog inside README.md dynamically between markers.
    """
    if not os.path.exists("README.md"):
        print("README.md not found. Skipping inline update.")
        return

    with open("README.md", "r", encoding="utf-8") as f:
        readme_content = f.read()

    start_marker = "<!--STAGED_IDEAS:START-->"
    end_marker = "<!--STAGED_IDEAS:END-->"

    if start_marker in readme_content and end_marker in readme_content:
        ideas = status.get("staged_ideas", [])
        if isinstance(ideas, list) and ideas:
            markdown_list = "\n".join(f"*   {idea}" for idea in ideas)
        else:
            markdown_list = "*   *No active ideas staged at the moment.*"

        import re
        readme_content = re.sub(
            f"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
            f"{start_marker}\n{markdown_list}\n{end_marker}",
            readme_content,
            flags=re.DOTALL
        )

        with open("README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("Updated README.md staged ideas.")
    else:
        print("Staged ideas markers not found in README.md. Skipping.")


def main():
    username = "Wired-Navi0x1F"
    
    print("Loading status parameters from status.yml...")
    status = load_status_yml("status.yml")
    
    print("Fetching live data from GitHub API...")
    stats = fetch_github_stats(username)
    
    # If custom sync rate is set in status.yml, override the dynamic sync rate
    if "sync_rate" in status:
        stats["sync_pct"] = f"{status['sync_rate']}%"
        
    print("Updating terminal.svg telemetry...")
    update_terminal_svg(stats)
        
    print("Updating README.md system state...")
    update_readme_system_state(status)

    print("Updating README.md staged ideas...")
    update_readme_staged_ideas(status)

    print("Success! Profile dynamic files updated.")


if __name__ == "__main__":
    main()
