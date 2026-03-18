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
    # Remove specific check for Windows to allow pyttsx3
    # if _IS_WIN:
    #    return None
    if pyttsx3 is None:
        return None
    with _engine_lock:
        if _engine is None:
            _engine = pyttsx3.init()
            try:
                rate = _engine.getProperty("rate") or 200
                _engine.setProperty("rate", 200) # Faster default
                _engine.setProperty("volume", 1.0)
            except Exception:
                pass
        return _engine

_sapi_voice = None # Global reference for stopping speech
def stop_all_tts():
    """Stops TTS engine. On Windows, purges SAPI buffer."""
    global _sapi_voice, _engine
    
    if _IS_WIN:
        try:
            if _sapi_voice:
                 # SVSFPurgeBeforeSpeak (2) stops current speech
                _sapi_voice.Speak("", 2)
        except Exception:
            pass
        return

    # Non-Windows pyttsx3 stop
    if _engine is None:
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
    """
    Direct SAPI via comtypes (faster than PowerShell, safer threading than pyttsx3).
    Fallback to PowerShell if comtypes fails.
    """
    global _sapi_voice
    try:
        import comtypes.client
        # SAPI.SpVoice interface
        if _sapi_voice is None:
             _sapi_voice = comtypes.client.CreateObject("SAPI.SpVoice")
        
        # Async mode (1). Sync (0) blocks GIL/COM often.
        _sapi_voice.Speak(text, 1)
        
        # Wait loop to simulate blocking, but allow interruption/purge
        while True:
            # Wait 100ms
            if _sapi_voice.WaitUntilDone(100):
                break # Done speaking
            # We can perform checks here if needed, but for now just loop
            pass
    except Exception as e:
        print(f"[TTS] Direct SAPI failed: {e}. Falling back to PowerShell.")
        # Fallback to slow PowerShell
        safe = str(text).replace("`", "``").replace('"', '`"')
        ps = f'[void](New-Object -ComObject SAPI.SpVoice).Speak("{safe}")'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)

def _pyttsx3_say(text: str):
    e = _init_engine()
    if e is None:
        return
    e.say(text)
    try:
        e.runAndWait()
    except Exception:
        pass

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
