# src/voice_auth/enroll_ui.py
import os
import time
from pathlib import Path
from typing import Optional, List
import tkinter as tk
from tkinter import ttk
import soundfile as sf
from .recorder import record_seconds
from .svm_auth import enroll_svm, SR

class _EnrollWindow:
    def __init__(self, samples_count=10, sample_seconds=3.0, sample_rate=16000,
                 device_index=None, model_path="voice_auth_svm.joblib", speak_fn=None):
        self.samples_count = int(samples_count)
        self.sample_seconds = float(sample_seconds)
        self.sample_rate = int(sample_rate)
        self.device_index = device_index
        self.model_path = model_path
        self.speak_fn = speak_fn or (lambda _t: None)
        
        self.phrases = [
            '"Hey Torque, what time is it?"',
            '"Hey Torque, check the weather."',
            '"Hey Torque, open the browser."',
            '"Hey Torque, close all apps."',
            '"Hey Torque, tell me a joke."'
        ]

        self.tmpdir = Path(".voice_enroll_tmp")
        self.tmpdir.mkdir(exist_ok=True)

        self.root = tk.Tk()
        self.root.title("AURIS – MFCC-SVM Voice Match Setup")
        self.root.geometry("560x340")
        self.root.resizable(False, False)

        # ---------------- DARK THEME CONFIGURATION ----------------
        bg_col = "#121212"
        fg_col = "#E0E0E0"
        accent = "#00B4D8"
        btn_bg = "#1E1E1E"

        self.root.configure(bg=bg_col)
        
        style = ttk.Style(self.root)
        style.theme_use('clam')
        
        style.configure("TFrame", background=bg_col)
        style.configure("TLabel", background=bg_col, foreground=fg_col)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=accent)
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#A0A0A0")
        style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"), foreground="#FFFFFF")
        style.configure("Phrase.TLabel", font=("Segoe UI", 16, "italic"), foreground="#FFD700")
        style.configure("Condition.TLabel", font=("Segoe UI", 11, "bold"), foreground="#FF6060")
        
        style.configure("TButton", font=("Segoe UI", 11), background=btn_bg, foreground=fg_col,
                        borderwidth=0, focuscolor=accent, lightcolor=bg_col, darkcolor=bg_col)
        style.map("TButton", background=[("active", "#2A2A2A"), ("disabled", "#121212")],
                  foreground=[("disabled", "#555555")])
        style.configure("Horizontal.TProgressbar", background=accent, troughcolor=btn_bg, 
                        bordercolor=bg_col, lightcolor=accent, darkcolor=accent)

        # ---------------- BUILD UI ----------------
        main_frame = ttk.Frame(self.root, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Secure MFCC-SVM Enrollment", style="Header.TLabel").pack(pady=(0, 5))

        self.info = ttk.Label(main_frame,
            text=(f"We will capture {self.samples_count} vocal profiles across varied noise conditions.\n"
                  f"Please read the phrases aloud when prompted."),
            justify="center", style="Sub.TLabel")
        self.info.pack(pady=(0, 5))

        self.condition_display = ttk.Label(main_frame, text="Condition: Loading...", style="Condition.TLabel")
        self.condition_display.pack(pady=(0, 5))

        self.phrase_display = ttk.Label(main_frame, text="", style="Phrase.TLabel")
        self.phrase_display.pack(pady=(5, 5))

        self.status = ttk.Label(main_frame, text="Click Start to begin calibration.", style="Status.TLabel")
        self.status.pack(pady=(5, 10))

        self.progress = ttk.Progressbar(main_frame, orient="horizontal",
                                        length=500, mode="determinate", maximum=self.samples_count)
        self.progress.pack(pady=(0, 15))

        btns = ttk.Frame(main_frame)
        btns.pack()
        
        self.start_btn = ttk.Button(btns, text=" START ENROLLMENT ", command=self._start)
        self.start_btn.pack(side="left", padx=10, ipadx=10, ipady=4)
        
        self.cancel_btn = ttk.Button(btns, text=" CANCEL ", command=self._cancel)
        self.cancel_btn.pack(side="left", padx=10, ipadx=10, ipady=4)

        self._canceled = False
        self._done = False
        self._wavs: List[str] = []
        self.idx = 1
        
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)

    def run(self):
        self.root.mainloop()
        return self._done

    def _say(self, text: str):
        try: self.speak_fn(text)
        except Exception: pass

    def _cancel(self):
        self._canceled = True
        try: self.root.destroy()
        except Exception: pass

    def _set_status(self, text: str):
        self.status.config(text=str(text or ""))
        self.root.update_idletasks()

    def _set_phrase(self, text: str):
        self.phrase_display.config(text=str(text or ""))
        self.root.update_idletasks()
        
    def _set_condition(self, text: str):
        self.condition_display.config(text=str(text or ""))
        self.root.update_idletasks()

    def _start(self):
        self.start_btn.config(state="disabled")
        self._say(f"Starting MFCC-SVM enrollment for {self.samples_count} samples.")
        self.root.after(50, self._step_recording)

    def _step_recording(self):
        if self._canceled: return
        if self.idx > self.samples_count:
            self._finish_enrollment()
            return
            
        quiet_max = max(1, int(self.samples_count * 0.4))
        mod_max = quiet_max + max(1, int(self.samples_count * 0.4))
        
        condition = "Quiet office"
        pause_needed = False
        
        if self.idx <= quiet_max:
            condition = "[ Environment: Quiet Room ]"
        elif self.idx <= mod_max:
            condition = "[ Environment: Moderate Background Noise (e.g. TV / Music) ]"
            if self.idx == quiet_max + 1 and not getattr(self, "_paused_for_mod", False):
                self._paused_for_mod = True
                pause_needed = True
        else:
            condition = "[ Environment: Loud Background Noise (e.g. Traffic / Cafe) ]"
            if self.idx == mod_max + 1 and not getattr(self, "_paused_for_loud", False):
                self._paused_for_loud = True
                pause_needed = True
                
        self._set_condition(condition)
                
        if pause_needed:
            msg = "Please change environment and click RESUME."
            self._set_status(msg)
            self._say(msg)
            self._set_phrase("(Waiting...)")
            self.cancel_btn.config(text=" RESUME ", command=self._resume_recording)
            return

        phrase_to_read = self.phrases[(self.idx - 1) % len(self.phrases)]
        
        self._set_phrase("...")
        self._set_status(f"Sample {self.idx}/{self.samples_count} starting in 1 sec…")
        self._countdown(1.0)
        if self._canceled: return
        
        self._set_phrase(phrase_to_read)
        self._set_status(f"Recording sample {self.idx}… Speak now.")
        y = record_seconds(self.sample_seconds, device_index=self.device_index)
        wav_path = (self.tmpdir / f"enroll_{self.idx}.wav").as_posix()
        sf.write(wav_path, y, SR)
        self._wavs.append(wav_path)
        self.progress["value"] = self.idx
        self._set_status(f"Captured sample {self.idx}.")
        time.sleep(0.3)
        
        self.idx += 1
        self.root.after(50, self._step_recording)

    def _resume_recording(self):
        self.cancel_btn.config(text=" CANCEL ", command=self._cancel)
        self.root.after(50, self._step_recording)
        
    def _finish_enrollment(self):
        self._set_status("Training MFCC-SVM Model (This may take a moment)…")
        self.root.update_idletasks()
        try:
            enroll_svm(self._wavs, self.model_path)
            self._set_status("Enrollment complete. MFCC-SVM ready.")
            self._say("Enrollment complete.")
            self._done = True
        except Exception as e:
            self._set_status(f"Enrollment failed: {e}")
            self._say("Enrollment failed.")
        self.root.after(1500, self._cancel)

    def _countdown(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end and not self._canceled:
            rem = max(0, end - time.time())
            self._set_status(f"Recording starts in {rem:.1f} s…")
            time.sleep(0.05)


def run_enrollment(model_path="voice_auth_svm.joblib", samples_count=10,
                   sample_seconds=3.0, device_index=None, speak_fn=None):
    win = _EnrollWindow(samples_count, sample_seconds, device_index=device_index,
                        model_path=model_path, speak_fn=speak_fn)
    return True if win.run() else None
