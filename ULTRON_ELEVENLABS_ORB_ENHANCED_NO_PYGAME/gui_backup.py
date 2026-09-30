"""ULTRON futuristic GUI.

A dark, holographic command console with a reactive energy orb in the center.
The orb is deliberately face-free: it represents ULTRON as a living energy
core and reacts to listening, thinking, and speaking states.

Voice input/output is handled by voice.py. The GUI communicates with it only
through callbacks so the audio work stays off Tkinter's main thread.
"""
from __future__ import annotations

import math
import os
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext

from config import CFG

# ---------------------------------------------------------------------------
# ULTRON palette
BG = "#02050A"
BG2 = "#030A11"
PANEL = "#061019"
PANEL_2 = "#091722"
BORDER = "#123746"
BORDER_2 = "#1B5267"
CYAN = "#66ECFF"
CYAN_2 = "#1AB5DE"
CYAN_D = "#0B5871"
RED = "#FF3448"
RED_2 = "#9E1B2A"
ORANGE = "#FF8A22"
ORANGE_2 = "#D65C18"
GREEN = "#39FF9A"
YELLOW = "#FFD166"
TEXT = "#E4F6FF"
TEXT_2 = "#8DB7C7"
MUTED = "#537184"
USER = "#A7F0FF"
DIM = "#173746"

FONT = ("Consolas", 10)
FONT_SM = ("Consolas", 8)
FONT_MED = ("Consolas", 10, "bold")
FONT_BIG = ("Consolas", 22, "bold")


