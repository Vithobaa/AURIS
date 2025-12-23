# src/setup/vosk_setup.py
import os
from pathlib import Path

def _common_model_locations():
    home = Path.home()
    candidates = [
        Path(os.getenv("VOSK_MODEL", "")) if os.getenv("VOSK_MODEL", "") else None,
        Path.cwd() / "models" / "vosk",
        Path.home() / "AppData" / "Local" / "TorqueAI" / "models" / "vosk",
        Path("/usr/local/share/torque/models/vosk"),
        Path("/opt/torque/models/vosk"),
    ]
    return [p for p in candidates if p]

def ensure_vosk_model() -> str:
    """
    Return a path to a valid Vosk model directory.
    If VOSK_MODEL env var points to a valid directory, return it.
    Otherwise scan common locations. If not found, raise RuntimeError.
    """
    env = os.getenv("VOSK_MODEL", "").strip()
    if env and Path(env).is_dir():
        return str(Path(env).resolve())

    for p in _common_model_locations():
        if p.is_dir():
            return str(p.resolve())

    # Not found — raise clear error so installer can be run
    raise RuntimeError(
        "Vosk model not found. Run installer.py to download a model, or set VOSK_MODEL in .env."
    )
