"""Direct desktop control: type, click, hotkeys, scroll, screenshot, find-on-screen."""
import platform
import time
from datetime import datetime
from pathlib import Path

_OS = platform.system()
_SHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"


def _pg():
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    return pyautogui


def computer_control(action: str, text: str = "", x=None, y=None, keys: str = "",
                     key: str = "", direction: str = "down", amount: int = 3,
                     description: str = "") -> str:
    """action: type|click|double_click|right_click|hotkey|press|scroll|move|
    screenshot|screen_find|screen_click"""
    a = (action or "").lower().strip()
    try:
        pg = _pg()
    except ImportError:
        return "pyautogui isn't installed. Run: pip install pyautogui"
    try:
        if a == "type":
            try:
                import pyperclip
                pyperclip.copy(text)
                time.sleep(0.1)
                pg.hotkey("command" if _OS == "Darwin" else "ctrl", "v")
            except Exception:
                pg.typewrite(text, interval=0.02)
            return f"Typed {len(text)} chars."
        if a in ("click", "double_click", "right_click"):
            btn = "right" if a == "right_click" else "left"
            clicks = 2 if a == "double_click" else 1
            if x is not None and y is not None:
                pg.click(int(x), int(y), button=btn, clicks=clicks)
            else:
                pg.click(button=btn, clicks=clicks)
            return f"{a} done."
        if a == "hotkey":
            parts = [k.strip() for k in keys.replace("+", " ").split()]
            pg.hotkey(*parts)
            return f"Pressed {'+'.join(parts)}"
        if a == "press":
            pg.press(key or "enter")
            return f"Pressed {key or 'enter'}"
        if a == "scroll":
            pg.scroll((amount if direction == "up" else -amount) * 100)
            return f"Scrolled {direction}."
        if a == "move":
            pg.moveTo(int(x), int(y), duration=0.3)
            return f"Moved to ({x},{y})"
        if a == "screenshot":
            _SHOT_DIR.mkdir(exist_ok=True)
            p = _SHOT_DIR / f"screen_{datetime.now():%Y%m%d_%H%M%S}.png"
            pg.screenshot(str(p))
            return f"Saved screenshot to {p}"
        if a in ("screen_find", "screen_click"):
            coords = _find_on_screen(description)
            if not coords:
                return f"Couldn't find '{description}' on screen."
            if a == "screen_click":
                pg.click(*coords)
                return f"Clicked '{description}' at {coords}."
            return f"'{description}' is at {coords}."
        return f"Unknown control action '{action}'."
    except Exception as e:
        return f"Control '{action}' failed: {e}"


def _find_on_screen(description: str):
    """Ask the vision model for the pixel coordinates of a described element."""
    from ai_helper import analyze_image
    from actions.vision import _capture_screen, _downscale
    try:
        import pyautogui
        w, h = pyautogui.size()
        raw = _downscale(_capture_screen(), (w, h))
        mime = "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "image/png"
        ans = analyze_image(
            raw, f"This screenshot is {w}x{h} pixels. Give ONLY the center x,y pixel "
                 f"coordinates of: {description}. Reply as 'x,y' or NOT_FOUND.", mime)
        m = __import__("re").search(r"(\d+)\s*,\s*(\d+)", ans)
        return (int(m.group(1)), int(m.group(2))) if m and "NOT_FOUND" not in ans.upper() else None
    except Exception:
        return None
