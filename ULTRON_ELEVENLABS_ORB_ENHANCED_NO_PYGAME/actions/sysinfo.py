"""System status and OS settings (volume, brightness, wifi, lock, power)."""
import platform
import shutil
import subprocess
import time

_OS = platform.system()  # Windows | Darwin | Linux
_HIDE = {"creationflags": subprocess.CREATE_NO_WINDOW} if _OS == "Windows" else {}


# ---------------------------------------------------------------- status
def system_status() -> str:
    try:
        import psutil
    except ImportError:
        return "psutil is needed for system status. Run: pip install psutil"
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    boot = time.time() - psutil.boot_time()
    up = f"{int(boot // 3600)}h {int((boot % 3600) // 60)}m"
    temp = None
    try:
        for _n, entries in (psutil.sensors_temperatures() or {}).items():
            if entries:
                temp = round(entries[0].current, 1)
                break
    except Exception:
        pass
    lines = [f"CPU: {cpu:.0f}%",
             f"RAM: {ram.percent:.0f}% ({ram.used/1024**3:.1f}/{ram.total/1024**3:.1f} GB)",
             f"Uptime: {up}", f"Processes: {len(psutil.pids())}"]
    if temp:
        lines.append(f"CPU temp: {temp}°C")
    return " | ".join(lines)


# ---------------------------------------------------------------- settings
def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10, **_HIDE)


def _pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = True
    return pyautogui


def _volume(direction):
    if _OS == "Windows":
        pg = _pyautogui()
        key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}[direction]
        for _ in range(1 if direction == "mute" else 5):
            pg.press(key)
    elif _OS == "Darwin":
        expr = {"up": "output volume of (get volume settings) + 10",
                "down": "output volume of (get volume settings) - 10"}.get(direction)
        if direction == "mute":
            _run(["osascript", "-e", "set volume with output muted"])
        else:
            _run(["osascript", "-e", f"set volume output volume ({expr})"])
    else:
        arg = {"up": "+10%", "down": "-10%", "mute": "toggle"}[direction]
        key = "set-sink-mute" if direction == "mute" else "set-sink-volume"
        _run(["pactl", key, "@DEFAULT_SINK@", arg])


def _volume_set(value):
    value = max(0, min(100, int(value)))
    if _OS == "Windows":
        try:
            import math
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            dev = AudioUtilities.GetSpeakers()
            vol = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                       POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevel(-65.25 if value == 0 else max(-65.25, 20 * math.log10(value / 100)), None)
        except Exception as e:
            return f"Could not set volume (install pycaw): {e}"
    elif _OS == "Darwin":
        _run(["osascript", "-e", f"set volume output volume {value}"])
    else:
        _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"])
    return f"Volume set to {value}%."


def _brightness(up):
    if _OS == "Darwin":
        _run(["osascript", "-e", f'tell application "System Events" to key code {144 if up else 145}'])
    elif _OS == "Linux":
        if shutil.which("brightnessctl"):
            _run(["brightnessctl", "set", "+10%" if up else "10%-"])
    else:
        op = "+ 10" if up else "- 10"
        bound = "Min(100," if up else "Max(0,"
        _run(["powershell", "-Command",
              "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
              f".WmiSetBrightness(1,[math]::{bound}"
              f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness {op}))"])


def _lock():
    if _OS == "Windows":
        _pyautogui().hotkey("win", "l")
    elif _OS == "Darwin":
        _run(["pmset", "displaysleepnow"])
    else:
        for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"]):
            if shutil.which(cmd[0]):
                _run(cmd)
                break


def _power(kind):
    if _OS == "Windows":
        _run(["shutdown", "/r" if kind == "restart" else "/s", "/t", "15"])
    elif _OS == "Darwin":
        verb = "restart" if kind == "restart" else "shut down"
        _run(["osascript", "-e", f'tell application "System Events" to {verb}'])
    else:
        _run(["systemctl", "reboot" if kind == "restart" else "poweroff"])
    return f"{kind.title()} in 15 seconds. Cancel from your terminal if this was a mistake."


def _wifi():
    if _OS == "Darwin":
        r = _run(["networksetup", "-getairportpower", "en0"])
        state = "off" if "On" in r.stdout else "on"
        _run(["networksetup", "-setairportpower", "en0", state])
    elif _OS == "Windows":
        _run(["powershell", "-Command",
              "$a=Get-NetAdapter|?{$_.PhysicalMediaType -eq 'Native 802.11'};"
              "if($a.Status -eq 'Up'){Disable-NetAdapter -Name $a.Name -Confirm:$false}"
              "else{Enable-NetAdapter -Name $a.Name -Confirm:$false}"])
    else:
        r = _run(["nmcli", "radio", "wifi"])
        _run(["nmcli", "radio", "wifi", "off" if "enabled" in r.stdout else "on"])


def computer_setting(action: str, value: str = "") -> str:
    """action: volume_up|volume_down|mute|volume_set|brightness_up|brightness_down|
    lock|wifi_toggle|shutdown|restart. shutdown/restart are gated by the caller."""
    a = (action or "").lower().strip()
    try:
        if a in ("volume_up", "volume_down", "mute"):
            _volume(a.replace("volume_", "") if a != "mute" else "mute")
            return f"Done: {a}."
        if a == "volume_set":
            return _volume_set(value or 50)
        if a in ("brightness_up", "brightness_down"):
            _brightness(a == "brightness_up")
            return f"Done: {a}."
        if a in ("lock", "lock_screen"):
            _lock()
            return "Screen locked."
        if a in ("wifi_toggle", "toggle_wifi"):
            _wifi()
            return "Toggled Wi-Fi."
        if a in ("shutdown", "restart"):
            return _power(a)
        return f"Unknown setting '{action}'. Try volume_up, mute, brightness_up, lock, wifi_toggle, shutdown."
    except Exception as e:
        return f"Setting '{action}' failed: {e}"
