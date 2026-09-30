"""OS-native scheduled reminders (Task Scheduler / launchd / systemd / at)."""
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_OS = platform.system()
_HIDE = {"creationflags": subprocess.CREATE_NO_WINDOW} if _OS == "Windows" else {}
_DIR = Path.home() / ".ultron" / "reminders"


def _script(task_name: str, message: str) -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    msg = json.dumps(message)
    if _OS == "Windows":
        body = (f"message={msg}\n"
                "try:\n"
                " from plyer import notification; notification.notify(title='ULTRON Reminder',message=message,timeout=20)\n"
                "except Exception:\n"
                " import ctypes; ctypes.windll.user32.MessageBoxW(0,message,'ULTRON Reminder',0x40)\n")
    elif _OS == "Darwin":
        body = (f"message={msg}\n"
                "import subprocess\n"
                "subprocess.run(['osascript','-e',f'display notification \"{message}\" with title \"ULTRON Reminder\"'])\n")
    else:
        body = (f"message={msg}\n"
                "import subprocess\n"
                "subprocess.run(['notify-send','ULTRON Reminder',message])\n")
    p = _DIR / f"{task_name}.py"
    p.write_text(body + "import pathlib\ntry:\n pathlib.Path(__file__).unlink()\nexcept Exception:\n pass\n",
                 encoding="utf-8")
    return p


def set_reminder(date: str, time_str: str, message: str = "Reminder") -> str:
    if not date or not time_str:
        return "I need a date (YYYY-MM-DD) and time (HH:MM)."
    try:
        when = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Use date as YYYY-MM-DD and time as HH:MM (24h)."
    if when <= datetime.now():
        return "That time is in the past."
    task = f"ULTRON_{when:%Y%m%d_%H%M%S}"
    script = _script(task, message[:200])
    py = sys.executable
    try:
        if _OS == "Windows":
            pyw = Path(py).with_name("pythonw.exe")
            py = str(pyw if pyw.exists() else py)
            r = subprocess.run(["schtasks", "/Create", "/TN", task, "/SC", "ONCE",
                                "/ST", when.strftime("%H:%M"), "/SD", when.strftime("%Y/%m/%d"),
                                "/TR", f'"{py}" "{script}"', "/F"],
                               capture_output=True, text=True, **_HIDE)
            ok = r.returncode == 0
        elif _OS == "Darwin":
            agents = Path.home() / "Library" / "LaunchAgents"
            agents.mkdir(parents=True, exist_ok=True)
            label = f"com.ultron.reminder.{task}"
            plist = agents / f"{label}.plist"
            plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array><string>{py}</string><string>{script}</string></array>
<key>StartCalendarInterval</key><dict><key>Year</key><integer>{when.year}</integer>
<key>Month</key><integer>{when.month}</integer><key>Day</key><integer>{when.day}</integer>
<key>Hour</key><integer>{when.hour}</integer><key>Minute</key><integer>{when.minute}</integer></dict>
</dict></plist>""", encoding="utf-8")
            ok = subprocess.run(["launchctl", "load", str(plist)], capture_output=True).returncode == 0
        else:
            if shutil.which("at"):
                ok = subprocess.run(["at", when.strftime("%H:%M %Y-%m-%d")],
                                    input=f"{py} {script}\n", text=True, capture_output=True).returncode == 0
            elif shutil.which("systemd-run"):
                ok = subprocess.run(["systemd-run", "--user",
                                     f"--on-calendar={when:%Y-%m-%d %H:%M:00}", f"--unit={task}",
                                     "--", py, str(script)], capture_output=True).returncode == 0
            else:
                return "No scheduler found (need 'at' or systemd on Linux)."
    except Exception as e:
        script.unlink(missing_ok=True)
        return f"Couldn't schedule the reminder: {e}"
    if not ok:
        script.unlink(missing_ok=True)
        return "The system scheduler rejected the reminder."
    return f"Reminder set for {when:%B %d at %I:%M %p}."
