from __future__ import annotations
import json, os, tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from platformdirs import PlatformDirs

APP_NAME = "TORQUE"     # UI default title
APP_AUTHOR = "YourOrg"  # change to your name/org

dirs = PlatformDirs(APP_NAME, APP_AUTHOR)
CONFIG_DIR = Path(dirs.user_config_dir)
CONFIG_PATH = CONFIG_DIR / "settings.json"

@dataclass
class Settings:
    version: int = 1
    wake_word: str = "torque"  # default wake word
    tts_rate: int = 0          # 0 = engine default

def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)

def load_settings() -> Settings:
    env_wake = os.getenv("WAKE_WORD")
    if CONFIG_PATH.exists():
        try:
            obj = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            base = Settings()
            base_dict = asdict(base)
            base_dict.update(obj)
            s = Settings(**base_dict)
            if env_wake:
                s.wake_word = env_wake.strip()
            return s
        except Exception:
            pass
    s = Settings()
    if env_wake:
        s.wake_word = env_wake.strip()
    return s

def save_settings(s: Settings) -> None:
    _atomic_write(CONFIG_PATH, json.dumps(asdict(s), indent=2, ensure_ascii=False))

def set_wake_word(value: str) -> Settings:
    s = load_settings()
    s.wake_word = (value or "torque").strip()
    save_settings(s)
    return s
