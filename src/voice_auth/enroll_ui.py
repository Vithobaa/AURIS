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
    def __init__(self, samples_count=5, sample_seconds=2.0, sample_rate=16000,
                 device_index=None, model_path="voice_auth_svm.joblib", speak_fn=None):
        self.samples_count = int(samples_count)
        self.sample_seconds = float(sample_seconds)
        self.sample_rate = int(sample_rate)
        self.device_index = device_index
        self.model_path = model_path
        self.speak_fn = speak_fn or (lambda _t: None)

        self.tmpdir = Path(".voice_enroll_tmp")
        self.tmpdir.mkdir(exist_ok=True)

        self.root = tk.Tk()
        self.root.title("Torque – Voice Enrollment (SVM)")
        self.root.geometry("520x300")
        self.root.resizable(False, False)

        pad = {"padx": 14, "pady": 10}
        ttk.Label(self.root, text="Voice Enrollment", font=("Segoe UI", 16, "bold")).pack(**pad)

        self.info = ttk.Label(self.root,
            text=(f"We will record {self.samples_count} samples.\n"
                  f"Speak naturally when prompted. Each is ~{self.sample_seconds:.1f}s."),
            justify="center")
        self.info.pack(pady=(0, 6))

        self.status = ttk.Label(self.root, text="Click Start to begin.", font=("Segoe UI", 11))
        self.status.pack(pady=(6, 8))

        self.progress = ttk.Progressbar(self.root, orient="horizontal",
                                        length=440, mode="determinate", maximum=self.samples_count)
        self.progress.pack(pady=(0, 10))

        btns = ttk.Frame(self.root); btns.pack(pady=(4, 10))
        self.start_btn = ttk.Button(btns, text="Start", command=self._start)
        self.start_btn.pack(side="left", padx=6)
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self._cancel)
        self.cancel_btn.pack(side="left", padx=6)

        self._canceled = False
        self._done = False
        self._wavs: List[str] = []

        self.root.protocol("WM_DELETE_WINDOW", self._cancel)

    def run(self):
        self.root.mainloop()
        return self._done

    def _say(self, text: str):
        try:
            self.speak_fn(text)
        except Exception:
            pass

    def _cancel(self):
        self._canceled = True
        try: self.root.destroy()
        except Exception: pass

    def _set_status(self, text: str):
        self.status.config(text=str(text or ""))
        self.root.update_idletasks()

    def _start(self):
        self.start_btn.config(state="disabled")
        self._say("Starting voice enrollment.")
        self.root.after(50, self._record_loop)

    def _record_loop(self):
        for i in range(self.samples_count):
            if self._canceled: return
            idx = i + 1
            self._set_status(f"Sample {idx} of {self.samples_count} starts in 1 sec…")
            self._say(f"Sample {idx}. Get ready.")
            self._countdown(1.0)
            if self._canceled: return
            self._set_status(f"Recording sample {idx}… Speak now.")
            y = record_seconds(self.sample_seconds, device_index=self.device_index)
            wav_path = (self.tmpdir / f"enroll_{idx}.wav").as_posix()
            sf.write(wav_path, y, SR)
            self._wavs.append(wav_path)
            self.progress["value"] = idx
            self._set_status(f"Captured sample {idx}.")
            self._say("Captured.")
            time.sleep(0.4)

        self._set_status("Training SVM model…")
        try:
            enroll_svm(self._wavs, self.model_path)
            self._set_status("Enrollment complete.")
            self._say("Enrollment complete.")
            self._done = True
        except Exception as e:
            self._set_status(f"Enrollment failed: {e}")
            self._say("Enrollment failed.")
        self.root.after(900, self._cancel)

    def _countdown(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end and not self._canceled:
            rem = max(0, end - time.time())
            self._set_status(f"Recording starts in {rem:.1f} s…")
            time.sleep(0.05)


def run_enrollment(model_path="voice_auth_svm.joblib", samples_count=5,
                   sample_seconds=2.0, device_index=None, speak_fn=None):
    win = _EnrollWindow(samples_count, sample_seconds, device_index=device_index,
                        model_path=model_path, speak_fn=speak_fn)
    return True if win.run() else None
