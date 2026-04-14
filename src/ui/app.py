# src/ui/app.py  — AURIS UI v6  (Reference Match Build)
import math
import tkinter as tk

# ── Design Tokens (Reference Image Match) ─────────────────────────────────────
BG_MAIN        = "#004163"
BG_BUBBLE      = "#002238"
CYAN_PRIMARY   = "#00EEFF"
CYAN_DIM       = "#008899"
TEXT_WHITE     = "#FFFFFF"
BTN_RED        = "#7A2222"
BTN_CYAN       = "#00E3FF"

# ── Helpers ───────────────────────────────────────────────────────────────────
def lerp_color(hex_a, hex_b, t):
    try:
        a = int(hex_a.lstrip("#"), 16)
        b = int(hex_b.lstrip("#"), 16)
        ar, ag, ab_ = (a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF
        br, bg, bb  = (b >> 16) & 0xFF, (b >> 8) & 0xFF, b & 0xFF
        return (f"#{int(ar+(br-ar)*t):02x}"
                f"{int(ag+(bg-ag)*t):02x}"
                f"{int(ab_+(bb-ab_)*t):02x}")
    except: return hex_a

# ── Match Style Chat Bubble ───────────────────────────────────────────────────
class ChatBubble(tk.Frame):
    def __init__(self, master, text, sender="user", wrap=260):
        super().__init__(master, bg=BG_MAIN)
        
        self.row = tk.Frame(self, bg=BG_MAIN)
        self.row.pack(fill="x", pady=6, padx=12)

        if sender == "torque":
            # Robot icon on the left
            self._make_icon(self.row, "robot").pack(side="left", anchor="n", padx=(0, 8))
            bubble = tk.Frame(self.row, bg=BG_BUBBLE, padx=12, pady=10)
            bubble.pack(side="left", padx=(0, 40))
        elif sender == "user":
            # User icon on the right
            self._make_icon(self.row, "user").pack(side="right", anchor="n", padx=(8, 0))
            bubble = tk.Frame(self.row, bg=BG_BUBBLE, padx=12, pady=10)
            bubble.pack(side="right", padx=(40, 0))
        else:
            bubble = tk.Frame(self.row, bg=BG_MAIN, padx=12, pady=4)
            bubble.pack(side="left")

        self.lbl = tk.Label(
            bubble, text=text, bg=bubble.cget("bg"), fg=BG_MAIN, # Start invisible
            font=("Segoe UI", 10), wraplength=wrap, justify="left"
        )
        self.lbl.pack()

        self._fade_val = 0
        self.after(10, self._fade_in)

    def _make_icon(self, parent, kind):
        c = tk.Canvas(parent, width=32, height=32, bg=BG_MAIN, highlightthickness=0)
        if kind == "robot":
            # Robot Icon from Image
            c.create_rectangle(6, 10, 26, 24, outline=CYAN_PRIMARY, width=2)
            c.create_line(10, 16, 14, 16, fill=CYAN_PRIMARY, width=2)
            c.create_line(18, 16, 22, 16, fill=CYAN_PRIMARY, width=2)
            c.create_line(16, 10, 16, 6,  fill=CYAN_PRIMARY, width=1)
            c.create_oval(14, 4, 18, 8,   outline=CYAN_PRIMARY)
        else:
            # User Icon from Image
            c.create_oval(10, 4, 22, 16, fill=BG_BUBBLE, outline=BG_BUBBLE)
            c.create_arc(4, 16, 28, 32, start=0, extent=180, fill=BG_BUBBLE)
        return c

    def update_wraplength(self, canvas_w):
        try:
            new_wrap = max(140, int(canvas_w * 0.58))
            self.lbl.configure(wraplength=new_wrap)
        except: pass

    def _fade_in(self):
        if self._fade_val <= 10:
            target = TEXT_WHITE if self.lbl.master.cget("bg") == BG_BUBBLE else CYAN_PRIMARY
            col = lerp_color(BG_MAIN, target, self._fade_val / 10)
            try: self.lbl.configure(fg=col)
            except: pass
            self._fade_val += 1
            self.after(20, self._fade_in)
        else:
            final_col = TEXT_WHITE if self.lbl.master.cget("bg") == BG_BUBBLE else CYAN_PRIMARY
            try: self.lbl.configure(fg=final_col)
            except: pass

# ── Multi-Ring Avatar ──────────────────────────────────────────────────────────
class AvatarWidget(tk.Canvas):
    def __init__(self, master, size=110):
        super().__init__(master, width=size, height=size, bg=BG_MAIN, highlightthickness=0)
        self.view_size = size
        self.speaking = False
        self.pulse = 0.0
        self.after(40, self._tick)

    def set_speaking(self, v):
        self.speaking = bool(v)

    def _tick(self):
        try:
            self.delete("all")
            cx = cy = self.view_size // 2
            self.pulse += 0.15 if self.speaking else 0.06
            
            # 5-Layer Concentric Rings
            for i in range(5):
                alpha = 0.9 - (i * 0.18)
                col = lerp_color(BG_MAIN, CYAN_PRIMARY, alpha)
                amp = (0.22 if self.speaking else 0.04) * math.sin(self.pulse + i*0.4)
                r = (self.view_size * 0.15) + (i * 6) + (self.view_size * amp)
                self.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=1)
            
            # Double Core
            self.create_oval(cx-4, cy-4, cx+4, cy+4, fill=CYAN_PRIMARY, outline="")
            self.create_oval(cx-8, cy-8, cx+8, cy+8, outline=CYAN_PRIMARY, width=1)
            
            self.after(36, self._tick)
        except: pass

