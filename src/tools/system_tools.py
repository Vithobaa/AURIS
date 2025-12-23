# src/tools/system_tools.py
import os
import subprocess
import datetime
import random
from typing import Optional, Dict

import psutil

from ..nlp_entities import extract_app_name, extract_volume_value, guess_app_query
from ..apps.indexer import load_index, build_index
from ..apps.lookup import best_match

# ------------------------------------------------------------
# Session bookkeeping (what Torque opened this session)
# ------------------------------------------------------------
_LAUNCHED_PIDS: set[int] = set()     # exact PIDs we spawned (.exe)
_LAUNCHED_KEYS: set[str] = set()     # fuzzy keys/names we launched (.lnk/.url/UWP)

# In-memory cache of the app index (key -> absolute path)
_APPS: Optional[Dict[str, str]] = None

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _ensure_index():
    """Ensure _APPS is loaded; build if missing."""
    global _APPS
    if _APPS is None:
        _APPS = load_index()
        if not _APPS:
            # build_index() should do the full scan and return dict
            _APPS = build_index()

def _powershell_launch_uwp_by_name(name: str) -> bool:
    """Launch a UWP/Store app by fuzzy name using PowerShell Get-StartApps."""
    if os.name != "nt":
        return False
    try:
        safe = (name or "").replace("`", "``").replace('"', '`"')
        ps = f'''
$ErrorActionPreference="SilentlyContinue";
$name = "{safe}";
$apps = Get-StartApps | Sort-Object Name;
$app  = $apps | Where-Object {{ $_.Name -like "*$name*" }} | Select-Object -First 1;
if ($app -and $app.AppID) {{
  Start-Process explorer.exe "shell:AppsFolder\\$($app.AppID)";
  exit 0
}} else {{
  exit 2
}}
'''.strip()
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        return True
    except Exception:
        return False

def _try_protocol_schemes(name: str) -> bool:
    """Open via URL schemes for some popular apps (best-effort)."""
    if os.name != "nt":
        return False
    schemes = []
    n = (name or "").lower()
    if "spotify" in n:
        schemes.append("spotify:")
    if "edge" in n or "microsoft edge" in n:
        schemes.append("microsoft-edge:https://www.microsoft.com")
    if "mail" in n or "outlook" in n:
        schemes.append("outlookmail:")
    for s in schemes:
        try:
            os.startfile(s)
            return True
        except Exception:
            continue
    return False

# ------------------------------------------------------------
# Public tools
# ------------------------------------------------------------
def list_available_apps(_: str = "") -> str:
    """
    Read the discovered app index and return a readable, SHORT list.
    We show up to 25 app keys and speak a summary in main.py.
    """
    global _APPS
    _ensure_index()
    apps = sorted((_APPS or {}).keys())
    if not apps:
        return "I don't have any apps indexed yet. Say 'rescan apps' to build the list."

    total = len(apps)
    MAX_SHOW = 25
    shown = apps[:MAX_SHOW]
    listing = ", ".join(shown)
    if total > MAX_SHOW:
        return f"I can open about {total} apps. Some of them are: {listing}. Say 'rescan apps' to refresh the list."
    else:
        return f"I can open {total} apps: {listing}."


JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who understand binary and those who don’t."
]

def rescan_apps(_: str = "", cancel_evt=None) -> str:
    """
    Rebuild the app index using apps.indexer.build_index().
    If your build_index supports a cancel flag, pass it; otherwise just call it.
    """
    global _APPS
    try:
        # If your build_index signature accepts cancel_evt, uncomment next line and remove the other:
        # _APPS = build_index(cancel_evt=cancel_evt)
        _APPS = build_index()
    except Exception:
        # On any scan error, fall back to empty dict so we don't crash callers
        _APPS = {}

    found = len(_APPS or {})
    return f"App index refreshed. Found {found} entries."

