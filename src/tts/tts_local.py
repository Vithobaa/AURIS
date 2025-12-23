import atexit
import threading
import time
import os
import subprocess
from typing import Callable, Optional

# On Windows we use PowerShell SAPI for maximum reliability (no silent failures).
# On non-Windows we fall back to pyttsx3.

_IS_WIN = (os.name == "nt")
_engine = None
_engine_lock = threading.Lock()
try:
    import pyttsx3  # type: ignore
except Exception:
    pyttsx3 = None  # ok on Windows we don't need it

def _init_engine():
    """Init pyttsx3 engine for non-Windows only."""
    global _engine
    if _IS_WIN:
        return None
    if pyttsx3 is None:
        return None
    with _engine_lock:
        if _engine is None:
            _engine = pyttsx3.init()
            try:
                rate = _engine.getProperty("rate") or 180
                _engine.setProperty("rate", max(120, rate - 10))
                _engine.setProperty("volume", 1.0)
            except Exception:
                pass
        return _engine

def stop_all_tts():
    """Stops pyttsx3 if used (non-Windows). PowerShell calls are blocking anyway."""
    if _IS_WIN or _engine is None:
        return
    try:
        _engine.stop()
    except Exception:
        pass

@atexit.register
def _shutdown():
    try:
        stop_all_tts()
    except Exception:
        pass

# ----------------- Low-level say backends -----------------
def _win_ps_say(text: str):
    """Speak via PowerShell SAPI on Windows (blocking)."""
    safe = str(text).replace("`", "``").replace('"', '`"')
    ps = f'[void](New-Object -ComObject SAPI.SpVoice).Speak("{safe}")'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)

def _pyttsx3_say(text: str):
    e = _init_engine()
    if e is None:
        return
    e.say(text)
    e.runAndWait()

# ----------------- Public API -----------------
def speak_now(text: str):
    """Blocking speak. Uses PowerShell on Windows, pyttsx3 elsewhere."""
    if not text:
        return
    try:
        if _IS_WIN:
            _win_ps_say(text)
        else:
            _pyttsx3_say(text)
    except Exception:
        # As a last resort, try a second attempt (helps sporadic failures)
        try:
            time.sleep(0.05)
            if _IS_WIN:
                _win_ps_say(text)
            else:
                _pyttsx3_say(text)
        except Exception:
            # give up silently; UI still shows captions
            pass

def speak_stream(
    text: str,
    on_start: Optional[Callable[[], None]] = None,
    on_word: Optional[Callable[[str], None]] = None,
    on_end: Optional[Callable[[], None]] = None,
):
    """
    Streams captions while audio plays.
    On Windows (PowerShell) we emulate word events with a typewriter effect.
    On non-Windows with pyttsx3, we just typewriter as well for consistency.
    """
    if not text:
        return

    # Start audio in a background thread
    done_evt = threading.Event()

    def _audio_worker():
        try:
            speak_now(text)  # blocking in this thread
        finally:
            done_evt.set()

    t = threading.Thread(target=_audio_worker, daemon=True)
    t.start()

    # Callbacks for UI
    if on_start:
        try: on_start()
        except Exception: pass

    words = text.split()
    # Emit words at a natural pace while audio is playing
    for i, w in enumerate(words):
        if on_word:
            try: on_word(w)
            except Exception: pass
        time.sleep(0.06 if len(words) > 12 else 0.09)

    # Wait (short) for audio to finish so UI stays in sync
    done_evt.wait(timeout=max(1.5, min(6.0, 0.18 * len(words))))
    if on_end:
        try: on_end()
        except Exception: pass
