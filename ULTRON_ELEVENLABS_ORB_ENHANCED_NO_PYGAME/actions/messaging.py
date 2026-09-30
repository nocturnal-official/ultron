"""Send a message through a desktop chat app by driving its UI (WhatsApp, Telegram, etc.).

This types into whatever app is opened, so the caller confirms first. For WhatsApp/Discord
the API-based tools in tools.py are more reliable; this covers Telegram/Signal/Messenger.
"""
import platform
import subprocess
import time
import webbrowser

_OS = platform.system()


def _pg():
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.06
    return pyautogui


def _paste(pg, text):
    try:
        import pyperclip
        pyperclip.copy(text)
        time.sleep(0.15)
        pg.hotkey("command" if _OS == "Darwin" else "ctrl", "v")
    except Exception:
        pg.typewrite(text, interval=0.02)


def _open_app(pg, app):
    if _OS == "Windows":
        pg.press("win"); time.sleep(0.6); _paste(pg, app); time.sleep(0.7); pg.press("enter")
    elif _OS == "Darwin":
        subprocess.run(["open", "-a", app], capture_output=True)
    else:
        try:
            subprocess.Popen([app.lower()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return False
    time.sleep(3.0)
    return True


def send_message(receiver: str, message_text: str, platform_name: str = "whatsapp") -> str:
    if not receiver or not message_text:
        return "Need both a recipient and a message."
    try:
        pg = _pg()
    except ImportError:
        return "pyautogui isn't installed. Run: pip install pyautogui"

    plat = platform_name.lower().strip()
    app = {"whatsapp": "WhatsApp", "telegram": "Telegram", "signal": "Signal",
           "discord": "Discord"}.get(plat)
    try:
        if plat in ("instagram", "messenger"):
            url = ("https://www.instagram.com/direct/new/" if plat == "instagram"
                   else "https://www.messenger.com/")
            webbrowser.open(url)
            time.sleep(4)
        elif app:
            if not _open_app(pg, app):
                return f"Couldn't open {app}."
        else:
            return f"Unsupported platform '{platform_name}'."
        # search for the contact, open the chat, type and send
        pg.hotkey("command" if _OS == "Darwin" else "ctrl", "f")
        time.sleep(0.5)
        _paste(pg, receiver)
        time.sleep(1.0)
        pg.press("enter")
        time.sleep(0.8)
        _paste(pg, message_text)
        time.sleep(0.2)
        pg.press("enter")
    except Exception as e:
        return f"Couldn't send via {platform_name}: {e}"
    return (f"Attempted to send to {receiver} via {platform_name}. "
            "Check the app — if the window wasn't focused it may be unsent.")
