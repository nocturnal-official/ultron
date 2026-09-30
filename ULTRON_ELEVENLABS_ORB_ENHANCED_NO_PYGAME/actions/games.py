"""Steam / Epic game management via official URL schemes (no screen-scraping)."""
import os
import platform
import re
import subprocess
from pathlib import Path

_OS = platform.system()


def _steam_path():
    if _OS == "Windows":
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    k = winreg.OpenKey(hive, key)
                    val, _ = winreg.QueryValueEx(k, "InstallPath" if hive == winreg.HKEY_LOCAL_MACHINE else "SteamPath")
                    if Path(val).exists():
                        return Path(val)
                except OSError:
                    continue
        except ImportError:
            pass
        for c in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
            if Path(c).exists():
                return Path(c)
    elif _OS == "Darwin":
        p = Path.home() / "Library/Application Support/Steam"
        return p if p.exists() else None
    else:
        for c in (Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"):
            if c.exists():
                return c
    return None


def _steam_games(steam):
    games = []
    libs = [steam / "steamapps"]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore")):
            lib = Path(m.replace("\\\\", "/")) / "steamapps"
            if lib.exists():
                libs.append(lib)
    for lib in libs:
        for acf in lib.glob("appmanifest_*.acf"):
            t = acf.read_text(errors="ignore")
            aid = re.search(r'"appid"\s+"(\d+)"', t)
            name = re.search(r'"name"\s+"([^"]+)"', t)
            if aid and name:
                games.append((aid.group(1), name.group(1)))
    return games


def _launch_steam_url(url):
    if _OS == "Darwin":
        subprocess.Popen(["open", url])
    elif _OS == "Linux":
        subprocess.Popen(["xdg-open", url])
    else:
        os.startfile(url)  # noqa


def game_updater(action: str = "update", platform_name: str = "steam",
                 game_name: str = "") -> str:
    a = (action or "update").lower().strip()
    steam = _steam_path()
    if not steam:
        return "Steam doesn't appear to be installed."
    try:
        games = _steam_games(steam)
        if a == "list":
            if not games:
                return "No Steam games found."
            return f"{len(games)} Steam games: " + ", ".join(n for _, n in games[:15])
        if a in ("update", "install"):
            if game_name:
                match = [(i, n) for i, n in games if game_name.lower() in n.lower()]
                if match:
                    aid, name = match[0]
                    _launch_steam_url(f"steam://update/{aid}")
                    return f"Asked Steam to update/verify '{name}'."
                _launch_steam_url(f"steam://store/{game_name}")
                return f"'{game_name}' isn't installed; opened its Steam store page."
            for aid, _ in games:
                _launch_steam_url(f"steam://update/{aid}")
            return f"Triggered update checks for {len(games)} Steam games."
        return f"Unknown game action '{action}'. Use update, install, list."
    except Exception as e:
        return f"Game updater failed: {e}"
