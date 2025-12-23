# src/ui/app.py
import math
import tkinter as tk
import time

# ==========================
# Theme
# ==========================
BG_MAIN        = "#044163"
CYAN_PRIMARY   = "#00E1FF"
CYAN_MED       = "#34EEFF"
CYAN_SOFT      = "#6FEFFF"

USER_BUBBLE    = "#002238"
AI_BUBBLE      = "#00324D"
SYS_BUBBLE     = "#1E3A4D"

# ==========================
# Utilities
# ==========================
def lerp_color(hex_a, hex_b, t):
    """Interpolate between two hex colors. t in [0,1]."""
    a = int(hex_a.lstrip("#"), 16)
    b = int(hex_b.lstrip("#"), 16)
    ar, ag, ab = (a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF
    br, bg, bb = (b >> 16) & 0xFF, (b >> 8) & 0xFF, b & 0xFF
    rr = int(ar + (br - ar) * t)
    rg = int(ag + (bg - ag) * t)
    rb = int(ab + (bb - ab) * t)
    return f"#{rr:02x}{rg:02x}{rb:02x}"

# ==========================
# Chat bubble with icon + fade-in + slide
# ==========================
class ChatBubble(tk.Frame):
    def __init__(self, master, text, sender="user", bounce=True, icon_robot_style=1, icon_user_style='B'):
        super().__init__(master, bg=BG_MAIN)
        self.sender = sender
        self.text = text
        self.bounce = bool(bounce)
        self.icon_robot_style = icon_robot_style
        self.icon_user_style = icon_user_style

        # choose colors and side
        if sender == "user":
            bubble_color = USER_BUBBLE
            side = "right"
            icon_side = "right"
        elif sender == "torque":
            bubble_color = AI_BUBBLE
            side = "left"
            icon_side = "left"
        else:
            bubble_color = SYS_BUBBLE
            side = "left"
            icon_side = "left"

        # row contains icon + bubble (so icon left for AI, right for user)
        row = tk.Frame(self, bg=BG_MAIN)
        row.pack(fill="x", pady=6, padx=6)  # <— Added left/right padding


        # For left side: icon -> bubble; for right: bubble -> icon
        if icon_side == "left":
            icon = self._make_icon(row, sender)
            icon.pack(side="left", padx=(4, 6))

            bubble = tk.Frame(row, bg=bubble_color, padx=8, pady=6)

            bubble.pack(side="left", padx=(6, 200 if self.bounce else 6))
        else:
            bubble = tk.Frame(row, bg=bubble_color, padx=12, pady=8)
            bubble.pack(side="right", padx=(200 if self.bounce else 6, 6))
            icon = self._make_icon(row, sender)
            icon.pack(side="right", padx=(6, 4))


        # text label (starts invisible color, will fade to white)
        self.lbl = tk.Label(
            bubble,
            text=self.text,
            bg=bubble_color,
            fg=BG_MAIN,
            wraplength=260,            # smaller wrap width
            justify="left",
            font=("Comic Sans MS", 9)  # NEW cosmic sans font
        )

        self.lbl.pack()

        # tail
        tail = tk.Canvas(row, width=14, height=14, bg=BG_MAIN, highlightthickness=0)
        if side == "right":
            tail.pack(side="right", padx=(0,6))
            tail.create_polygon(0,7, 14,0, 14,14, fill=bubble_color, outline=bubble_color)
        else:
            tail.pack(side="left", padx=(6,0))
            tail.create_polygon(14,7, 0,0, 0,14, fill=bubble_color, outline=bubble_color)

        # animation state
        self._fade_step = 0
        self._fade_steps = 12
        self._slide_step = 0
        self._slide_steps = 12
        self._bubble_widget = bubble
        # start animations
        self.after(10, self._animate_step)

    def _make_icon(self, parent, sender):
        """Create and return a small Canvas icon for sender.
           Robot style 1: boxy robot head (chosen by user). User style B: minimal rounded user.
        """
        c = tk.Canvas(parent, width=36, height=36, bg=BG_MAIN, highlightthickness=0)
        if sender == "torque":
            # Robot boxy style (style 1)
            # head rectangle
            c.create_rectangle(6,8,30,26, outline=CYAN_PRIMARY, width=2, fill="")
            # eyes
            c.create_oval(10,12,14,16, fill=CYAN_PRIMARY, outline=CYAN_PRIMARY)
            c.create_oval(22,12,26,16, fill=CYAN_PRIMARY, outline=CYAN_PRIMARY)
            # mouth (line)
            c.create_line(12,22,24,22, fill=CYAN_PRIMARY, width=2)
            # small antenna
            c.create_line(18,6,18,8, fill=CYAN_PRIMARY, width=2)
        elif sender == "user":
            # Minimal rounded user (style B)
            # head circle
            c.create_oval(10,6,26,22, outline=USER_BUBBLE, width=2, fill=USER_BUBBLE)
            # body (rounded rectangle / semicircle)
            c.create_rectangle(8,20,28,30, outline=USER_BUBBLE, width=1, fill=USER_BUBBLE)
        else:
            # system: small neutral circle
            c.create_oval(8,8,28,28, outline=CYAN_MED, width=2, fill=CYAN_MED)
        return c

    def _animate_step(self):
        # fade text color from BG_MAIN -> white
        if self._fade_step <= self._fade_steps:
            t = self._fade_step / self._fade_steps
            color = lerp_color(BG_MAIN, "#ffffff", t)
            try:
                self.lbl.configure(fg=color)
            except Exception:
                pass
            self._fade_step += 1

        # slide/bounce by reducing initial padding
        if self._slide_step <= self._slide_steps:
            t = self._slide_step / self._slide_steps
            ease = 1 - (1 - t) ** 2  # ease-out
            offset = int((1 - ease) * 200)
            side = self._bubble_widget.pack_info().get("side", "left")
            if side == "right":
                self._bubble_widget.pack_configure(padx=(offset, 6))
            else:
                self._bubble_widget.pack_configure(padx=(6, offset))
            self._slide_step += 1

        if self._fade_step <= self._fade_steps or self._slide_step <= self._slide_steps:
            self.after(24, self._animate_step)

# ==========================
# Avatar
# ==========================
class AvatarWidget(tk.Canvas):
    def __init__(self, master, size=150):
        super().__init__(master, width=size, height=size, bg=BG_MAIN, highlightthickness=0)
        self.size = size
        self.speaking = False
        self.pulse = 0.0
        self.after(40, self._animate)

    def set_speaking(self, v: bool):
        self.speaking = bool(v)

    def _animate(self):
        self.delete("all")
        cx = cy = self.size // 2
        base_r = self.size * 0.36

        # layered glow rings
        for i in range(6):
            t = i / 5
            col = lerp_color(CYAN_MED, BG_MAIN, 0.35 + 0.65 * t)
            r = base_r + i * 3
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=1)

        # pulse core
        if self.speaking:
            self.pulse += 0.28
            scale = 1 + 0.32 * abs(math.sin(self.pulse))
        else:
            self.pulse += 0.07
            scale = 1 + 0.06 * math.sin(self.pulse)

        core_r = int(self.size * 0.16 * scale)
        for i in range(4):
            t = i / 3
            ccol = lerp_color(CYAN_PRIMARY, CYAN_MED, t)
            rr = int(core_r * (1 - 0.12 * i))
            self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=ccol, width=2 if i == 0 else 1)

        self.after(36, self._animate)