def open_app(user_text: str) -> str:
    """
    Fuzzy-match an app from the index and launch it, recording what we opened.
    Includes UWP/Store & URL-scheme fallbacks and a single rebuild-and-retry.
    """
    global _APPS, _LAUNCHED_PIDS, _LAUNCHED_KEYS
    _ensure_index()

    q = guess_app_query(user_text) or user_text
    apps = _APPS or {}
    match = best_match(q, apps)
    if match:
        key, path, _score = match
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in {".lnk", ".url"}:
                os.startfile(path)
                _LAUNCHED_KEYS.add(key)
            elif ext == ".exe":
                p = subprocess.Popen([path], shell=False)
                _LAUNCHED_PIDS.add(p.pid)
                _LAUNCHED_KEYS.add(key)
            else:
                os.startfile(path)
                _LAUNCHED_KEYS.add(key)
            return f"Opening {key}."
        except Exception as e:
            # UWP/Store fallback
            if "windowsapps" in path.lower() or isinstance(e, PermissionError):
                if _try_protocol_schemes(key) or _powershell_launch_uwp_by_name(key):
                    _LAUNCHED_KEYS.add(key)
                    return f"Opening {key}."
            # Rebuild and retry once
            _APPS = build_index()
            apps = _APPS or {}
            match2 = best_match(q, apps)
            if match2:
                key2, path2, _ = match2
                try:
                    ext2 = os.path.splitext(path2)[1].lower()
                    if ext2 in {".lnk", ".url"}:
                        os.startfile(path2)
                        _LAUNCHED_KEYS.add(key2)
                    elif ext2 == ".exe":
                        p2 = subprocess.Popen([path2], shell=False)
                        _LAUNCHED_PIDS.add(p2.pid)
                        _LAUNCHED_KEYS.add(key2)
                    else:
                        os.startfile(path2)
                        _LAUNCHED_KEYS.add(key2)
                    return f"Opening {key2}."
                except Exception:
                    if "windowsapps" in (path2 or "").lower():
                        if _try_protocol_schemes(key2) or _powershell_launch_uwp_by_name(key2):
                            _LAUNCHED_KEYS.add(key2)
                            return f"Opening {key2}."
            return "I rescanned, but still couldn’t launch that app."

    # No match in index → last-chance UWP by fuzzy name
    if _try_protocol_schemes(q) or _powershell_launch_uwp_by_name(q):
        _LAUNCHED_KEYS.add(q.lower().strip())
        return f"Opening {q}."
    return "I couldn’t find that app. Say 'rescan apps' if you installed it recently."

def close_app(user_text: str) -> str:
    """
    Fuzzy-match app name and try to terminate related processes safely.
    """
    global _APPS
    _ensure_index()

    q = guess_app_query(user_text) or user_text
    match = best_match(q, _APPS or {})
    target_key = match[0] if match else (q.lower().strip() or "")
    if not target_key:
        return "Which app should I close?"

    targets = []
    tokens = set(target_key.split())

    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info.get("name") or "").lower()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        if name and any(tok and tok in name for tok in tokens):
            targets.append(p)

    if not targets:
        return f"I couldn't find a running process for '{target_key}'."

    killed = 0
    for p in targets:
        try:
            p.terminate()
        except Exception:
            pass

    gone, alive = psutil.wait_procs(targets, timeout=1.5)
    killed += len(gone)

    for p in alive:
        try:
            p.kill()
            killed += 1
        except Exception:
            pass

    if killed == 0:
        return f"Couldn't close {target_key}."
    if killed == 1:
        return f"Closed {target_key}."
    return f"Closed {killed} processes for {target_key}."

def close_all_apps(_: str = "") -> str:
    """
    Close only the apps Torque launched in THIS session.
    1) Terminate by PID we spawned.
    2) Also try fuzzy-close by keys we recorded (covers .lnk/.url/UWP).
    """
    global _LAUNCHED_PIDS, _LAUNCHED_KEYS

    total_attempts = 0
    total_closed = 0

    # 1) Exact PIDs first
    to_wait = []
    for pid in list(_LAUNCHED_PIDS):
        try:
            p = psutil.Process(pid)
            total_attempts += 1
            p.terminate()
            to_wait.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            _LAUNCHED_PIDS.discard(pid)

    gone, alive = psutil.wait_procs(to_wait, timeout=1.5)
    total_closed += len(gone)

    for p in alive:
        try:
            p.kill()
            total_closed += 1
        except Exception:
            pass
        finally:
            _LAUNCHED_PIDS.discard(p.pid)

    # 2) Fuzzy-close by recorded keys (names)
    if _LAUNCHED_KEYS:
        tokens_sets = [set(k.lower().split()) for k in list(_LAUNCHED_KEYS)]
        protect = {"explorer.exe", "python.exe", "pythonw.exe"}  # don’t kill shell/runtime

        cands = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = (p.info.get("name") or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if not name or name in protect:
                continue
            for toks in tokens_sets:
                if any(tok and tok in name for tok in toks):
                    cands.append(p)
                    break

        to_wait2 = []
        for p in cands:
            try:
                total_attempts += 1
                p.terminate()
                to_wait2.append(p)
            except Exception:
                pass

        gone2, alive2 = psutil.wait_procs(to_wait2, timeout=1.5)
        total_closed += len(gone2)
        for p in alive2:
            try:
                p.kill()
                total_closed += 1
            except Exception:
                pass

    _LAUNCHED_KEYS.clear()
    _LAUNCHED_PIDS.clear()

    if total_attempts == 0:
        return "I didn’t open any apps this session."
    if total_closed == 0:   
        return "I tried, but couldn’t close the apps I opened."
    return f"Closed {total_closed} app process(es) I opened this session."

def get_time(_: str) -> str:
    now = datetime.datetime.now()
    return now.strftime("It's %I:%M %p on %A, %d %B %Y.")

def tell_joke(_: str) -> str:
    return random.choice(JOKES)

def set_volume(user_text: str) -> str:
    value: Optional[int] = extract_volume_value(user_text)
    if value is None:
        return "What volume level should I set? (0-100)"
    # Replace this with your real volume setter if you wire one up.
    return f"Setting volume to {value} percent (simulated)."
