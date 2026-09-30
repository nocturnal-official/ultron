"""File and folder operations, scoped to the user's home directory for safety."""
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    import send2trash
    _TRASH = True
except ImportError:
    _TRASH = False

_HOME = Path.home()


def _xdg(name, default):
    v = os.environ.get(name, "")
    return Path(v) if v and Path(v).exists() else _HOME / default


_SHORTCUTS = {
    "desktop": _xdg("XDG_DESKTOP_DIR", "Desktop"),
    "downloads": _xdg("XDG_DOWNLOAD_DIR", "Downloads"),
    "documents": _xdg("XDG_DOCUMENTS_DIR", "Documents"),
    "pictures": _xdg("XDG_PICTURES_DIR", "Pictures"),
    "music": _xdg("XDG_MUSIC_DIR", "Music"),
    "videos": _xdg("XDG_VIDEOS_DIR", "Videos"),
    "home": _HOME,
}


def _resolve(raw: str) -> Path:
    return _SHORTCUTS.get((raw or "").strip().lower(), Path(raw or ".").expanduser())


def _safe(p: Path) -> bool:
    try:
        r = p.resolve()
        return r == _HOME.resolve() or r.is_relative_to(_HOME.resolve())
    except Exception:
        return False


def _fmt(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def file_op(action: str, path: str = "desktop", name: str = "", destination: str = "",
            new_name: str = "", content: str = "", extension: str = "") -> str:
    a = (action or "").lower().strip()
    base = _resolve(path)
    target = (base / name) if name else base
    try:
        if a == "list":
            if not target.is_dir():
                return f"Not a folder: {target}"
            items = []
            for it in sorted(target.iterdir()):
                if it.name.startswith("."):
                    continue
                items.append(f"[dir] {it.name}/" if it.is_dir()
                             else f"{it.name} ({_fmt(it.stat().st_size)})")
            return f"{target} ({len(items)} items):\n" + "\n".join(items[:100]) if items else "Empty folder."
        if not _safe(target):
            return f"Access denied (outside home folder): {target}"
        if a == "read":
            if not target.is_file():
                return f"Not a file: {target}"
            txt = target.read_text(encoding="utf-8", errors="ignore")
            return txt[:6000] + (f"\n\n[truncated, {len(txt)} chars total]" if len(txt) > 6000 else "")
        if a == "create_file":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Created file: {target}"
        if a == "create_folder":
            target.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {target}"
        if a == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Wrote {target.name}"
        if a == "delete":
            if not target.exists():
                return f"Not found: {target}"
            if target.resolve() in {p.resolve() for p in _SHORTCUTS.values()}:
                return "That's a protected folder; I won't delete it."
            if not _TRASH:
                return "send2trash isn't installed, so I won't hard-delete. Run: pip install send2trash"
            send2trash.send2trash(str(target))
            return f"Moved to Recycle Bin: {target.name}"
        if a in ("move", "copy"):
            dst = _resolve(destination)
            if not target.exists():
                return f"Source not found: {target}"
            if not _safe(dst):
                return f"Access denied (destination): {dst}"
            if dst.is_dir():
                dst = dst / target.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if a == "move":
                shutil.move(str(target), str(dst))
                return f"Moved to {dst}"
            (shutil.copytree if target.is_dir() else shutil.copy2)(str(target), str(dst))
            return f"Copied to {dst}"
        if a == "rename":
            if not new_name:
                return "No new name given."
            newp = target.parent / new_name
            if newp.exists():
                return f"'{new_name}' already exists there."
            target.rename(newp)
            return f"Renamed to {new_name}"
        if a == "find":
            hits = []
            for it in base.rglob("*"):
                if it.is_file() and (not name or name.lower() in it.name.lower()) \
                        and (not extension or it.suffix.lower() == extension.lower()):
                    hits.append(f"{it.name} — {it.parent}")
                    if len(hits) >= 30:
                        break
            return f"Found {len(hits)}:\n" + "\n".join(hits) if hits else "No matches."
        if a == "disk_usage":
            u = shutil.disk_usage(base)
            return f"Disk {base}: {_fmt(u.used)} used / {_fmt(u.total)} ({u.used/u.total*100:.0f}%), {_fmt(u.free)} free"
        return f"Unknown file action '{action}'."
    except Exception as e:
        return f"File op failed: {e}"


_TYPES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md"},
    "Videos": {".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v"},
    "Music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".cpp", ".go", ".rs"},
}


def set_wallpaper(image_path: str) -> str:
    import platform
    import subprocess
    p = Path(image_path).expanduser()
    if not p.is_file():
        return f"Image not found: {p}"
    osname = platform.system()
    try:
        if osname == "Windows":
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(p), 3)
        elif osname == "Darwin":
            subprocess.run(["osascript", "-e",
                            f'tell application "System Events" to tell every desktop to set picture to POSIX file "{p}"'],
                           capture_output=True)
        else:
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{p}"],
                           capture_output=True)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", f"file://{p}"],
                           capture_output=True)
        return f"Wallpaper set to {p.name}."
    except Exception as e:
        return f"Couldn't set wallpaper: {e}"


def organize_folder(path: str = "desktop") -> str:
    folder = _resolve(path)
    if not _safe(folder) or not folder.is_dir():
        return f"Can't organize {folder}."
    moved = 0
    for it in list(folder.iterdir()):
        if it.is_dir() or it.name.startswith(".") or it.name in _TYPES:
            continue
        dest_name = next((k for k, v in _TYPES.items() if it.suffix.lower() in v), "Others")
        d = folder / dest_name
        d.mkdir(exist_ok=True)
        if not (d / it.name).exists():
            shutil.move(str(it), str(d / it.name))
            moved += 1
    return f"Organized {folder.name}: {moved} files sorted into type folders."