# ==========================
# EKG waveform (glow)
# ==========================
class EKGWidget(tk.Canvas):
    def __init__(self, master, width=420, height=64):
        super().__init__(master, width=width, height=height, bg=BG_MAIN, highlightthickness=0)
        self.width = width
        self.height = height
        self.buffer = [0.0] * (self.width // 4)
        self.tick = 0
        self.level = 0.0
        self.after(36, self._run)

    def update_level(self, lvl):
        try:
            if isinstance(lvl, float) and 0.0 <= lvl <= 1.0:
                self.level = lvl
            else:
                v = float(lvl)
                self.level = max(0.0, min(1.0, v / 100.0))
        except Exception:
            self.level = 0.0

    def _run(self):
        self.tick += 1
        spike = 0.0
        if self.level > 0.35 and (self.tick % 8 == 0):
            spike = 0.8 * self.level
        sample = min(1.0, self.level * 0.9 + spike + 0.06 * math.sin(self.tick * 0.6))
        self.buffer.pop(0)
        self.buffer.append(sample)
        self._draw()
        self.after(36, self._run)

    def _draw(self):
        self.delete("all")
        mid = self.height // 2
        step = self.width / max(1, len(self.buffer))
        pts = []
        x = 0
        for v in self.buffer:
            y = mid - v * (self.height * 0.42)
            pts.append((x, y))
            x += step

        # glow layers
        for i in range(4):
            t = i / 3
            col = lerp_color(CYAN_SOFT, BG_MAIN, 0.6 * t)
            width = 6 - i
            for j in range(len(pts) - 1):
                x1, y1 = pts[j]
                x2, y2 = pts[j + 1]
                self.create_line(x1, y1, x2, y2, fill=col, width=width, smooth=True)

        # core line
        for j in range(len(pts) - 1):
            x1, y1 = pts[j]
            x2, y2 = pts[j + 1]
            self.create_line(x1, y1, x2, y2, fill=CYAN_PRIMARY, width=2, smooth=True)

# ==========================
# Main UI (borderless + slide + glow)
# ==========================
class AssistantUI:
    def __init__(self, root: tk.Tk, on_submit, title="AURIS", on_force_stop=None):
        self.root = root
        self.on_submit = on_submit
        self.on_force_stop = on_force_stop or (lambda: None)

        # remove title bar and initial geometry (slide from top)
        root.overrideredirect(True)
        
        root.configure(bg=BG_MAIN)

        self.w = 390
        self.h = 667
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.final_x = (sw - self.w) // 2
        self.final_y = int(sh * 0.12)
        self.start_y = -self.h - 40
        root.geometry(f"{self.w}x{self.h}+{self.final_x}+{self.start_y}")

        # custom drag
        root.bind("<ButtonPress-1>", self._drag_start)
        root.bind("<B1-Motion>", self._drag_move)

        # build layout
        self._build_layout(title)

        # slide-in animation params
        self._slide_step = 0
        self._slide_steps = 18
        self._slide_in()

    def _build_layout(self, title):
        # outer canvas for glow border
        self.canvas_outer = tk.Canvas(self.root, bg=BG_MAIN, highlightthickness=0)
        self.canvas_outer.pack(fill="both", expand=True)
        self._draw_glow_border()

        pad = 12
        inner = tk.Frame(self.canvas_outer, bg=BG_MAIN)
        inner.place(x=pad, y=pad, width=self.w - pad*2, height=self.h - pad*2)

        # header
        header = tk.Frame(inner, bg=BG_MAIN)
        header.pack(fill="x", pady=(6,4), padx=8)
        tk.Label(header, text=f"● {title}", fg=CYAN_PRIMARY, bg=BG_MAIN,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="Idle")
        tk.Label(header, textvariable=self.status_var, fg=CYAN_MED, bg=BG_MAIN,
                 font=("Segoe UI", 10)).pack(side="right")
        tk.Button(header, text="✖", bg="#5A1A1A", fg="white", relief="flat", command=self.root.destroy).pack(side="right", padx=6)

        # avatar
        self.avatar = AvatarWidget(inner, size=160)
        self.avatar.pack(pady=(4,6))

        # chat area
        wrapper = tk.Frame(inner, bg=BG_MAIN)
        wrapper.pack(fill="both", expand=True, padx=8, pady=(4,6))

        self.canvas = tk.Canvas(wrapper, bg=BG_MAIN, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(wrapper, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.msg_container = tk.Frame(self.canvas, bg=BG_MAIN)
        self.msg_window = self.canvas.create_window((0,0), window=self.msg_container, anchor="nw")

        # Auto-resize chat width
        self.canvas.bind("<Configure>",
                        lambda e: self.canvas.itemconfig(self.msg_window, width=e.width))

        self.msg_container.configure(padx=6)

        self.msg_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # EKG mic widget
        self.ekg = EKGWidget(inner, width=self.w - 64, height=68)
        self.ekg.pack(pady=(6,8))

        # input row
        input_row = tk.Frame(inner, bg=BG_MAIN)
        input_row.pack(fill="x", padx=8, pady=(4,10))

        self.entry = tk.Entry(input_row, bg="#001A2C", fg="white", relief="flat", insertbackground="white",
                              font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))
        self.entry.bind("<Return>", lambda e: self._submit())

        tk.Button(input_row, text="Send", bg=CYAN_PRIMARY, fg="black", relief="flat",
                  font=("Segoe UI", 10, "bold"), command=self._submit).pack(side="left", ipadx=12, ipady=6)
        tk.Button(input_row, text="✖", bg="#7A2222", fg="white", relief="flat", command=self._force_stop).pack(side="left", padx=(8,0), ipadx=6, ipady=6)

    def _draw_glow_border(self):
        self.canvas_outer.delete("all")
        pads = 12
        layers = 8
        for i in range(layers):
            t = i / (layers - 1)
            col = lerp_color(CYAN_PRIMARY, BG_MAIN, 0.55 + 0.45 * t)
            offset = i * 2
            x1 = pads - offset
            y1 = pads - offset
            x2 = self.w - pads + offset
            y2 = self.h - pads + offset
            # simple rectangle outline (no joinstyle)
            self.canvas_outer.create_rectangle(x1, y1, x2, y2, outline=col)

    def _slide_in(self):
        self._slide_step += 1
        t = self._slide_step / self._slide_steps
        ease = 1 - (1 - t) ** 3
        y = int(self.start_y + (self.final_y - self.start_y) * ease)
        self.root.geometry(f"{self.w}x{self.h}+{self.final_x}+{y}")
        if self._slide_step < self._slide_steps:
            self.root.after(16, self._slide_in)
        else:
            self.root.geometry(f"{self.w}x{self.h}+{self.final_x}+{self.final_y}")

    # ========================
    # Public API (compatible)
    # ========================
    def append(self, text, is_torque=False, is_system=False):
        sender = "system" if is_system else ("torque" if is_torque else "user")
        b = ChatBubble(self.msg_container, text, sender, bounce=True, icon_robot_style=1, icon_user_style='B')
        b.pack(fill="x")
        self.root.after(30, lambda: self.canvas.yview_moveto(1.0))

    def set_status(self, txt):
        try:
            self.status_var.set(txt)
        except Exception:
            pass

    def set_listening(self, v: bool):
        # for compatibility; show status briefly
        self.set_status("● Listening" if v else "● Idle")

    def set_speaking(self, v: bool):
        self.avatar.set_speaking(bool(v))
        if v:
            self.set_status("● Speaking")
        else:
            self.set_status("● Idle")

    def set_caption(self, text: str):
        # compatibility placeholder (no caption UI)
        pass

    def update_mic_level(self, level):
        try:
            if isinstance(level, float) and 0.0 <= level <= 1.0:
                lvl = level
            else:
                lvl = float(level) / 100.0
            lvl = max(0.0, min(1.0, lvl))
        except Exception:
            lvl = 0.0
        self.ekg.update_level(lvl)

    # ========================
    # Input handlers
    # ========================
    def _submit(self):
        t = self.entry.get().strip()
        if not t:
            return
        self.append(t, is_torque=False)
        self.entry.delete(0, "end")
        try:
            self.on_submit(t)
        except Exception as e:
            self.append(f"[Error] {e}", is_system=True)

    def _force_stop(self):
        self.append("Force stopping session.", is_system=True)
        try:
            self.on_force_stop()
        except Exception as e:
            self.append(str(e), is_system=True)

    # ========================
    # Window dragging
    # ========================
    def _drag_start(self, event):
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event):
        if not hasattr(self, "_drag_offset") or self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")
