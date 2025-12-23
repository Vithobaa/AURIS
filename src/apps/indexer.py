import os, json, pathlib
from typing import Dict, Iterable

APPDATA_DIR = os.path.join(os.getenv("APPDATA", ""), "Torque")
INDEX_PATH  = os.path.join(APPDATA_DIR, "apps_index.json")

# Shortcuts (existing)
_START_MENU_USER = os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
_START_MENU_ALL  = os.path.join(os.getenv("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
_DESKTOP_USER    = os.path.join(os.path.expanduser("~"), "Desktop")
_DESKTOP_PUBLIC  = os.path.join(os.getenv("PUBLIC", r"C:\Users\Public"), "Desktop")

# Extra locations to look for .exe (per-user & common)
_EXE_DIRS: Iterable[str] = [
    os.path.join(os.getenv("APPDATA", ""), "Spotify"),
    os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs"),
    os.path.join(os.getenv("LOCALAPPDATA", ""), r"Microsoft\WindowsApps"),
    os.getenv("ProgramFiles", r"C:\Program Files"),
    os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"),
]

_VALID_SHORTCUTS = {".lnk", ".url"}
_VALID_BINARIES  = {".exe"}

def _norm(name: str) -> str:
    t = name.lower()
    t = "".join(ch for ch in t if ch.isalnum() or ch.isspace())
    return " ".join(t.split())

def _gather_shortcuts(root: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not root or not os.path.isdir(root):
        return out
    for p in pathlib.Path(root).rglob("*"):
        if p.is_file() and p.suffix.lower() in _VALID_SHORTCUTS:
            out[p.stem] = str(p)
    return out

def _gather_exes(root: str, *, max_depth: int = 2) -> Dict[str, str]:
    """
    Shallow scan for .exe to avoid huge walks.
    max_depth counts folders below root.
    """
    out: Dict[str, str] = {}
    if not root or not os.path.isdir(root):
        return out

    root_path = pathlib.Path(root)
    for p in root_path.rglob("*.exe"):
        # enforce shallow depth
        try:
            depth = len(p.relative_to(root_path).parts) - 1  # exclude the file itself
        except Exception:
            depth = 99
        if depth > max_depth:
            continue

        name = p.stem
        # skip updaters/helpers to reduce noise
        bad = ("helper", "update", "updater", "installer", "setup", "elevation")
        lname = name.lower()
        if any(b in lname for b in bad):
            continue

        out[name] = str(p)
    return out

def build_index() -> Dict[str, str]:
    # 1) Shortcuts
    index: Dict[str, str] = {}
    for folder in [_START_MENU_USER, _START_MENU_ALL, _DESKTOP_USER, _DESKTOP_PUBLIC]:
        index.update(_gather_shortcuts(folder))

    # 2) Executables (shallow)
    for folder in _EXE_DIRS:
        index.update(_gather_exes(folder))

    # Normalize + vendorless aliases
    normalized: Dict[str, str] = {}
    for name, path in index.items():
        base = _norm(name)
        if not base:
            continue
        normalized[base] = path
        words = base.split()
        if len(words) > 1 and words[0] in {"microsoft","adobe","google","oracle","nvidia","intel"}:
            normalized[" ".join(words[1:])] = path

    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    return normalized

def load_index() -> Dict[str, str]:
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
