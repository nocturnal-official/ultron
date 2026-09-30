"""Ultron's toolset: web, email, apps, WhatsApp, Discord and Android phone control.

Every tool returns a JSON string: {"ok": true, "result": ...} or {"ok": false, "error": ...}
so the AI always gets a clear, honest outcome.
"""
import email
import imaplib
import json
import os
import platform
import re
import shutil
import smtplib
import ssl
import subprocess
import time
import urllib.parse
import webbrowser
from datetime import datetime
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import requests

from config import BASE_DIR, CFG

OS = platform.system()  # "Windows", "Darwin" (macOS) or "Linux"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SCREENSHOT_DIR = BASE_DIR / "screenshots"


def _ok(result, **extra) -> str:
    return json.dumps({"ok": True, "result": result, **extra}, ensure_ascii=False, default=str)


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


# ============================================================ contacts
def load_contacts() -> dict:
    path = BASE_DIR / "contacts.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k.strip().lower(): v for k, v in data.items()
            if isinstance(v, dict) and not k.startswith("_")}


def find_contact(name: str):
    contacts = load_contacts()
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in contacts:
        return contacts[key]
    partial = [v for k, v in contacts.items() if key in k or k in key]
    return partial[0] if len(partial) == 1 else None


def list_contacts() -> str:
    c = load_contacts()
    if not c:
        return _ok("No contacts saved. Add people to contacts.json.")
    return _ok({name: sorted(info.keys()) for name, info in c.items()})


# ============================================================ web
def web_search(query: str, max_results: int = 5) -> str:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return _err("Search library missing. Run: pip install ddgs")
    try:
        raw = list(DDGS().text(query, max_results=max(1, min(int(max_results), 10))))
    except Exception as e:
        return _err(f"Search failed: {e}")
    results = [{"title": r.get("title", ""),
                "url": r.get("href") or r.get("url", ""),
                "snippet": r.get("body", "")} for r in raw]
    return _ok(results) if results else _err("No results found.")