# ── Layered EKG Wave ───────────────────────────────────────────────────────────
class EKGWidget(tk.Canvas):
    def __init__(self, master, height=48):
        super().__init__(master, height=height, bg=BG_MAIN, highlightthickness=0)
        self.current_w = 400
        self.view_height = height
        self.buf = [0.0] * 64
        self.tick = 0
        self.level = 0.0
        self.bind("<Configure>", self._on_configure)
        self.after(36, self._run)

    def _on_configure(self, event):
        self.current_w = max(event.width, 10)
        new_len = max(20, self.current_w // 6)
        if len(self.buf) != new_len:
            self.buf = [0.0] * new_len

    def update_level(self, lvl):
        try: self.level = max(0.0, min(1.0, float(lvl) / 100.0 if float(lvl) > 1.0 else float(lvl)))
        except: self.level = 0.0

    def _run(self):
        try:
            self.tick += 1
            spike = 0.8 * self.level if (self.level > 0.35 and self.tick % 7 == 0) else 0.0
            val = min(1.0, self.level * 0.7 + spike + 0.08 * math.sin(self.tick * 0.6))
            self.buf.pop(0)
            self.buf.append(max(0.0, val))
            self._draw()
            self.after(32, self._run)
        except: pass

    def _draw(self):
        w, h = self.current_w, self.view_height
        if w < 20 or len(self.buf) < 2: return
        self.delete("all")
        mid = h // 2
        step = w / len(self.buf)
        pts = [(i * step, mid - v * (h * 0.42)) for i, v in enumerate(self.buf)]
        
        # 3 Layers of Blue
        for i in range(3):
            col = lerp_color(BG_MAIN, CYAN_PRIMARY, 0.4 - i*0.1)
            self.create_line(pts, fill=col, width=5-i*2, smooth=True)
        self.create_line(pts, fill=CYAN_PRIMARY, width=1, smooth=True)

# ── Main UI v6 ─────────────────────────────────────────────────────────────────
class AssistantUI:
    def __init__(self, root: tk.Tk, on_submit, title="AURIS", on_force_stop=None):
        self.root          = root
        self._on_submit_cb = on_submit
        self._on_stop_cb   = on_force_stop or (lambda: None)
        self._drag_offset  = None
        self._bubbles      = []
        self._placeholder  = "Type command..."
        self._ph_color     = CYAN_DIM

        root.title(title)
        root.configure(bg=BG_MAIN)
        root.resizable(True, True)
        root.minsize(360, 560)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w0, h0 = 420, 720
        root.geometry(f"{w0}x{h0}+{(sw-w0)//2}+{int(sh*0.08)}")

        self.main_container = tk.Frame(self.root, bg=BG_MAIN)
        self.main_container.pack(fill="both", expand=True)

        self._build_layout(title)
        self._set_input_state("disabled")

    def _build_layout(self, title):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.main_container, bg=BG_MAIN, pady=15, padx=15)
        hdr.pack(side="top", fill="x")

        # Blue dot
        self._dot = tk.Canvas(hdr, width=14, height=14, bg=BG_MAIN, highlightthickness=0)
        self._dot.pack(side="left", padx=(0, 10))
        self._dot_id = self._dot.create_oval(2, 2, 12, 12, fill=CYAN_PRIMARY, outline="")

        tk.Label(hdr, text=title.upper(), fg=CYAN_PRIMARY, bg=BG_MAIN,
                 font=("Segoe UI", 20, "bold")).pack(side="left")

        self.status_var = tk.StringVar(value="● Listening")
        tk.Label(hdr, textvariable=self.status_var, fg=CYAN_PRIMARY, bg=BG_MAIN,
                 font=("Segoe UI", 12)).pack(side="right", padx=(0, 20))

        # Close button X
        btn_close = tk.Button(hdr, text="✕", bg=BTN_RED, fg="white", relief="flat",
                              font=("Segoe UI", 12, "bold"), command=self.root.destroy, padx=10)
        btn_close.pack(side="right")

        hdr.bind("<ButtonPress-1>", self._drag_start)
        hdr.bind("<B1-Motion>",     self._drag_move)

        # ── Middle ────────────────────────────────────────────────────────────
        self.avatar = AvatarWidget(self.main_container, size=110)
        self.avatar.pack(side="top", pady=15)

        chat_wrap = tk.Frame(self.main_container, bg=BG_MAIN)
        chat_wrap.pack(side="top", fill="both", expand=True, padx=10)

        self.canvas = tk.Canvas(chat_wrap, bg=BG_MAIN, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(chat_wrap, orient="vertical", command=self.canvas.yview, width=4)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.msg_container = tk.Frame(self.canvas, bg=BG_MAIN)
        self._msg_win = self.canvas.create_window((0, 0), window=self.msg_container, anchor="nw")

        self.canvas.bind("<Configure>", self._on_chat_resize)
        self.msg_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # ── Footer ────────────────────────────────────────────────────────────
        footer = tk.Frame(self.main_container, bg=BG_MAIN, padx=15, pady=15)
        footer.pack(side="bottom", fill="x")

        self.ekg = EKGWidget(footer, height=44)
        self.ekg.pack(side="top", fill="x", pady=(0, 15))

        inp_row = tk.Frame(footer, bg=BG_MAIN)
        inp_row.pack(side="top", fill="x")

        self.entry = tk.Entry(inp_row, bg="#001828", fg="white", relief="flat",
                              insertbackground="white", font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True, ipady=12, padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self._submit())
        self.entry.bind("<FocusIn>", self._ph_in)
        self.entry.bind("<FocusOut>", self._ph_out)
        self.entry.insert(0, self._placeholder)
        self.entry.config(fg=self._ph_color)

        self.send_btn = tk.Button(inp_row, text="Send", bg=BTN_CYAN, fg="black",
                                  font=("Segoe UI", 11, "bold"), relief="flat",
                                  padx=20, pady=8, command=self._submit)
        self.send_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = tk.Button(inp_row, text="✕", bg=BTN_RED, fg="white",
                                  font=("Segoe UI", 12, "bold"), relief="flat",
                                  padx=15, pady=8, command=self._force_stop)
        self.stop_btn.pack(side="left")

    def _on_chat_resize(self, event):
        self.canvas.itemconfig(self._msg_win, width=event.width)
        for b in self._bubbles:
            try: b.update_wraplength(event.width)
            except: pass

    def _drag_start(self, event):
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event):
        if self._drag_offset:
            self.root.geometry(f"+{event.x_root - self._drag_offset[0]}+{event.y_root - self._drag_offset[1]}")

    # ── API ─────────────────────────────────────────────────────────────────────
    def append(self, text, is_torque=False, is_system=False):
        def _do():
            sender = "system" if is_system else "torque" if is_torque else "user"
            cw = max(200, self.canvas.winfo_width())
            b = ChatBubble(self.msg_container, text, sender, wrap=int(cw*0.58))
            b.pack(fill="x")
            self._bubbles.append(b)
            if len(self._bubbles) > 100: self._bubbles.pop(0).destroy()
            self.canvas.after(50, lambda: self.canvas.yview_moveto(1.0))
        self.root.after(0, _do)

    def set_status(self, txt):
        self.root.after(0, lambda: self.status_var.set(f"● {txt}"))

    def set_listening(self, v: bool):
        def _do():
            self._dot.itemconfig(self._dot_id, fill=CYAN_PRIMARY if v else CYAN_DIM)
            self.status_var.set("● Listening" if v else "● Idle")
        self.root.after(0, _do)

    def set_speaking(self, v: bool):
        def _do():
            self.avatar.set_speaking(v)
            self.status_var.set("● Speaking" if v else "● Idle")
        self.root.after(0, _do)

    def update_mic_level(self, level):
        self.root.after(0, lambda: self.ekg.update_level(level))

    def set_text_input_locked(self, locked: bool, hint: str = None):
        def _do():
            self._set_input_state("disabled" if locked else "normal")
        self.root.after(0, _do)

    def _set_input_state(self, state: str):
        try:
            self.entry.configure(state=state)
            if state == "disabled":
                self.entry.configure(bg="#001018", fg=CYAN_DIM)
                self.send_btn.configure(state="disabled", bg="#002238")
            else:
                self.entry.configure(bg="#001828", fg="white")
                self.send_btn.configure(state="normal", bg=BTN_CYAN)
        except: pass

    def _ph_in(self, _):
        if self.entry.get() == self._placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg="white")

    def _ph_out(self, _):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.config(fg=self._ph_color)

    def _submit(self):
        t = self.entry.get().strip()
        if not t or t == self._placeholder: return
        self.append(t, is_torque=False)
        self.entry.delete(0, "end")
        import threading
        threading.Thread(target=lambda: self._on_submit_cb(t), daemon=True).start()

    def _force_stop(self):
        try: self._on_stop_cb()
        except: pass
