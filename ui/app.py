import math
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Jarvis Color Palette
JARVIS_PRIMARY = "#ff3b30"
JARVIS_ACCENT  = "#ffd60a"
BG_DARK        = "#0b0f14"
BG_LIGHT       = "#f7f7f8"

class AssistantUI:
    def __init__(self, root: tk.Tk, on_submit, title: str = "TORQUE", on_force_stop=None):
        self.root = root
        self.on_submit = on_submit
        self.on_force_stop = on_force_stop or (lambda: None)

        # Style Setup
        try:
            self.style = tb.Style(theme="cyborg")
        except Exception:
            self.style = tb.Style()

        self.current_theme = "dark"

        root.title(f"{title} Assistant")
        root.geometry("900x640")
        root.minsize(760, 520)

        self._is_listening = False
        self._is_speaking = False
        self._pulse_phase = 0.0
        self._pulse_id = None

        # --- Header ---
        header = tb.Frame(root, bootstyle="primary", height=6)
        header.pack(fill="x")

        title_row = tb.Frame(root, padding=(12, 8, 12, 8))
        title_row.pack(fill="x")

        self._title_lbl = tb.Label(
            title_row,
            text=f"◉ {title}",
            font=("Segoe UI Black", 20),
            foreground=JARVIS_PRIMARY
        )
        self._title_lbl.pack(side="left")

        # Theme toggle
        right = tb.Frame(title_row)
        right.pack(side="right")
        tb.Label(right, text="Theme").pack(side="left", padx=(0, 6))
        self.theme_var = tk.StringVar(value="dark")
        self.theme_btn = tb.Checkbutton(
            right,
            text="Dark",
            bootstyle="primary-round-toggle",
            command=self._toggle_theme,
            variable=self.theme_var,
            onvalue="dark",
            offvalue="light"
        )
        self.theme_btn.pack(side="left")

        # --- Status bar ---
        top = tb.Frame(root, padding=(12, 4, 12, 0))
        top.pack(fill="x")
        self.status_var = tk.StringVar(value="● Booting")
        self.status_lbl = tb.Label(top, textvariable=self.status_var, font=("Segoe UI", 11, "bold"))
        self.status_lbl.pack(side="left")

        mic_box = tb.Frame(top)
        mic_box.pack(side="right")
        tb.Label(mic_box, text="Mic", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.mic = tb.Progressbar(
            mic_box,
            orient="horizontal",
            mode="determinate",
            length=200,
            maximum=100,
            bootstyle="info-striped"
        )
        self.mic.pack(side="left")

        # --- Pulse and caption area ---
        center = tb.Frame(root, padding=(12, 8))
        center.pack(fill="x")
        self.pulse = tk.Canvas(center, width=200, height=200, highlightthickness=0, bg=BG_DARK, bd=0)
        self.pulse.pack(side="left", padx=(0, 16))
        self._pulse_circle = self.pulse.create_oval(60, 60, 140, 140, outline=JARVIS_ACCENT, width=4)
        self._schedule_pulse()

        cap_col = tb.Frame(center)
        cap_col.pack(side="left", fill="both", expand=True)
        tb.Label(cap_col, text="Heard:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.caption_var = tk.StringVar(value="")
        self.caption = tb.Label(cap_col, textvariable=self.caption_var, font=("Segoe UI", 12))
        self.caption.pack(fill="x", pady=(6, 0))

        # --- Log / Chat Display ---
        log_frame = tb.Frame(root, padding=(12, 8))
        log_frame.pack(fill="both", expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            state="disabled",
            font=("Consolas", 11),
            bg="#0e131a",
            fg="#e6e6e6",
            insertbackground="#ffffff",
            relief="flat"
        )
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_config("user", foreground=self.style.colors.get("primary"))
        self.log.tag_config("torque", foreground=JARVIS_PRIMARY)
        self.log.tag_config("system", foreground=self.style.colors.get("danger"))
        self.log.tag_config("prefix", font=("Consolas", 11, "bold"))

        # --- Input area ---
        input_row = tb.Frame(root, padding=(12, 8, 12, 12))
        input_row.pack(fill="x")
        self.entry = tb.Entry(input_row, font=("Segoe UI", 11), bootstyle="primary")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self._submit())
        tb.Button(input_row, text="Send", bootstyle="success", command=self._submit).pack(side="left", padx=(0, 8))
        tb.Button(input_row, text="Force Stop", bootstyle="danger-outline", command=self._force_stop).pack(side="left")

        # Initial message
        self._blink()
        self.append("UI loaded. Use voice after wake word, or type a command and press Send.", is_torque=True)

    # ----------------------------- METHODS -----------------------------

    def append(self, text: str, is_torque: bool = False, is_system: bool = False):
        if not text:
            return
        tag = "system" if is_system else ("torque" if is_torque else "user")
        prefix = "[System] " if is_system else ("TORQUE: " if is_torque else "You: ")
        self.log.configure(state="normal")
        self.log.insert("end", prefix, 'prefix')
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, text: str):
        self.status_var.set(str(text or ""))

    def set_listening(self, is_listening: bool):
        self._is_listening = bool(is_listening)

    def set_speaking(self, is_speaking: bool):
        self._is_speaking = bool(is_speaking)

    def set_caption(self, text: str):
        self.caption_var.set(str(text or ""))

    def update_mic_level(self, level: int):
        try:
            self.mic["value"] = max(0, min(100, int(level)))
        except Exception:
            self.mic["value"] = 0

    def _submit(self):
        txt = self.entry.get().strip()
        if not txt:
            return
        self.append(txt, is_torque=False)
        self.entry.delete(0, "end")
        try:
            self.on_submit(txt)
        except Exception as e:
            self.append(f"submit error: {e}", is_system=True)

    def _force_stop(self):
        self.append("Force stopping current session.", is_system=True)
        try:
            self.on_force_stop()
        except Exception as e:
            self.append(f"force stop error: {e}", is_system=True)

    def _blink(self):
        prefix = "● Speaking" if self._is_speaking else ("● Listening" if self._is_listening else "● Idle")
        tail = ""
        if "—" in self.status_var.get():
            tail = self.status_var.get().split("—", 1)[1].strip()
        self.status_var.set(prefix + (f" — {tail}" if tail else ""))
        self.root.after(600, self._blink)

    def _schedule_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.10) % (2.0 * math.pi)
        r0 = 40
        base = 1.12 if self._is_speaking else (1.06 if self._is_listening else 1.0)
        scale = base + 0.08 * math.sin(self._pulse_phase)
        r = r0 * scale
        cx, cy = 100, 100
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
        color = JARVIS_PRIMARY if self._is_speaking or self._is_listening else JARVIS_ACCENT
        try:
            self.pulse.coords(self._pulse_circle, x0, y0, x1, y1)
            self.pulse.itemconfig(self._pulse_circle, outline=color)
        except tk.TclError:
            return
        self._pulse_id = self.root.after(40, self._schedule_pulse)

    def _toggle_theme(self):
        mode = self.theme_var.get()
        if mode == "light":
            self.style.theme_use("flatly")
            self.current_theme = "light"
            self.root.configure(bg=BG_LIGHT)
            self.log.configure(bg="#ffffff", fg="#1f1f1f", insertbackground="#1f1f1f")
            self.pulse.configure(bg=BG_LIGHT)
            self.theme_btn.config(text="Light")
            self._title_lbl.config(foreground=self.style.colors.get("primary"))
        else:
            self.style.theme_use("cyborg")
            self.current_theme = "dark"
            self.root.configure(bg=BG_DARK)
            self.log.configure(bg="#0e131a", fg="#e6e6e6", insertbackground="#ffffff")
            self.pulse.configure(bg=BG_DARK)
            self.theme_btn.config(text="Dark")
            self._title_lbl.config(foreground=JARVIS_PRIMARY)
