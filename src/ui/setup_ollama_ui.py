# src/ui/setup_ollama_ui.py
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import sys
import os
from pathlib import Path
import subprocess

# We reuse the logic from the old installer
import ollama_installer as ol

class _OllamaSetupWindow:
    def __init__(self):
        self.root = tb.Toplevel(title="AURIS – AI Brain Setup")
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        main_frame = tb.Frame(self.root, padding=25)
        main_frame.pack(fill=BOTH, expand=True)

        tb.Label(main_frame, text="Setting up Local AI Model", font=("Segoe UI", 20, "bold"), bootstyle="info").pack(pady=(0, 5))
        
        self.desc = tb.Label(main_frame, text="Checking system hardware...", font=("Segoe UI", 11), bootstyle="secondary", justify="center")
        self.desc.pack(pady=(5, 15))

        self.status = tb.Label(main_frame, text="Initializing...", font=("Segoe UI", 14, "bold"), bootstyle="warning")
        self.status.pack(pady=(15, 10))

        self.progress = tb.Progressbar(main_frame, bootstyle="info-striped", mode="indeterminate")
        self.progress.pack(fill=X, pady=15, padx=20)

        btns = tb.Frame(main_frame)
        btns.pack(pady=10)

        self.skip_btn = tb.Button(btns, text=" Skip / Not Now ", bootstyle="danger-outline", command=self._skip)
        self.skip_btn.pack(side=LEFT, padx=10)

        self._done = False
        self._canceled = False
        self.root.protocol("WM_DELETE_WINDOW", self._skip)

    def run(self):
        # Start installation loop in background to not freeze GUI
        threading.Thread(target=self._install_thread, daemon=True).start()
        self.root.wait_window()
        return self._done

    def _skip(self):
        self._canceled = True
        try: 
            self.root.destroy()
        except Exception: pass

    def _set_status(self, text, style="warning"):
        try:
            self.status.config(text=text, bootstyle=style)
            self.root.update_idletasks()
        except: pass

    def _set_desc(self, text):
        try:
            self.desc.config(text=text)
            self.root.update_idletasks()
        except: pass

    def _install_thread(self):
        try:
            self.progress.start(10)
            
            # Step 1: Detect Hardware
            hw = ol.detect_hardware()
            model = ol.select_model(hw)
            
            self._set_desc(f"Hardware match: {hw['ram_gb']}GB RAM detected.\nSelected highly optimized model: {model}.")
            
            ol.write_env_key("OLLAMA_MODEL", model)
            ol.write_env_key("OLLAMA_HOST", "http://127.0.0.1:11434")

            # Step 2: Install Ollama if missing
            self._set_status("Checking Ollama installation...", "warning")
            if not ol.ensure_ollama_installed(cancel_check=lambda: self._canceled):
                if self._canceled: return
                self._set_status("Failed to install Ollama.", "danger")
                return

            if self._canceled: return
            self._set_status("Starting AI Engine...", "info")
            ol.start_ollama_service()
            import time
            time.sleep(3)

            # Step 3: Pull model
            self._set_status(f"Downloading Model...\nThis will take 2-15 minutes.", "primary")
            self.progress.stop()
            self.progress.config(mode="indeterminate")
            self.progress.start(15)

            if not self._canceled:
                success = ol.pull_model(model)
                if not success:
                    self._set_status("Retrying model download...", "warning")
                    time.sleep(3)
                    success = ol.pull_model(model)

                if success:
                    self._set_status("SUCCESS! Local AI is ready.", "success")
                    self._done = True
                    self.progress.stop()
                    self.progress["value"] = 100
                    time.sleep(2)
                    try: self.root.destroy()
                    except: pass
                else:
                    self._set_status("Failed to download AI model.", "danger")
                    self.progress.stop()

        except Exception as e:
            self._set_status(f"Error: {str(e)[:30]}", "danger")


def run_ollama_setup_ui():
    win = _OllamaSetupWindow()
    return win.run()
