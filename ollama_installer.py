import os
import sys
import subprocess
import platform
import shutil
import time
from pathlib import Path
import psutil  # pip install psutil

# -----------------------------
# ENV File Management
# -----------------------------
ENV_PATH = Path(".env")

def write_env_key(key: str, value: str):
    data = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    data[k] = v
    data[key] = str(value)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")


# -----------------------------
# Detect hardware
# -----------------------------
def detect_hardware():
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    cores = psutil.cpu_count(logical=True)
    return {"ram_gb": ram_gb, "cores": cores}


# -----------------------------
# Choose correct model
# -----------------------------
def select_model(hw):
    ram = hw["ram_gb"]

    if ram < 8:
        return "llama3.2:1b-instruct-q4_0"

    if ram < 16:
        return "qwen2.5:3b-instruct-q4_K_M"

    if ram < 32:
        return "qwen2.5:7b-instruct-q5_K_M"

    return "qwen2.5:14b-instruct-q4_K_M"


# -----------------------------
# Ensure Ollama installed
# -----------------------------
def ensure_ollama_installed():
    try:
        subprocess.check_output("ollama --version", shell=True)
        print("[Installer] Ollama is already installed.")
        return True
    except Exception:
        pass

    print("[Installer] Ollama not found. Installing...")

    if platform.system().lower() == "windows":
        url = "https://ollama.com/download/OllamaSetup.exe"
        exe_path = Path("OllamaSetup.exe")

        print("[Installer] Downloading Ollama installer...")
        import requests
        r = requests.get(url)
        exe_path.write_bytes(r.content)

        print("[Installer] Running installer...")
        subprocess.call(f'"{exe_path}" /quiet', shell=True)

        time.sleep(5)
        return True

    print("[Installer] Unsupported OS for automatic install.")
    return False


# -----------------------------
# Start Ollama service
# -----------------------------
def start_ollama_service():
    try:
        subprocess.call("ollama serve --detach", shell=True)
    except:
        pass


# -----------------------------
# Pull model using Ollama
# -----------------------------
def pull_model(model: str):
    print(f"[Installer] Pulling model: {model} ...")

    try:
        p = subprocess.Popen(
            f"ollama pull {model}",
            shell=True,
        )
        p.wait()
        if p.returncode == 0:
            print("[Installer] Model pulled successfully.")
            return True
    except Exception as e:
        print("[Installer] Pull failed:", e)

    return False


# -----------------------------
# Main installer logic
# -----------------------------
def run_installer():
    print("========== OLLAMA INSTALLER ==========")

    hw = detect_hardware()
    print(f"[Installer] Hardware detected: {hw}")

    model = select_model(hw)
    print(f"[Installer] Selected model: {model}")

    write_env_key("OLLAMA_MODEL", model)
    write_env_key("OLLAMA_HOST", "http://127.0.0.1:11434")

    if not ensure_ollama_installed():
        print("[Installer] Ollama installation failed.")
        sys.exit(1)

    print("[Installer] Starting Ollama service...")
    start_ollama_service()
    time.sleep(3)

    print("[Installer] Pulling model...")
    if not pull_model(model):
        print("[Installer] Model pull failed. Trying again in 3 sec...")
        time.sleep(3)
        if not pull_model(model):
            print("[Installer] ERROR: Could not install model.")
            sys.exit(1)

    print("\n[Installer] SUCCESS! Ollama model installed and ready.")
    print("[Installer] You may now run: python -m src.main")


if __name__ == "__main__":
    run_installer()
