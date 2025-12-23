# installer.py
import sys
import os
import shutil
import zipfile
import tempfile
import multiprocessing
from pathlib import Path

try:
    import requests
except Exception:
    print("Please install requests: pip install requests")
    raise


# -----------------------------
# Detect Hardware
# -----------------------------
def detect_hardware():
    import platform

    # RAM in GB
    try:
        import psutil
        ram_gb = int(psutil.virtual_memory().total / (1024**3))
    except Exception:
        ram_gb = 4  # fallback

    cores = multiprocessing.cpu_count()

    # CPU flags (for AVX2)
    try:
        import cpuinfo
        flags = cpuinfo.get_cpu_info().get("flags", [])
        avx2 = "avx2" in flags
    except Exception:
        avx2 = False

    return {
        "ram_gb": ram_gb,
        "cores": cores,
        "avx2": avx2,
        "platform": platform.system()
    }


# -----------------------------
# Vosk Model Selection Logic
# -----------------------------
def choose_vosk_model(hw):
    ram = hw["ram_gb"]
    cores = hw["cores"]
    avx2 = hw["avx2"]

    # Model URLs
    MODELS = {
        "tiny": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "normal": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
        "large": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip"
    }

    if ram < 4 or cores <= 2:
        return ("tiny", MODELS["tiny"])

    if 4 <= ram < 12:
        return ("normal", MODELS["normal"])

    # High-end system → large model
    if ram >= 12 and avx2:
        return ("large", MODELS["large"])

    # fallback safe
    return ("normal", MODELS["normal"])


# -----------------------------
# ENV handling
# -----------------------------
ROOT = Path.cwd()
ENV_PATH = ROOT / ".env"

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
# Installer Paths
# -----------------------------
def get_target_dir():
    if os.name == "nt":
        local = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        base = local / "TorqueAI" / "models" / "vosk"
    else:
        base = Path.home() / ".local" / "share" / "torque" / "models" / "vosk"
    base.mkdir(parents=True, exist_ok=True)
    return base


def model_already_installed(base_dir: Path):
    for p in base_dir.iterdir():
        if p.is_dir() and p.name.startswith("vosk-model-"):
            return p
    return None


# -----------------------------
# Download + Extract
# -----------------------------
def download_and_extract(url: str, dest: Path):
    print(f"[Installer] Downloading {url} ...")
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", "0"))
        downloaded = 0

        with open(tmp.name, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r[Installer] {pct}% downloaded", end="", flush=True)

    print("\n[Installer] Extracting model ...")
    tmpdir = tempfile.mkdtemp()

    try:
        with zipfile.ZipFile(tmp.name, "r") as z:
            z.extractall(tmpdir)

        for child in Path(tmpdir).iterdir():
            if child.is_dir():
                tgt = dest / child.name
                if tgt.exists():
                    shutil.rmtree(tgt)
                shutil.move(str(child), str(tgt))
                print(f"[Installer] Installed → {tgt}")
                return tgt

        return None

    finally:
        os.unlink(tmp.name)
        shutil.rmtree(tmpdir, ignore_errors=True)


# -----------------------------
# MAIN INSTALLER
# -----------------------------
def main():
    print("===========================================")
    print("      TORQUE VOSK INSTALLER (AUTO MODE)")
    print("===========================================")

    hw = detect_hardware()
    print(f"[Installer] Hardware detected: {hw}")

    model_name, model_url = choose_vosk_model(hw)
    print(f"[Installer] Selected model: {model_name} → {model_url}")

    base = get_target_dir()
    already = model_already_installed(base)
    if already:
        print(f"[Installer] Vosk already installed: {already}")
        write_env_key("VOSK_MODEL", str(already))
        print("[Installer] Updated .env")
        return

    try:
        tgt = download_and_extract(model_url, base)
        if tgt and tgt.exists():
            write_env_key("VOSK_MODEL", str(tgt))
            print("[Installer] Installation complete.")
            return
    except Exception as e:
        print(f"[Installer] Download failed: {e}")

    print("[Installer] ERROR: All downloads failed.")
    print("Please manually download a model from:")
    print("https://alphacephei.com/vosk/models")
    sys.exit(1)


if __name__ == "__main__":
    main()