def fetch_webpage(url: str, max_chars: int = 8000) -> str:
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return _err(f"Could not fetch page: {e}")
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = soup.get_text("\n")
    except ImportError:
        title, text = "", re.sub(r"<[^>]+>", " ", r.text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return _ok(text[:int(max_chars)], title=title, url=r.url, truncated=len(text) > int(max_chars))


def open_website(url: str) -> str:
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    webbrowser.open(url)
    return _ok(f"Opened {url} in the browser.")


# ============================================================ desktop apps
# name -> per-OS launch target. Targets ending in ":" / containing "://" are URI schemes.
APP_ALIASES = {
    "whatsapp": {"Windows": "whatsapp:", "Darwin": "WhatsApp", "Linux": "https://web.whatsapp.com"},
    "discord": {"Windows": "discord://", "Darwin": "Discord", "Linux": "discord"},
    "spotify": {"Windows": "spotify:", "Darwin": "Spotify", "Linux": "spotify"},
    "telegram": {"Windows": "tg://", "Darwin": "Telegram", "Linux": "telegram-desktop"},
    "chrome": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "google chrome": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "edge": {"Windows": "msedge", "Darwin": "Microsoft Edge", "Linux": "microsoft-edge"},
    "firefox": {"Windows": "firefox", "Darwin": "Firefox", "Linux": "firefox"},
    "notepad": {"Windows": "notepad", "Darwin": "TextEdit", "Linux": "gedit"},
    "calculator": {"Windows": "calc", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    "calc": {"Windows": "calc", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    "file explorer": {"Windows": "explorer", "Darwin": "Finder", "Linux": "nautilus"},
    "explorer": {"Windows": "explorer", "Darwin": "Finder", "Linux": "nautilus"},
    "files": {"Windows": "explorer", "Darwin": "Finder", "Linux": "nautilus"},
    "settings": {"Windows": "ms-settings:", "Darwin": "System Settings", "Linux": "gnome-control-center"},
    "terminal": {"Windows": "wt", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "cmd": {"Windows": "cmd", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "vs code": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "vscode": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "word": {"Windows": "winword", "Darwin": "Microsoft Word", "Linux": "libreoffice --writer"},
    "excel": {"Windows": "excel", "Darwin": "Microsoft Excel", "Linux": "libreoffice --calc"},
    "powerpoint": {"Windows": "powerpnt", "Darwin": "Microsoft PowerPoint", "Linux": "libreoffice --impress"},
    "outlook": {"Windows": "outlook", "Darwin": "Microsoft Outlook", "Linux": "thunderbird"},
    "paint": {"Windows": "mspaint", "Darwin": "Preview", "Linux": "gimp"},
    "camera": {"Windows": "microsoft.windows.camera:", "Darwin": "Photo Booth", "Linux": "cheese"},
    "mail": {"Windows": "outlookmail:", "Darwin": "Mail", "Linux": "thunderbird"},
    "store": {"Windows": "ms-windows-store:", "Darwin": "App Store", "Linux": "gnome-software"},
}

WEB_FALLBACKS = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "instagram": "https://www.instagram.com", "linkedin": "https://www.linkedin.com",
    "twitter": "https://x.com", "x": "https://x.com", "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai", "netflix": "https://www.netflix.com",
    "google": "https://www.google.com", "maps": "https://maps.google.com",
}


def _is_uri(target: str) -> bool:
    return target.endswith(":") or "://" in target


def _open_uri(uri: str):
    if OS == "Windows":
        os.startfile(uri)  # noqa  (Windows only)
    elif OS == "Darwin":
        subprocess.Popen(["open", uri])
    else:
        subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _win_start_apps():
    """Every app in the Windows Start menu, including Microsoft Store apps."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=25)
        data = json.loads(r.stdout or "[]")
        return [data] if isinstance(data, dict) else data
    except Exception:
        return []


def _best_match(query: str, names):
    q = query.lower()
    exact = [n for n in names if n.lower() == q]
    if exact:
        return exact[0]
    starts = [n for n in names if n.lower().startswith(q)]
    contains = [n for n in names if q in n.lower()]
    pool = starts or contains
    return min(pool, key=len) if pool else None


def _launch_windows(target: str, original: str) -> bool:
    if _is_uri(target):
        try:
            os.startfile(target)  # noqa
            return True
        except OSError:
            pass
    exe = shutil.which(target)
    if exe:
        subprocess.Popen([exe])
        return True
    # Start-menu apps (covers Store apps like WhatsApp and normal installs)
    apps = _win_start_apps()
    for query in dict.fromkeys([original, target]):
        name = _best_match(query, [a.get("Name", "") for a in apps if a.get("Name")])
        if name:
            appid = next(a["AppID"] for a in apps if a.get("Name") == name)
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{appid}"])
            return True
    # Start menu shortcuts
    roots = [Path(os.environ.get("ProgramData", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
             Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs"]
    shortcuts = {}
    for root in roots:
        if root.exists():
            for p in root.rglob("*.lnk"):
                shortcuts[p.stem] = p
    name = _best_match(original, shortcuts.keys())
    if name:
        os.startfile(str(shortcuts[name]))  # noqa
        return True
    # Registered "App Paths" (e.g. winword, excel, chrome)
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{target}.exe")
                path, _ = winreg.QueryValueEx(key, "")
                subprocess.Popen([path])
                return True
            except OSError:
                continue
    except ImportError:
        pass
    return False


def _launch_mac(target: str, original: str) -> bool:
    if _is_uri(target):
        return subprocess.run(["open", target]).returncode == 0
    for name in dict.fromkeys([target, original, original.title()]):
        if subprocess.run(["open", "-a", name], capture_output=True).returncode == 0:
            return True
    return False


def _launch_linux(target: str, original: str) -> bool:
    if _is_uri(target):
        _open_uri(target)
        return True
    parts = target.split()
    if shutil.which(parts[0]):
        subprocess.Popen(parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    desktop_dirs = [Path("/usr/share/applications"), Path.home() / ".local/share/applications",
                    Path("/var/lib/flatpak/exports/share/applications")]
    files = {p.stem: p for d in desktop_dirs if d.exists() for p in d.glob("*.desktop")}
    name = _best_match(original.replace(" ", "-"), files.keys()) or _best_match(original, files.keys())
    if name and shutil.which("gtk-launch"):
        subprocess.Popen(["gtk-launch", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False


def open_app(app_name: str) -> str:
    name = app_name.strip()
    key = name.lower()
    alias = APP_ALIASES.get(key) or next((v for k, v in APP_ALIASES.items() if k in key.split()), None)
    targets = [alias[OS]] if alias and OS in alias else []
    targets.append(name)
    launcher = {"Windows": _launch_windows, "Darwin": _launch_mac}.get(OS, _launch_linux)
    for t in dict.fromkeys(targets):
        try:
            if launcher(t, name):
                return _ok(f"Opened {name}.")
        except Exception:
            continue
    if key in WEB_FALLBACKS:
        webbrowser.open(WEB_FALLBACKS[key])
        return _ok(f"{name} isn't installed as an app, so I opened {WEB_FALLBACKS[key]} in the browser.")
    return _err(f"Couldn't find an app called '{name}' on this computer.")


def close_app(app_name: str) -> str:
    name = app_name.strip()
    if OS == "Windows":
        proc = name if name.lower().endswith(".exe") else name + ".exe"
        r = subprocess.run(["taskkill", "/IM", proc, "/F"], capture_output=True, text=True)
    elif OS == "Darwin":
        r = subprocess.run(["osascript", "-e", f'quit app "{name}"'], capture_output=True, text=True)
    else:
        r = subprocess.run(["pkill", "-f", name], capture_output=True, text=True)
    if r.returncode == 0:
        return _ok(f"Closed {name}.")
    return _err(f"Couldn't close {name}: {(r.stderr or r.stdout).strip() or 'not running'}")


# ============================================================ WhatsApp
def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        return digits[1:]
    if digits.startswith("00"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        return CFG.default_country_code + digits
    return digits


def _resolve_phone(recipient: str):
    if re.fullmatch(r"[\d\s+\-()]{7,}", recipient.strip()):
        return recipient
    contact = find_contact(recipient)
    return (contact or {}).get("phone") or (contact or {}).get("whatsapp")


def send_whatsapp_message(recipient: str, message: str) -> str:
    phone = _resolve_phone(recipient)
    if not phone:
        return _err(f"I don't have a phone number for '{recipient}'. Add them to contacts.json "
                    "or give me the number.")
    num = _normalize_phone(phone)
    try:
        import pyautogui
    except Exception as e:
        return _err(f"pyautogui is needed to press Send ({e}). Run: pip install pyautogui")
    text = urllib.parse.quote(message)
    use_desktop = CFG.whatsapp_mode == "desktop" and OS in ("Windows", "Darwin")
    try:
        if use_desktop:
            _open_uri(f"whatsapp://send?phone={num}&text={text}")
            time.sleep(CFG.whatsapp_wait)
        else:
            webbrowser.open(f"https://web.whatsapp.com/send?phone={num}&text={text}")
            time.sleep(CFG.whatsapp_web_wait)
        pyautogui.press("enter")
    except Exception as e:
        return _err(f"WhatsApp send failed: {e}")
    how = "WhatsApp Desktop" if use_desktop else "WhatsApp Web"
    return _ok(f"Opened the chat with +{num} in {how} with the message and pressed Send. "
               "If the window wasn't focused, the message may be sitting unsent in the box.")


# ============================================================ Discord
DISCORD_API = "https://discord.com/api/v10"


def _chunks(text: str, size: int = 1900):
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def send_discord_message(recipient: str, message: str, recipient_is_user: bool = False) -> str:
    target = recipient.strip()
    webhook = None
    channel_id = user_id = None

    if "discord.com/api/webhooks/" in target or "discordapp.com/api/webhooks/" in target:
        webhook = target
    elif target.isdigit():
        if recipient_is_user:
            user_id = target
        else:
            channel_id = target
    else:
        contact = find_contact(target)
        if not contact:
            return _err(f"'{recipient}' isn't in contacts.json. Add a discord_user_id, "
                        "discord_channel_id or discord_webhook for them.")
        webhook = contact.get("discord_webhook")
        channel_id = contact.get("discord_channel_id")
        user_id = contact.get("discord_user_id")

    try:
        if webhook:
            for part in _chunks(message):
                r = requests.post(webhook, json={"content": part}, timeout=15)
                if r.status_code >= 300:
                    return _err(f"Discord webhook error {r.status_code}: {r.text[:300]}")
            return _ok(f"Posted to Discord via webhook ({recipient}).")

        if not CFG.discord_bot_token:
            return _err("DISCORD_BOT_TOKEN isn't set in .env.")
        headers = {"Authorization": f"Bot {CFG.discord_bot_token}", "Content-Type": "application/json"}

        if not channel_id and user_id:
            r = requests.post(f"{DISCORD_API}/users/@me/channels", headers=headers,
                              json={"recipient_id": str(user_id)}, timeout=15)
            if r.status_code >= 300:
                return _err(f"Couldn't open a DM (the user must share a server with the bot): "
                            f"{r.status_code} {r.text[:300]}")
            channel_id = r.json()["id"]
        if not channel_id:
            return _err(f"No Discord ID saved for '{recipient}'.")

        for part in _chunks(message):
            r = requests.post(f"{DISCORD_API}/channels/{channel_id}/messages", headers=headers,
                              json={"content": part}, timeout=15)
            if r.status_code >= 300:
                return _err(f"Discord error {r.status_code}: {r.text[:300]}")
        return _ok(f"Sent Discord message to {recipient}.")
    except requests.RequestException as e:
        return _err(f"Network error talking to Discord: {e}")


# ============================================================ email
def _resolve_emails(value) -> list:
    if not value:
        return []
    items = value if isinstance(value, list) else re.split(r"[,;]", str(value))
    out = []
    for item in (i.strip() for i in items):
        if not item:
            continue
        if "@" in item:
            out.append(item)
        else:
            contact = find_contact(item)
            if contact and contact.get("email"):
                out.append(contact["email"])
            else:
                raise ValueError(f"No email address saved for '{item}'.")
    return out


def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    if not (CFG.email_address and CFG.email_password):
        return _err("EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set in .env.")
    try:
        to_list, cc_list, bcc_list = _resolve_emails(to), _resolve_emails(cc), _resolve_emails(bcc)
    except ValueError as e:
        return _err(str(e))
    if not to_list:
        return _err("No recipient given.")

    msg = EmailMessage()
    msg["From"] = formataddr((CFG.email_display_name, CFG.email_address)) if CFG.email_display_name \
        else CFG.email_address
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        if CFG.smtp_port == 465:
            with smtplib.SMTP_SSL(CFG.smtp_host, CFG.smtp_port, context=ctx, timeout=30) as s:
                s.login(CFG.email_address, CFG.email_password)
                s.send_message(msg, to_addrs=to_list + cc_list + bcc_list)
        else:
            with smtplib.SMTP(CFG.smtp_host, CFG.smtp_port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(CFG.email_address, CFG.email_password)
                s.send_message(msg, to_addrs=to_list + cc_list + bcc_list)
    except smtplib.SMTPAuthenticationError:
        return _err("Email login failed. For Gmail you need an App Password, not your normal password.")
    except Exception as e:
        return _err(f"Sending failed: {e}")
    return _ok(f"Email sent to {', '.join(to_list)}.")


def _decode(value) -> str:
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


def _plain_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")


def read_recent_emails(count: int = 5, unread_only: bool = False, search: str = "") -> str:
    if not (CFG.email_address and CFG.email_password):
        return _err("EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set in .env.")
    count = max(1, min(int(count), 20))
    try:
        box = imaplib.IMAP4_SSL(CFG.imap_host)
        box.login(CFG.email_address, CFG.email_password)
        box.select("INBOX", readonly=True)
        criteria = ["UNSEEN"] if unread_only else ["ALL"]
        if search:
            safe = search.replace('"', "")
            criteria = criteria + ["TEXT", f'"{safe}"']
        status, data = box.search(None, *criteria)
        ids = data[0].split()[-count:] if status == "OK" and data and data[0] else []
        emails = []
        for mid in reversed(ids):
            _, parts = box.fetch(mid, "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if not raw:
                continue
            m = email.message_from_bytes(raw)
            body = re.sub(r"\s+", " ", _plain_body(m)).strip()
            emails.append({"from": _decode(m.get("From")), "subject": _decode(m.get("Subject")),
                           "date": m.get("Date", ""), "preview": body[:600]})
        box.logout()
    except imaplib.IMAP4.error as e:
        return _err(f"Inbox login failed ({e}). Gmail needs IMAP on and an App Password.")
    except Exception as e:
        return _err(f"Couldn't read inbox: {e}")
    return _ok(emails if emails else "No matching emails.")


# ============================================================ Android phone (ADB)
PHONE_APPS = {
    "whatsapp": "com.whatsapp", "whatsapp business": "com.whatsapp.w4b",
    "instagram": "com.instagram.android", "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome", "gmail": "com.google.android.gm", "discord": "com.discord",
    "spotify": "com.spotify.music", "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps", "telegram": "org.telegram.messenger",
    "settings": "com.android.settings", "play store": "com.android.vending",
    "facebook": "com.facebook.katana", "snapchat": "com.snapchat.android",
    "linkedin": "com.linkedin.android", "x": "com.twitter.android", "twitter": "com.twitter.android",
    "netflix": "com.netflix.mediaclient", "photos": "com.google.android.apps.photos",
    "phonepe": "com.phonepe.app", "paytm": "net.one97.paytm", "gpay": "com.google.android.apps.nbu.paisa.user",
}


def _adb(*args, timeout=20, binary=False):
    adb = CFG.adb_path
    if not (shutil.which(adb) or Path(adb).exists()):
        raise RuntimeError("adb not found. Install Android platform-tools and set ADB_PATH in .env.")
    cmd = [adb] + (["-s", CFG.phone_serial] if CFG.phone_serial else []) + list(args)
    return subprocess.run(cmd, capture_output=True, text=not binary, timeout=timeout)


def _device_problem():
    """Returns an error message if no usable phone is connected, else None."""
    r = _adb("devices")
    lines = [l.split() for l in r.stdout.splitlines()[1:] if l.strip()]
    if CFG.phone_serial:
        lines = [l for l in lines if l[0] == CFG.phone_serial]
    if not lines:
        return "No phone connected. Plug it in by USB with USB debugging turned on."
    states = {l[1] for l in lines if len(l) > 1}
    if "device" in states:
        return None
    if "unauthorized" in states:
        return "Phone is connected but hasn't allowed this computer. Unlock it and tap 'Allow USB debugging'."
    return f"Phone state is {', '.join(states)}; reconnect the cable."


def _screen_state():
    power = _adb("shell", "dumpsys", "power").stdout
    awake = "mWakefulness=Awake" in power or "Display Power: state=ON" in power
    win = _adb("shell", "dumpsys", "window").stdout
    locked = None
    for pattern in ("mDreamingLockscreen=", "mShowingLockscreen=", "isStatusBarKeyguard="):
        m = re.search(pattern + r"(true|false)", win)
        if m:
            locked = (locked or False) or m.group(1) == "true"
    if locked is None:
        trust = _adb("shell", "dumpsys", "trust").stdout
        m = re.search(r"deviceLocked=(\d)", trust)
        if m:
            locked = m.group(1) == "1"
    return awake, locked


def phone_status() -> str:
    try:
        problem = _device_problem()
        if problem:
            return _err(problem)
        model = _adb("shell", "getprop", "ro.product.model").stdout.strip()
        battery = re.search(r"level: (\d+)", _adb("shell", "dumpsys", "battery").stdout)
        awake, locked = _screen_state()
    except Exception as e:
        return _err(str(e))
    return _ok({"model": model, "battery_percent": int(battery.group(1)) if battery else None,
                "screen_on": awake,
                "locked": "unknown" if locked is None else locked})


def phone_unlock() -> str:
    if not CFG.phone_pin:
        return _err("PHONE_PIN isn't set in .env, so I can't unlock the phone.")
    try:
        problem = _device_problem()
        if problem:
            return _err(problem)
        _adb("shell", "input", "keyevent", "224")  # wake
        time.sleep(0.6)
        size = _adb("shell", "wm", "size").stdout
        dims = re.findall(r"(\d+)x(\d+)", size)
        w, h = (int(dims[-1][0]), int(dims[-1][1])) if dims else (1080, 2340)
        _adb("shell", "input", "swipe", str(w // 2), str(int(h * 0.85)), str(w // 2), str(int(h * 0.3)), "300")
        time.sleep(0.8)
        _adb("shell", "input", "text", CFG.phone_pin)
        time.sleep(0.3)
        _adb("shell", "input", "keyevent", "66")  # enter
        time.sleep(1.5)
        _, locked = _screen_state()
    except Exception as e:
        return _err(str(e))
    if locked:
        return _err("Entered the PIN but the phone still looks locked. Check PHONE_PIN "
                    "(pattern locks aren't supported, only PIN/password).")
    return _ok("Phone unlocked." if locked is False else "PIN entered; phone should be unlocked.")


def phone_lock() -> str:
    try:
        problem = _device_problem()
        if problem:
            return _err(problem)
        awake, _ = _screen_state()
        if awake:
            _adb("shell", "input", "keyevent", "26")
    except Exception as e:
        return _err(str(e))
    return _ok("Phone screen locked.")


def phone_open_app(app_name: str) -> str:
    try:
        problem = _device_problem()
        if problem:
            return _err(problem)
        key = app_name.strip().lower()
        package = app_name.strip() if re.fullmatch(r"[\w]+(\.[\w]+)+", app_name.strip()) else PHONE_APPS.get(key)
        if not package:
            pkgs = [l.replace("package:", "").strip()
                    for l in _adb("shell", "pm", "list", "packages").stdout.splitlines()]
            squashed = key.replace(" ", "")
            hits = [p for p in pkgs if squashed in p.lower().replace("_", "")]
            if not hits:
                return _err(f"No app matching '{app_name}' on the phone.")
            package = min(hits, key=len)
        awake, locked = _screen_state()
        if not awake or locked:
            unlock = json.loads(phone_unlock())
            if not unlock["ok"]:
                return _err("Phone is locked and unlocking failed: " + unlock["error"])
        r = _adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        if "No activities found" in r.stdout + r.stderr or r.returncode != 0:
            return _err(f"Couldn't launch {package} on the phone.")
    except Exception as e:
        return _err(str(e))
    return _ok(f"Opened {app_name} on the phone ({package}).")


def phone_screenshot() -> str:
    try:
        problem = _device_problem()
        if problem:
            return _err(problem)
        r = _adb("exec-out", "screencap", "-p", binary=True, timeout=30)
        if r.returncode != 0 or not r.stdout.startswith(b"\x89PNG"):
            return _err("Screenshot failed.")
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        path = SCREENSHOT_DIR / f"phone_{datetime.now():%Y%m%d_%H%M%S}.png"
        path.write_bytes(r.stdout)
    except Exception as e:
        return _err(str(e))
    return _ok(f"Saved phone screenshot to {path}")


# ============================================================ misc
def get_datetime() -> str:
    return _ok(datetime.now().strftime("%A, %d %B %Y, %I:%M %p"))


# ============================================================ registry
def _schema(props: dict, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


S = {"type": "string"}
TOOL_SPECS = [
    ("fetch_webpage", "Download a web page and return its readable text. Use after web_search to read a result.",
     _schema({"url": S}, ["url"]), fetch_webpage),
    ("open_website", "Open a URL in the user's browser so they can see it.",
     _schema({"url": S}, ["url"]), open_website),
    ("open_app", "Open an application on this computer, e.g. WhatsApp, Discord, Chrome, Spotify, Notepad.",
     _schema({"app_name": S}, ["app_name"]), open_app),
    ("close_app", "Close an application on this computer.",
     _schema({"app_name": {"type": "string", "description": "Process/app name, e.g. chrome, WhatsApp"}},
             ["app_name"]), close_app),
    ("list_contacts", "List saved contacts and which details (phone, email, discord) each has.",
     _schema({}), list_contacts),
    ("send_whatsapp_message", "Send a WhatsApp message. recipient is a contact name from contacts.json "
     "or a phone number.", _schema({"recipient": S, "message": S}, ["recipient", "message"]),
     send_whatsapp_message),
    ("send_discord_message", "Send a Discord message via the user's bot/webhook. recipient is a contact name, "
     "a channel ID, a user ID (set recipient_is_user=true) or a webhook URL.",
     _schema({"recipient": S, "message": S, "recipient_is_user": {"type": "boolean"}},
             ["recipient", "message"]), send_discord_message),
    ("send_email", "Send an email from the user's account. to/cc/bcc accept addresses or contact names, "
     "comma-separated. Write a complete, well-formatted body.",
     _schema({"to": S, "subject": S, "body": S, "cc": S, "bcc": S}, ["to", "subject", "body"]), send_email),
    ("read_recent_emails", "Read recent emails from the user's inbox (without marking them read).",
     _schema({"count": {"type": "integer"}, "unread_only": {"type": "boolean"}, "search": S}),
     read_recent_emails),
    ("phone_status", "Check the USB-connected Android phone: model, battery, screen on, locked.",
     _schema({}), phone_status),
    ("phone_unlock", "Wake and unlock the connected Android phone using the PIN saved in the user's config.",
     _schema({}), phone_unlock),
    ("phone_lock", "Turn off / lock the connected phone's screen.", _schema({}), phone_lock),
    ("phone_open_app", "Open an app on the connected phone (unlocks first if needed). Name or package id.",
     _schema({"app_name": S}, ["app_name"]), phone_open_app),
    ("phone_screenshot", "Take a screenshot of the connected phone and save it on the computer.",
     _schema({}), phone_screenshot),
    ("get_datetime", "Get the current local date and time.", _schema({}), get_datetime),
]


# ============================================================ ported "actions" tools
# These modules return plain human-readable strings; _plain wraps them as JSON results.
def _plain(fn):
    def wrapper(**kwargs):
        return _ok(fn(**kwargs))
    return wrapper


def _register_actions():
    """Import the actions package and add its tools. Missing optional deps degrade gracefully."""
    from actions import (sysinfo, files, web, vision, control, reminders,
                         browser, fileproc, dev, messaging, games, memory)
    B = {"type": "boolean"}
    I = {"type": "integer"}
    specs = [
        ("system_status", "Report CPU, RAM, uptime, process count and temperature.",
         _schema({}), sysinfo.system_status),
        ("computer_setting", "Change an OS setting: volume_up/volume_down/mute/volume_set, "
         "brightness_up/brightness_down, lock, wifi_toggle, shutdown, restart. Pass value for volume_set.",
         _schema({"action": S, "value": S}, ["action"]), sysinfo.computer_setting),
        ("file_op", "Manage files/folders in the user's home area: list, read, create_file, create_folder, "
         "write, delete (to Recycle Bin), move, copy, rename, find, disk_usage.",
         _schema({"action": S, "path": S, "name": S, "destination": S, "new_name": S,
                  "content": S, "extension": S}, ["action"]), files.file_op),
        ("organize_folder", "Sort loose files in a folder (default desktop) into type subfolders.",
         _schema({"path": S}), files.organize_folder),
        ("web_search", "Search the web. mode: search | news | research | price | compare. "
         "For compare, pass items (list) and aspect.",
         _schema({"query": S, "mode": S, "items": {"type": "array", "items": S}, "aspect": S}), web.web_search),
        ("weather", "Live weather for a city (defaults to DEFAULT_CITY).",
         _schema({"city": S, "when": S}), web.weather),
        ("youtube", "YouTube: action 'play' (query) opens the first video; 'summarize' (url) summarizes it.",
         _schema({"action": S, "query": S, "url": S}), web.youtube),
        ("look", "Capture the screen or webcam and describe/answer a question about it. angle: screen | camera.",
         _schema({"angle": S, "question": S}), vision.look),
        ("computer_control", "Direct desktop control: type, click, double_click, right_click, hotkey, press, "
         "scroll, move, screenshot, screen_find, screen_click. Use screen_click with a description to click "
         "something by sight.",
         _schema({"action": S, "text": S, "x": I, "y": I, "keys": S, "key": S,
                  "direction": S, "amount": I, "description": S}, ["action"]), control.computer_control),
        ("set_reminder", "Schedule an OS notification. date=YYYY-MM-DD, time_str=HH:MM (24h), message.",
         _schema({"date": S, "time_str": S, "message": S}, ["date", "time_str"]), reminders.set_reminder),
        ("browser_control", "Drive a real browser: go_to (url), search (query, engine), click (description), "
         "type (description, text), read, press (key), screenshot, close.",
         _schema({"action": S, "url": S, "query": S, "engine": S, "description": S, "text": S, "key": S},
                 ["action"]), browser.browser_control),
        ("file_process", "Do something with a file: images (describe/ocr/resize/convert/compress), "
         "pdf/docx/text (summarize/extract_text/word_count), data (stats/info/convert/analyze), "
         "json (validate/format/analyze), code (explain/review), audio/video (transcribe/info/trim/"
         "extract_audio/convert), archive (list/extract), pptx (summarize). Pass an instruction for anything else.",
         _schema({"file_path": S, "action": S, "instruction": S, "format": S,
                  "width": I, "height": I, "quality": I, "start": S, "end": S}, ["file_path"]),
         fileproc.file_process),
        ("code_helper", "Write, edit, explain, optimize or run code. action: write|edit|explain|optimize|"
         "review|document|run. Give description (write/edit) or file_path (edit/explain/run).",
         _schema({"action": S, "description": S, "language": S, "output_path": S,
                  "file_path": S, "args": S, "timeout": I}), dev.code_helper),
        ("send_message_ui", "Send a chat message by driving a desktop app's UI (Telegram, Signal, Messenger, "
         "or WhatsApp/Discord as a fallback to the API tools). recipient, message_text, platform_name.",
         _schema({"receiver": S, "message_text": S, "platform_name": S}, ["receiver", "message_text"]),
         messaging.send_message),
        ("game_updater", "Manage Steam games: action update|install|list, optional game_name.",
         _schema({"action": S, "platform_name": S, "game_name": S}), games.game_updater),
        ("set_wallpaper", "Set the desktop wallpaper to an image file on the computer.",
         _schema({"image_path": S}, ["image_path"]), files.set_wallpaper),
        ("flights", "Open Google Flights pre-filled for a route.",
         _schema({"origin": S, "destination": S, "date": S, "return_date": S}, ["origin", "destination"]),
         web.flights),
        ("remember", "Save a durable fact about the user. category: identity|preferences|projects|people|notes.",
         _schema({"category": S, "key": S, "value": S}, ["category", "key", "value"]), memory.remember),
        ("recall", "Look up what's stored in memory, optionally filtered by a query.",
         _schema({"query": S}), memory.recall),
        ("forget", "Remove a stored fact by key, or set clear_all=true to wipe memory.",
         _schema({"key": S, "clear_all": B}), memory.forget),
    ]
    for name, desc, schema, fn in specs:
        TOOL_SPECS.append((name, desc, schema, _plain(fn)))


try:
    _register_actions()
except Exception as _e:  # never let an optional module break the core assistant
    print(f"[Ultron] Some extra tools failed to load: {_e}")

REGISTRY = {name: fn for name, _, _, fn in TOOL_SPECS}
# These act on the outside world, so Ultron asks before running them (CONFIRM_ACTIONS=true).
SENSITIVE = {"send_whatsapp_message", "send_discord_message", "send_email", "phone_unlock", "close_app",
             "computer_control", "set_reminder", "send_message_ui"}
# shutdown/restart are gated inside computer_setting via a dedicated confirm below.
_SETTING_CONFIRM = {"shutdown", "restart"}


def anthropic_tools():
    return [{"name": n, "description": d, "input_schema": s} for n, d, s, _ in TOOL_SPECS]


def openai_tools():
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": s}}
            for n, d, s, _ in TOOL_SPECS]


def execute_tool(name: str, args: dict, confirm=None) -> str:
    fn = REGISTRY.get(name)
    if not fn:
        return _err(f"Unknown tool '{name}'.")
    args = args or {}
    needs_confirm = name in SENSITIVE or (
        name == "computer_setting" and str(args.get("action", "")).lower() in _SETTING_CONFIRM
        or name == "file_op" and str(args.get("action", "")).lower() == "delete")
    if needs_confirm and CFG.confirm_actions and confirm is not None and not confirm(name, args):
        return _err("The user declined this action. Don't retry unless they ask.")
    try:
        return fn(**args)
    except TypeError as e:
        return _err(f"Bad arguments for {name}: {e}")
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")