class UltronHUD:
    """Procedural face-free holographic ULTRON orb.

    State controls the palette and motion, while voice_level controls how much
    the orb expands and how energetic the field becomes. The orb is intentionally
    abstract: concentric energy bands + filaments + particles rather than a face.
    """

    def __init__(self, parent: tk.Widget):
        self.canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.state = "IDLE"
        self.voice_level = 0.0
        self.target_level = 0.0
        self.phase = 0.0
        self.running = True
        self.last_t = time.perf_counter()

        rng = random.Random(24092026)
        self.particles = [
            {
                "a": rng.random() * math.tau,
                "r": rng.uniform(0.55, 1.62),
                "speed": rng.uniform(-0.9, 1.1),
                "size": rng.uniform(0.7, 2.4),
                "jitter": rng.random() * math.tau,
                "hot": rng.random(),
            }
            for _ in range(280)
        ]

        self.canvas.bind("<Configure>", lambda _e: self.canvas.after_idle(self._draw))
        self._animate()

    def set_state(self, state: str):
        self.state = str(state or "IDLE").upper()
        if self.state != "SPEAKING":
            self.target_level = 0.0

    def set_voice_level(self, level: float):
        try:
            self.target_level = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            self.target_level = 0.0

    def stop(self):
        self.running = False

    def _colors(self):
        if self.state == "SPEAKING":
            return ORANGE, RED, CYAN
        if self.state == "LISTENING":
            return CYAN, GREEN, ORANGE
        if self.state == "THINKING":
            return CYAN, ORANGE, RED
        return CYAN_2, ORANGE_2, RED_2

    def _animate(self):
        if not self.running:
            return

        now = time.perf_counter()
        dt = min(0.05, max(0.0, now - self.last_t))
        self.last_t = now
        self.phase += dt * (1.45 + self.voice_level * 0.7)

        # The orb only reacts to audio. Without speech it keeps a calm rotational pulse.
        base_energy = 0.018 + 0.012 * (0.5 + 0.5 * math.sin(self.phase * 2.2))
        if self.state in ("SPEAKING", "LISTENING"):
            desired = max(base_energy, self.target_level)
        else:
            desired = base_energy

        self.voice_level += (desired - self.voice_level) * min(1.0, dt * 9.0)
        self._draw()
        self.canvas.after(28, self._animate)  # ~36 FPS: smoother on Tk + lighter CPU

    @staticmethod
    def _hex(rgb: tuple[int, int, int]) -> str:
        return "#%02x%02x%02x" % rgb

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w = max(560, c.winfo_width())
        h = max(560, c.winfo_height())
        cx = w * 0.5
        cy = h * 0.49
        size = min(w, h)
        primary, accent, hot = self._colors()

        # ---------------------------------------------------------------- background
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")

        # Fine grid
        grid = 44
        for x in range(0, int(w) + grid, grid):
            c.create_line(x, 0, x, h, fill="#06131C")
        for y in range(0, int(h) + grid, grid):
            c.create_line(0, y, w, y, fill="#06131C")

        # Very faint radial crosshair
        c.create_line(cx, 42, cx, h - 74, fill="#0A2430")
        c.create_line(34, cy, w - 34, cy, fill="#0A2430")

        # ---------------------------------------------------------------- labels/top markers
        c.create_text(26, 22, anchor="nw", text="ULTRON // NEURAL CORE", fill=CYAN,
                      font=("Consolas", 9, "bold"))
        c.create_text(w - 26, 22, anchor="ne", text="CORE LINK  •  STABLE", fill=GREEN,
                      font=("Consolas", 8, "bold"))

        # ---------------------------------------------------------------- ring system
        orb_r = size * 0.20 * (1.0 + self.voice_level * 0.14)
        reactor_r = orb_r * (2.25 + self.voice_level * 0.24)

        # glow-like concentric rings
        for i in range(13, 0, -1):
            rr = reactor_r * (0.54 + i * 0.035)
            shade = CYAN_D if i % 2 else "#0A2937"
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                          outline=shade, width=1)

        # segmented external arcs
        for i, rr_frac in enumerate((0.285, 0.33, 0.378, 0.425, 0.472)):
            rr = size * rr_frac
            rotation = (self.phase * (24 + i * 7) + i * 71) % 360
            for j in range(3 if i < 3 else 2):
                start = rotation + j * (132 + i * 11)
                extent = 46 + ((i * 13 + j * 9) % 32) + self.voice_level * 28
                color = primary if j == 0 else (accent if (i + j) % 3 == 0 else CYAN_D)
                c.create_arc(cx - rr, cy - rr, cx + rr, cy + rr,
                             start=start, extent=extent, outline=color,
                             width=2 if i < 2 else 1)

        # radial tick marks
        tick_r1 = reactor_r * 1.02
        tick_r2 = reactor_r * 1.075
        for deg in range(0, 360, 10):
            a = math.radians(deg)
            inner = tick_r1 - (8 if deg % 30 else 0)
            x1 = cx + math.cos(a) * inner
            y1 = cy + math.sin(a) * inner
            x2 = cx + math.cos(a) * tick_r2
            y2 = cy + math.sin(a) * tick_r2
            color = BORDER_2 if deg % 30 else CYAN_D
            c.create_line(x1, y1, x2, y2, fill=color, width=2 if deg % 30 == 0 else 1)

        # rotating radar sweeps
        sweep_specs = (
            (reactor_r * 0.95, 1.0, 72, primary),
            (reactor_r * 0.80, -0.76, 48, accent),
            (reactor_r * 0.64, 1.27, 38, CYAN_2),
        )
        for rr, speed, extent, color in sweep_specs:
            start = (self.phase * 73.0 * speed) % 360
            c.create_arc(cx - rr, cy - rr, cx + rr, cy + rr,
                         start=start, extent=extent + self.voice_level * 38,
                         outline=color, width=3)

        # ---------------------------------------------------------------- particles / sparks
        kick = 1.0 + self.voice_level * 5.3
        for p in self.particles:
            p["a"] += p["speed"] * 0.005 * kick
            pulse = 0.018 * math.sin(self.phase * 4.5 + p["jitter"])
            rr = reactor_r * (p["r"] + pulse)
            x = cx + math.cos(p["a"]) * rr * 1.02
            y = cy + math.sin(p["a"]) * rr * 0.56
            if x < 15 or x > w - 15 or y < 46 or y > h - 76:
                continue
            s = p["size"] * (0.8 + self.voice_level * 2.8)
            col = hot if p["hot"] > 0.90 else accent if p["hot"] > 0.68 else primary
            c.create_oval(x - s, y - s, x + s, y + s, fill=col, outline="")

        # ---------------------------------------------------------------- central energy orb
        # Layered circles approximate a soft glow using Tkinter's solid fills.
        layers = 17
        glow = orb_r * (1.95 + self.voice_level * 0.45)
        for i in range(layers, 0, -1):
            rr = glow * (i / layers)
            if i >= 14:
                fill = "#03111A"
            elif i >= 10:
                fill = "#06202B"
            elif i >= 7:
                fill = "#073140"
            elif i >= 4:
                fill = "#0A4352"
            else:
                fill = "#0F5664"
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=fill, outline="")

        # ellipsoidal plasma bands
        for i in range(12):
            rr = orb_r * (0.48 + i * 0.064)
            wobble = 0.80 + 0.08 * math.sin(self.phase * 2.4 + i)
            start = (self.phase * (37 + i * 3.4) + i * 31) % 360
            span = 112 + self.voice_level * (18 + i)
            c.create_arc(cx - rr, cy - rr * wobble, cx + rr, cy + rr * wobble,
                         start=start, extent=span,
                         outline=primary if i % 2 == 0 else accent,
                         width=1)
            c.create_arc(cx - rr, cy - rr * wobble, cx + rr, cy + rr * wobble,
                         start=start + 180, extent=span * 0.32,
                         outline=hot if i % 3 == 0 else CYAN_D,
                         width=1)

        # plasma filaments / electrical scratches
        filaments = 64
        filament_kick = 1.0 + self.voice_level * 2.2
        for i in range(filaments):
            a = math.tau * i / filaments + self.phase * (0.48 + (i % 6) * 0.018)
            noise = math.sin(i * 2.31 + self.phase * 7.0)
            r1 = orb_r * (0.72 + 0.17 * noise)
            r2 = r1 + orb_r * (0.10 + self.voice_level * 0.12) * filament_kick
            a2 = a + 0.035 * math.sin(i * 5 + self.phase * 4)
            x1 = cx + math.cos(a) * r1
            y1 = cy + math.sin(a) * r1
            x2 = cx + math.cos(a2) * r2
            y2 = cy + math.sin(a2) * r2
            color = hot if i % 11 == 0 else primary
            c.create_line(x1, y1, x2, y2, fill=color, width=1)

        # central plasma nucleus
        nucleus = orb_r * (0.31 + self.voice_level * 0.10)
        for i in range(9, 0, -1):
            rr = nucleus * i / 9
            fill = "#15414C" if i > 6 else "#2A7A84" if i > 3 else "#8BE6EE" if i > 1 else "#EFFDFF"
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=fill, outline="")

        # subtle energy spokes
        for deg in range(0, 360, 20):
            a = math.radians(deg)
            inner = nucleus * 1.15
            outer = orb_r * (0.80 + 0.08 * math.sin(self.phase * 4 + deg))
            x1 = cx + math.cos(a) * inner
            y1 = cy + math.sin(a) * inner
            x2 = cx + math.cos(a) * outer
            y2 = cy + math.sin(a) * outer
            c.create_line(x1, y1, x2, y2, fill="#3B9DA8", width=1)

        # orb labels
        c.create_text(cx, cy - 7, text="ULTRON", fill="#F0FEFF",
                      font=("Consolas", max(14, int(size * 0.025)), "bold"))
        c.create_text(cx, cy + 18, text="NEURAL ENERGY CORE", fill="#7CB6C4",
                      font=("Consolas", max(7, int(size * 0.010))))

        # ---------------------------------------------------------------- energy spectrum / orange bar
        baseline = min(h - 100, cy + reactor_r + 22)
        bars = 54
        span = min(w * 0.58, size * 0.62)
        bw = max(3.0, span / bars)
        left = cx - span * 0.5
        center_gain = 1.0 - abs((bars / 2) - 0.5 - 0) / bars

        for i in range(bars):
            carrier = 0.22 + 0.78 * abs(math.sin(self.phase * 6.8 + i * 0.50))
            detail = 0.45 + 0.55 * abs(math.sin(self.phase * 13.0 - i * 0.31))
            distance = abs(i - (bars - 1) / 2) / ((bars - 1) / 2)
            profile = 0.45 + 0.55 * (1.0 - distance * 0.65)
            hgt = 3.0 + (5.0 + self.voice_level * 48.0) * carrier * detail * profile
            x = left + i * bw
            col = ORANGE if (i % 7 == 0 or self.state == "SPEAKING") else ORANGE_2
            if self.state == "LISTENING":
                col = CYAN if i % 8 else GREEN
            c.create_rectangle(x, baseline - hgt, x + bw * 0.58, baseline,
                               fill=col, outline="")

        # orange/cyan baseline + end caps
        line_color = ORANGE if self.state == "SPEAKING" else CYAN_D
        c.create_line(left - 8, baseline, left + span + 8, baseline,
                      fill=line_color, width=1)
        c.create_line(left - 18, baseline, left - 7, baseline, fill=ORANGE_2, width=2)
        c.create_line(left + span + 7, baseline, left + span + 18, baseline,
                      fill=ORANGE_2, width=2)

        # ---------------------------------------------------------------- status exactly below the little bar
        state_color = self._state_color()
        state_map = {
            "IDLE": "●  READY",
            "LISTENING": "◉  LISTENING",
            "STANDBY": "◌  STANDBY  ·  WAKE WORD",
            "THINKING": "◈  THINKING",
            "SPEAKING": "●  SPEAKING",
        }
        state_text = state_map.get(self.state, f"●  {self.state}")
        status_y = min(h - 45, baseline + 27)
        c.create_text(cx, status_y, text=state_text, fill=state_color,
                      font=("Consolas", 11, "bold"))
        c.create_text(cx, status_y + 19,
                      text="VOICE LINK  •  SPEECH-TO-TEXT  •  TEXT-TO-SPEECH",
                      fill="#476D7A", font=("Consolas", 7))

        # ---------------------------------------------------------------- corners / technical labels
        bracket = size * 0.44
        corner = 34
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x = cx + sx * bracket
            y = cy + sy * bracket * 0.79
            c.create_line(x - sx * corner, y, x, y, fill=CYAN_D, width=2)
            c.create_line(x, y, x, y - sy * corner, fill=CYAN_D, width=2)

        c.create_text(24, h - 20, anchor="sw",
                      text="PLASMA FIELD  •  PARTICLE ARRAY  •  AUDIO ENVELOPE",
                      fill="#2A5260", font=("Consolas", 7))
        c.create_text(w - 24, h - 20, anchor="se", text="ULTRON CORE 07",
                      fill="#2A5260", font=("Consolas", 7))

    def _state_color(self):
        return {
            "IDLE": MUTED,
            "LISTENING": GREEN,
            "STANDBY": YELLOW,
            "THINKING": CYAN,
            "SPEAKING": ORANGE,
        }.get(self.state, CYAN)


class UltronGUI:
    def __init__(self, provider=None):
        self.q: queue.Queue = queue.Queue()
        self.brain = None
        self.provider = provider or CFG.provider
        self.busy = False
        self.voice = None
        self.voice_enabled = True
        self.voice_playing = False
        self._voice_lock = threading.Lock()
        self._greeting_spoken = False
        self._closing = False
        self._speech_generation = 0
        self._voice_thread = None
        self._passive_listening = False
        self._standby_mode = False
        self._awaiting_command = False
        self._command_pending = threading.Event()
        self._wake_words = ("wake up ultron", "wake up", "ultron")
        self._last_speech_text = ""

        self.root = tk.Tk()
        self.root.title("ULTRON // NEURAL CORE")
        self.root.configure(bg=BG)
        self.root.geometry("1480x900")
        self.root.minsize(1180, 720)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._build()
        self.root.after(50, self._drain)
        self.root.after(120, self._boot)
        self.root.bind("<Control-space>", lambda _e: self._speak())
        self.root.bind("<Escape>", lambda _e: self._stop_voice())
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    # ---------------------------------------------------------------- layout
    def _panel(self, parent, width=None):
        f = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        if width:
            f.configure(width=width)
            f.pack_propagate(False)
        return f

    def _label(self, parent, text, fg=MUTED, font=FONT_SM, **kw):
        return tk.Label(parent, text=text, fg=fg, bg=parent.cget("bg"), font=font, **kw)

    def _build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=18, pady=(13, 8))
        tk.Label(top, text="U.L.T.R.O.N", fg=RED, bg=BG, font=FONT_BIG).pack(side="left")
        tk.Label(top, text="  //  NEURAL AUTONOMOUS INTELLIGENCE",
                 fg="#5D7B8C", bg=BG, font=FONT_SM).pack(side="left", padx=8)
        self.status = tk.Label(top, text="BOOTING", fg=MUTED, bg=BG, font=FONT_SM)
        self.status.pack(side="right")
        self.brain_lbl = tk.Label(top, text="", fg=CYAN, bg=BG, font=FONT_SM)
        self.brain_lbl.pack(side="right", padx=20)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=18)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(8, 12))

        # left telemetry
        left = self._panel(body, 208)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._label(left, "SYSTEM TELEMETRY", CYAN_2, FONT_MED).pack(anchor="w", padx=12, pady=(12, 8))
        self.mon = {}
        for key in ("CPU", "MEM", "DISK", "NET", "UPTIME", "PROC"):
            row = tk.Frame(left, bg=PANEL)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=key, fg=MUTED, bg=PANEL, font=FONT_SM).pack(side="left")
            v = tk.Label(row, text="—", fg=CYAN, bg=PANEL, font=FONT_SM)
            v.pack(side="right")
            self.mon[key] = v

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=12, pady=12)
        self._label(left, "VOICE LINK", CYAN_2, FONT_MED).pack(anchor="w", padx=12, pady=(2, 5))
        self.voice_state_lbl = tk.Label(left, text="INITIALISING", fg=MUTED, bg=PANEL, font=FONT_SM)
        self.voice_state_lbl.pack(anchor="w", padx=12, pady=3)

        self.voice_mode_lbl = tk.Label(left, text="MODE  ·  ALWAYS LISTENING", fg=GREEN, bg=PANEL, font=FONT_SM)
        self.voice_mode_lbl.pack(anchor="w", padx=12, pady=3)
        self._label(left, "CONTROL CHANNEL", CYAN_2, FONT_MED).pack(anchor="w", padx=12, pady=(18, 6))
        self._label(left, "Use the controls below the command box", TEXT_2, FONT_SM,
                    justify="left", wraplength=175).pack(anchor="w", padx=12)

        self._label(left, "CORE STATUS", CYAN_2, FONT_MED).pack(anchor="w", padx=12, pady=(18, 6))
        self.core_label = tk.Label(left, text="● CORE STANDBY", fg=GREEN, bg=PANEL, font=FONT_SM)
        self.core_label.pack(anchor="w", padx=12)

        # center HUD
        center = tk.Frame(body, bg=BG)
        center.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.hud = UltronHUD(center)

        # right activity + command
        right = self._panel(body, 386)
        right.pack(side="left", fill="y")
        self._label(right, "ACTIVITY / MEMORY STREAM", CYAN_2, FONT_MED).pack(anchor="w", padx=12, pady=(12, 6))

        self.feed = scrolledtext.ScrolledText(
            right, bg=PANEL_2, fg=TEXT, font=FONT, wrap="word", bd=0,
            highlightbackground=BORDER, highlightthickness=1, insertbackground=CYAN,
            padx=10, pady=10, state="disabled")
        self.feed.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.feed.tag_config("user", foreground=USER)
        self.feed.tag_config("ultron", foreground=CYAN)
        self.feed.tag_config("name_u", foreground=USER, font=("Consolas", 10, "bold"))
        self.feed.tag_config("name_a", foreground=RED, font=("Consolas", 10, "bold"))
        self.feed.tag_config("sys", foreground=MUTED, font=FONT_SM)
        self.feed.tag_config("warn", foreground=ORANGE, font=FONT_SM)

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(0, 8))
        self._label(right, "COMMAND CHANNEL", CYAN_2, FONT_SM).pack(anchor="w", padx=12)
        command = tk.Frame(right, bg=right.cget("bg"))
        command.pack(fill="x", padx=10, pady=6)

        self.entry = tk.Entry(command, bg=PANEL_2, fg=TEXT, font=FONT, bd=0,
                              highlightbackground=BORDER, highlightthickness=1,
                              insertbackground=CYAN)
        self.entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 6))
        self.entry.bind("<Return>", lambda _e: self._send())
        self.entry.focus_set()

        self.send_btn = tk.Button(command, text="SEND", font=FONT_MED, fg=BG, bg=CYAN,
                                  bd=0, relief="flat", activebackground="#8CEFFF",
                                  command=self._send)
        self.send_btn.pack(side="left", ipadx=11, ipady=7)

        controls = tk.Frame(right, bg=right.cget("bg"))
        controls.pack(fill="x", padx=10, pady=(0, 7))

        self.mic_btn = tk.Button(controls, text="MIC  ·  ON", font=FONT_SM, fg=GREEN,
                                 bg="#06190F", bd=0, relief="flat",
                                 activebackground="#0A2918", activeforeground=GREEN,
                                 command=self._toggle_voice)
        self.mic_btn.pack(side="left", fill="x", expand=True, ipadx=6, ipady=7, padx=(0, 5))

        self.standby_btn = tk.Button(controls, text="STANDBY  ·  OFF", font=FONT_SM, fg=CYAN,
                                     bg="#071821", bd=0, relief="flat",
                                     activebackground="#102D39", activeforeground=CYAN,
                                     command=self._toggle_standby)
        self.standby_btn.pack(side="left", fill="x", expand=True, ipadx=6, ipady=7, padx=5)

        self.stop_btn = tk.Button(controls, text="STOP SPEECH", font=FONT_SM, fg=RED,
                                  bg="#1A070B", bd=0, relief="flat",
                                  activebackground="#2B0B12", activeforeground="#FF7080",
                                  command=self._stop_voice)
        self.stop_btn.pack(side="left", fill="x", expand=True, ipadx=6, ipady=7, padx=(5, 0))

        tk.Label(right, text="MIC = always listen   ·   STANDBY = wake word only   ·   ESC = stop speech",
                 fg="#355565", bg=right.cget("bg"), font=("Consolas", 7)).pack(pady=(0, 9))

    # -------------------------------------------------------------- utilities
    def post(self, fn):
        if not self._closing:
            self.q.put(fn)

    def _drain(self):
        if self._closing:
            return
        while True:
            try:
                fn = self.q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except tk.TclError:
                # The window may have been closed while a worker callback was queued.
                if self._closing:
                    return
            except Exception as exc:
                if not self._closing:
                    try:
                        self.add_sys(f"[UI] callback error: {exc}", "warn")
                    except Exception:
                        pass
        if not self._closing:
            self.root.after(50, self._drain)

    def _write(self, text, *tags):
        self.feed.configure(state="normal")
        self.feed.insert("end", text, tags)
        self.feed.see("end")
        self.feed.configure(state="disabled")

    def add_user(self, text):
        self._write("YOU  ", "name_u")
        self._write(text + "\n\n", "user")

    def add_ultron(self, text):
        self._write("ULTRON  ", "name_a")
        self._write(text + "\n\n", "ultron")

    def add_sys(self, text, tag="sys"):
        self._write(text + "\n", tag)

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, fg=color)

    def _set_voice_state(self, text, color=MUTED):
        self.voice_state_lbl.configure(text=text, fg=color)

    # --------------------------------------------------------------- AI boot
    def _boot(self):
        from brain import Brain

        brain_ok = False
        try:
            self.brain = Brain(self.provider, confirm=self._confirm, on_tool=self._on_tool)
            self.brain_lbl.configure(text=self.brain.label)
            self._set_status("ONLINE", GREEN)
            brain_ok = True
            self.add_sys("[CORE] neural matrix initialised")
        except Exception as e:
            self.brain = None
            self._set_status("NO BRAIN", RED)
            self.hud.set_state("IDLE")
            self.add_sys(f"[CORE] {e}", "warn")
            self.add_sys("Add a provider key in .env or set AI_PROVIDER=ollama.")

        # Voice must initialise even if the AI provider is not configured.
        threading.Thread(target=self._init_voice, args=(brain_ok,), daemon=True).start()

    def _init_voice(self, brain_ok: bool):
        try:
            from voice import Voice
            voice = Voice(
                on_listening=lambda: self._voice_state("STANDBY" if self._standby_mode and not self._awaiting_command else "LISTENING", YELLOW if self._standby_mode and not self._awaiting_command else GREEN),
                on_speaking=lambda: self._voice_state("SPEAKING", ORANGE),
                on_level=lambda level: self.post(lambda lv=level: self.hud.set_voice_level(lv)),
            )
        except Exception as e:
            self.post(lambda err=str(e): self._voice_failed(err))
            return

        with self._voice_lock:
            self.voice = voice
            self.voice_enabled = True

        self.post(lambda: self._voice_ready(brain_ok))

    def _voice_failed(self, err):
        self.voice_enabled = False
        self.mic_btn.configure(text="MIC  ·  OFF", fg=MUTED, bg=PANEL_2)
        self._set_voice_state("UNAVAILABLE", RED)
        self.hud.set_state("IDLE")
        self.add_sys(f"[VOICE] {err}", "warn")
        if "ELEVENLABS_API_KEY" in str(err):
            self.add_sys("[VOICE] Add ELEVENLABS_API_KEY to .env, then restart ULTRON.", "warn")
        else:
            self.add_sys("Install: pip install -r requirements-voice.txt", "sys")

    def _voice_ready(self, brain_ok: bool):
        self._set_voice_state("LISTENING", GREEN)
        self.mic_btn.configure(text="MIC  ·  ON", fg=GREEN, bg="#06190F")
        self.standby_btn.configure(text="STANDBY  ·  OFF", fg=CYAN, bg="#071821")
        self.voice_mode_lbl.configure(text="MODE  ·  ALWAYS LISTENING", fg=GREEN)
        self.add_sys("[VOICE] speech-to-text + text-to-speech ready")

        # Greet exactly once after the voice engine becomes available.
        if not self._greeting_spoken:
            self._greeting_spoken = True
            if brain_ok:
                greeting = "Hello. Ultron is online. What do you need?"
            else:
                greeting = "Hello. Ultron is online. Voice link is active. Configure an AI provider when you are ready."
            self.add_ultron(greeting)
            self.voice_playing = True
            self.hud.set_state("SPEAKING")
            self._set_voice_state("SPEAKING", ORANGE)
            self._set_status("SPEAKING", ORANGE)
            self.core_label.configure(text="● AUDIO OUTPUT", fg=ORANGE)
            threading.Thread(target=self._speak_reply, args=(greeting,), daemon=True).start()

        # Default mode is active listening: every spoken command is processed.
        self._standby_mode = False
        self._passive_listening = False
        self._start_continuous_listening()

    # --------------------------------------------------------------- brain UX
    def _switch(self, provider):
        from brain import Brain
        try:
            self.brain = Brain(provider, confirm=self._confirm, on_tool=self._on_tool)
            self.brain_lbl.configure(text=self.brain.label)
            self._set_status("ONLINE", GREEN)
            self.add_sys(f"— switched to {self.brain.label} —")
        except Exception as e:
            self.add_sys(f"[!] {e}", "warn")

    def _on_tool(self, name, args):
        short = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items()
                           if k not in ("body", "message", "content"))
        self.post(lambda: self.add_sys(f"  · {name}({short})"))

    def _confirm(self, name, args):
        done = threading.Event()
        box = {}
        labels = {
            "send_email": "Send email", "send_whatsapp_message": "Send WhatsApp",
            "send_discord_message": "Send Discord message", "send_message_ui": "Send message",
            "phone_unlock": "Unlock the phone", "computer_control": "Control mouse/keyboard",
            "set_reminder": "Set a reminder", "close_app": "Close app",
            "computer_setting": "Change a system setting", "file_op": "Delete a file",
        }
        detail = "\n".join(f"{k}: {str(v)[:200]}" for k, v in args.items())

        def ask():
            box["r"] = messagebox.askyesno(labels.get(name, name),
                                             f"{labels.get(name, name)}?\n\n{detail}")
            done.set()

        self.post(ask)
        done.wait()
        return box.get("r", False)

    def _send(self):
        text = self.entry.get().strip()
        if not text or self.busy or not self.brain:
            if not self.brain:
                self.add_sys("[CORE] AI provider is not configured.", "warn")
            return

        self.entry.delete(0, "end")
        self.add_user(text)
        self.busy = True
        self._set_status("THINKING", CYAN)
        self.core_label.configure(text="● CORE THINKING", fg=CYAN)
        self.hud.set_state("THINKING")
        threading.Thread(target=self._work, args=(text,), daemon=True).start()

    def _work(self, text):
        try:
            reply = self.brain.ask(text)
        except Exception as e:
            reply = f"I encountered an error: {e}"
        self.post(lambda r=reply: self._finish_reply(r))

    def _finish_reply(self, reply):
        reply = str(reply or "").strip()
        if reply:
            self.add_ultron(reply)
        self.busy = False

        if self.voice_enabled and self.voice and reply:
            self.voice_playing = True
            self.hud.set_state("SPEAKING")
            self._set_voice_state("SPEAKING", ORANGE)
            self._set_status("SPEAKING", ORANGE)
            self.core_label.configure(text="● AUDIO OUTPUT", fg=ORANGE)
            threading.Thread(target=self._speak_reply, args=(reply,), daemon=True).start()
        else:
            self.hud.set_state("IDLE")
            self._set_status("ONLINE", GREEN)
            self.core_label.configure(text="● CORE STANDBY", fg=GREEN)

    def _speak_reply(self, reply):
        voice = self.voice
        if not voice or not self.voice_enabled:
            return

        # Every utterance gets its own generation number. This prevents a
        # delayed pyttsx3 callback from leaving the HUD stuck in SPEAKING.
        with self._voice_lock:
            self._speech_generation += 1
            generation = self._speech_generation

        self.post(lambda: self._begin_speech_ui(generation))
        try:
            voice.speak(reply)
        except Exception as e:
            self.post(lambda err=str(e): self._voice_error(err))
        finally:
            # pyttsx3 can finish without emitting its driver callback on some
            # Windows speech drivers, so the GUI always gets an explicit end.
            self.post(lambda g=generation: self._after_speech(g))

    def _begin_speech_ui(self, generation):
        if self._closing:
            return
        if generation != self._speech_generation:
            return
        self.voice_playing = True
        self.hud.set_state("SPEAKING")
        self._set_voice_state("SPEAKING", ORANGE)
        self._set_status("SPEAKING", ORANGE)
        self.core_label.configure(text="● AUDIO OUTPUT", fg=ORANGE)

    def _after_speech(self, generation=None):
        if self._closing:
            return
        if generation is not None and generation != self._speech_generation:
            return

        self.voice_playing = False
        self.hud.set_voice_level(0.0)

        # Give pyttsx3's Windows callback thread a moment to drain. Then force
        # the visual state back to standby. This is deliberately unconditional
        # when no newer utterance has started.
        self.root.after(120, lambda g=generation: self._finish_speech_ui(g))

    def _finish_speech_ui(self, generation=None):
        if self._closing:
            return
        if generation is not None and generation != self._speech_generation:
            return

        self.voice_playing = False
        self.hud.set_voice_level(0.0)
        if not self.busy and self.voice_enabled and self.voice:
            # After speech, automatically return to the selected listening mode.
            active = self._awaiting_command and self._last_speech_text == "__WAKE_ACK__"
            if not active:
                self._awaiting_command = False
                self._passive_listening = self._standby_mode

            if self._standby_mode and not self._awaiting_command:
                self.hud.set_state("STANDBY")
                self._set_voice_state("STANDBY", YELLOW)
                self._set_status("STANDBY", YELLOW)
                self.core_label.configure(text="● WAKE WORD ACTIVE", fg=YELLOW)
            else:
                self.hud.set_state("LISTENING")
                self._set_voice_state("LISTENING", GREEN)
                self._set_status("LISTENING", GREEN)
                self.core_label.configure(text="● MIC ACTIVE", fg=GREEN)
            self._start_continuous_listening()
        else:
            self.hud.set_state("THINKING" if self.busy else "IDLE")
            self._set_voice_state("THINKING" if self.busy else "READY", CYAN if self.busy else GREEN)
            self._set_status("THINKING" if self.busy else "ONLINE", CYAN if self.busy else GREEN)
            self.core_label.configure(text="● CORE THINKING" if self.busy else "● CORE STANDBY", fg=CYAN if self.busy else GREEN)

    # ---------------------------------------------------------------- voice
    def _voice_state(self, state, color):
        # Canvas updates are lightweight but still schedule a UI update through post.
        self.post(lambda s=state: self.hud.set_state(s))
        self.post(lambda s=state, c=color: self._apply_voice_state_ui(s, c))

    def _apply_voice_state_ui(self, state, color):
        self._set_voice_state(state, color)
        if state == "SPEAKING":
            self.voice_playing = True
            self._set_status("SPEAKING", ORANGE)
            self.core_label.configure(text="● AUDIO OUTPUT", fg=ORANGE)
        elif state == "LISTENING":
            self.voice_playing = False
            self._set_status("LISTENING", GREEN)
            self.core_label.configure(text="● MIC ACTIVE", fg=GREEN)
        elif state == "STANDBY":
            self.voice_playing = False
            self._set_status("STANDBY", YELLOW)
            self.core_label.configure(text="● WAKE WORD ACTIVE", fg=YELLOW)
        else:
            self.voice_playing = False
            if not self.busy:
                self._set_status("ONLINE", GREEN)
                self.core_label.configure(text="● CORE STANDBY", fg=GREEN)

    def _speak(self):
        """Force one active command capture, regardless of standby mode."""
        if self._closing or self.busy or not self.brain or not self.voice or not self.voice_enabled:
            return
        self._awaiting_command = True
        self._passive_listening = False
        self._last_speech_text = ""
        self._stop_current_listen()

    def _start_continuous_listening(self):
        if self._closing or not self.voice or not self.voice_enabled:
            return
        if self._voice_thread and self._voice_thread.is_alive():
            return
        self._voice_thread = threading.Thread(
            target=self._continuous_voice_loop, name="ultron-continuous-stt", daemon=True
        )
        self._voice_thread.start()

    def _stop_current_listen(self):
        voice = self.voice
        if voice:
            threading.Thread(target=voice.stop_listening, name="ultron-stop-stt", daemon=True).start()

    def _continuous_voice_loop(self):
        """Continuously listen. Normal mode processes speech; standby requires a wake word."""
        while not self._closing and self.voice_enabled and self.voice:
            if self.voice_playing or self.busy or self._command_pending.is_set():
                time.sleep(0.12)
                continue

            passive = self._standby_mode and not self._awaiting_command
            self._passive_listening = passive
            self.post(lambda: self._apply_voice_state_ui("STANDBY" if passive else "LISTENING", YELLOW if passive else GREEN))

            try:
                text = self.voice.listen(timeout=4.0, phrase_time_limit=30.0)
            except Exception as e:
                self.post(lambda err=str(e): self._voice_error(err))
                time.sleep(0.5)
                continue

            if not text:
                continue

            normalized = " ".join(text.lower().split())
            if passive:
                wake = next((phrase for phrase in self._wake_words if phrase in normalized), None)
                if not wake:
                    continue
                remainder = normalized.replace(wake, "", 1).strip()
                self._awaiting_command = True
                self._passive_listening = False
                if remainder:
                    text = remainder
                else:
                    self._last_speech_text = "__WAKE_ACK__"
                    self.post(lambda: self.add_sys("[VOICE] Wake phrase detected — listening for command."))
                    threading.Thread(target=self._speak_reply, args=("I'm listening.",), daemon=True).start()
                    continue

            # A real command is now ready. Mark it pending before posting to Tk.
            self._command_pending.set()
            self._last_speech_text = ""
            self.post(lambda t=text: self._handle_voice_command(t))

            while not self._closing and (self._command_pending.is_set() or self.busy or self.voice_playing):
                time.sleep(0.12)

            self._awaiting_command = False
            self._passive_listening = self._standby_mode

    def _handle_voice_command(self, text):
        if self._closing or not text or self.busy or not self.brain:
            self._command_pending.clear()
            return
        self._command_pending.clear()
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.add_user(text)
        self.busy = True
        self._set_status("THINKING", CYAN)
        self.core_label.configure(text="● CORE THINKING", fg=CYAN)
        self.hud.set_state("THINKING")
        threading.Thread(target=self._work, args=(text,), name="ultron-brain", daemon=True).start()

    def _voice_error(self, err):
        self._set_voice_state("ERROR", RED)
        self.hud.set_state("IDLE")
        self._set_status("VOICE ERROR", RED)
        self.add_sys(f"[VOICE] {err}", "warn")

    def _toggle_voice(self):
        """Turn the microphone listener on/off. This does not change standby mode."""
        if not self.voice:
            self.add_sys("[VOICE] still initialising or unavailable", "warn")
            return

        if not self.voice_enabled:
            self.voice_enabled = True
            self.mic_btn.configure(text="MIC  ·  ON", fg=GREEN, bg="#06190F")
            if self._standby_mode:
                self._set_voice_state("STANDBY", YELLOW)
                self._set_status("STANDBY", YELLOW)
                self.core_label.configure(text="● WAKE WORD ACTIVE", fg=YELLOW)
            else:
                self._set_voice_state("LISTENING", GREEN)
                self._set_status("LISTENING", GREEN)
                self.core_label.configure(text="● MIC ACTIVE", fg=GREEN)
            self.add_sys("[VOICE] microphone enabled")
            self._start_continuous_listening()
            return

        self.voice_enabled = False
        self._awaiting_command = False
        self._command_pending.clear()
        self.mic_btn.configure(text="MIC  ·  OFF", fg=MUTED, bg=PANEL_2)
        self._set_voice_state("DISABLED", MUTED)
        self._set_status("MIC OFF", MUTED)
        self.core_label.configure(text="● MIC OFF", fg=MUTED)
        self.hud.set_state("IDLE")
        self.hud.set_voice_level(0.0)
        self.add_sys("[VOICE] microphone disabled")
        self._cancel_voice_async()

    def _toggle_standby(self):
        """Toggle wake-word standby. Normal mode listens to every utterance."""
        if not self.voice or not self.voice_enabled:
            self.add_sys("[VOICE] turn MIC ON before enabling standby", "warn")
            return

        self._standby_mode = not self._standby_mode
        self._awaiting_command = False
        self._last_speech_text = ""
        self._stop_current_listen()

        if self._standby_mode:
            self._passive_listening = True
            self.standby_btn.configure(text="STANDBY  ·  ON", fg=YELLOW, bg="#201B07")
            self.voice_mode_lbl.configure(text="MODE  ·  WAKE WORD ONLY", fg=YELLOW)
            self._set_voice_state("STANDBY", YELLOW)
            self._set_status("STANDBY", YELLOW)
            self.core_label.configure(text="● WAKE WORD ACTIVE", fg=YELLOW)
            self.add_sys("[VOICE] standby enabled — say 'wake up' or 'Ultron'")
        else:
            self._passive_listening = False
            self.standby_btn.configure(text="STANDBY  ·  OFF", fg=CYAN, bg="#071821")
            self.voice_mode_lbl.configure(text="MODE  ·  ALWAYS LISTENING", fg=GREEN)
            self._set_voice_state("LISTENING", GREEN)
            self._set_status("LISTENING", GREEN)
            self.core_label.configure(text="● MIC ACTIVE", fg=GREEN)
            self.add_sys("[VOICE] standby disabled — continuous listening resumed")

        self._start_continuous_listening()

    def _cancel_voice_async(self):
        """Stop audio on a worker thread so ESC/buttons never freeze or crash Tk."""
        voice = self.voice
        if not voice:
            return

        def worker():
            try:
                voice.stop_listening()
            except Exception:
                pass
            try:
                voice.stop_speaking()
            except Exception:
                pass

        threading.Thread(target=worker, name="ultron-voice-stop", daemon=True).start()

    def _stop_voice(self):
        """Stop current speech/listening without turning the microphone off."""
        self._cancel_voice_async()
        self._command_pending.clear()
        self._awaiting_command = False
        self.voice_playing = False
        self.hud.set_state("IDLE")
        self.hud.set_voice_level(0.0)

        if self.voice and self.voice_enabled:
            self._passive_listening = self._standby_mode
            self._set_voice_state("STANDBY" if self._standby_mode else "LISTENING", YELLOW if self._standby_mode else GREEN)
            self._set_status("STANDBY" if self._standby_mode else "LISTENING", YELLOW if self._standby_mode else GREEN)
            self.core_label.configure(text="● WAKE WORD ACTIVE" if self._standby_mode else "● MIC ACTIVE",
                                      fg=YELLOW if self._standby_mode else GREEN)
            self._start_continuous_listening()
        else:
            self._set_status("MIC OFF", MUTED)
            self.core_label.configure(text="● MIC OFF", fg=MUTED)

    # --------------------------------------------------------------- monitor
    def _monitor_loop(self):
        try:
            import psutil
        except ImportError:
            return

        root_path = os.path.abspath(os.sep)
        while not self._closing:
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage(root_path).percent
                net = psutil.net_io_counters()
                up = time.time() - psutil.boot_time()
                stats = {
                    "CPU": f"{cpu:.0f}%",
                    "MEM": f"{ram:.0f}%",
                    "DISK": f"{disk:.0f}%",
                    "NET": f"{(net.bytes_sent + net.bytes_recv)/1048576:.0f} MB",
                    "UPTIME": f"{int(up//3600)}h {int((up%3600)//60)}m",
                    "PROC": str(len(psutil.pids())),
                }
                self.post(lambda s=stats: [self.mon[k].configure(text=v) for k, v in s.items()])
            except Exception:
                pass
            time.sleep(2)

    def _close(self):
        if self._closing:
            return
        self._closing = True
        try:
            self.hud.stop()
            if self.voice:
                threading.Thread(target=self.voice.close, name="ultron-voice-close", daemon=True).start()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    import argparse
    p = argparse.ArgumentParser(description="ULTRON futuristic GUI")
    p.add_argument("--provider", choices=["claude", "chatgpt", "local"])
    o = p.parse_args()
    prov = {"claude": "anthropic", "chatgpt": "openai", "local": "ollama"}.get(o.provider)
    UltronGUI(prov).run()


if __name__ == "__main__":
    main()
