# Run with: python -m src.main
import os
import time
import threading
import tkinter as tk

from dotenv import load_dotenv
load_dotenv()

# --- Local imports ---
from .intent_router import IntentRouter
from .wake.pvporcupine import WakeWordListener
from .stt.whisper_command import WhisperCommandRecognizer
from .settings import load_settings
from .nlp_entities import extract_app_name
from .tts.tts_local import speak_now, stop_all_tts
from .ai.planner import plan

# --- Voice authentication (SVM-based) ---
from .voice_auth.recorder import record_seconds
from .voice_auth.svm_auth import verify_svm, enroll_svm, SR
from .voice_auth.enroll_ui import run_enrollment

# --- Tools ---
from .tools.system_tools import (
    open_app, close_app, rescan_apps, close_all_apps,
    list_available_apps, set_volume, get_time, tell_joke
)


DISPLAY_PREFIX = "Torque:"


# ---------------- Router ----------------
def build_router() -> IntentRouter:
    router = IntentRouter(threshold=0.52)
    router.add_intent("open_app",
        ["open notepad","launch calculator","start the browser","open file explorer","open my files","start chrome","open spotify"],
        open_app)
    router.add_intent("close_app",
        ["close chrome","quit edge","exit notepad","close visual studio code","kill spotify","stop browser"],
        close_app)
    router.add_intent("rescan_apps",
        ["rescan apps","scan apps","rebuild app index","refresh apps"],
        rescan_apps)
    router.add_intent("close_all_apps",
        ["close all the apps","close everything you opened","close all apps","shut everything you started"],
        close_all_apps)
    router.add_intent("list_apps",
        ["what apps can you open","what can you open","list apps","show installed apps","which apps can you launch"],
        list_available_apps)
    router.add_intent("get_time",
        ["what time is it","tell me the time","current time","what day is it","date today"],
        get_time)
    router.add_intent("tell_joke",
        ["tell me a joke","make me laugh","joke please","say a joke"],
        tell_joke)
    router.add_intent("set_volume",
        ["set volume to 50%","volume 30","increase volume to 80","decrease volume to 20"],
        set_volume)
    router.build()
    return router


# ---------------- Main ----------------
def main():
    settings = load_settings()
    assistant_name = (
        getattr(settings, "wake", None) and (settings.wake.phrase or "TORQUE") or "TORQUE"
    ).upper()

    VOICE_MODEL_PATH = os.getenv("VOICE_MODEL_PATH", "voice_auth_svm.joblib").strip()
    AUTH_ENROLL_SAMPLES = int(os.getenv("AUTH_ENROLL_SAMPLES", "5"))
    AUTH_ENROLL_SECONDS = float(os.getenv("AUTH_ENROLL_SECONDS", "2.0"))
    AUTH_DEVICE_INDEX_ENV = os.getenv("AUTH_DEVICE_INDEX", "").strip()
    AUTH_DEVICE_INDEX = int(AUTH_DEVICE_INDEX_ENV) if AUTH_DEVICE_INDEX_ENV.isdigit() else None

    # ---------- Auto-enroll if model missing ----------
    if not os.path.exists(VOICE_MODEL_PATH):
        print("[Auth] No voice model found. Starting automatic enrollment...")
        run_enrollment(
            model_path=VOICE_MODEL_PATH,
            samples_count=AUTH_ENROLL_SAMPLES,
            sample_seconds=AUTH_ENROLL_SECONDS,
            device_index=AUTH_DEVICE_INDEX,
            speak_fn=speak_now,
        )
        print("[Auth] Enrollment finished, model saved.")
        time.sleep(1.0)

    # ---------- Build assistant UI ----------
    router = build_router()
    root = tk.Tk()

    from .ui.app import AssistantUI

    shutdown_evt = threading.Event()
    force_stop_evt = threading.Event()
    active_rec = {"obj": None}
    wake_holder = {"obj": None}

    def say(text: str):
        if shutdown_evt.is_set():
            return
        line = (text or "").strip()
        if not line:
            return
        ui.append(line, is_torque=True)
        ui.set_speaking(True)
        try:
            speak_now(line)
            time.sleep(0.10)
        except Exception as e:
            print("[TTS] speak_now failed:", e)
        finally:
            ui.set_speaking(False)

    def handle_text(text: str):
        t = (text or "").strip()
        lower = t.lower()
        if any(sw in lower for sw in ("sleep","stop listening","hide window","goodbye","bye","quit","exit")):
            return

        looks_like_qa = t.endswith("?") or lower.startswith(
            ("what ","who ","how ","why ","when ","where ","tell me ","explain ")
        )
        try_planner_first = looks_like_qa

        try:
            label, score = (None, 0.0)
            if not try_planner_first:
                label, score = router.route(t)
            print(f"[Router] label={label} score={score:.2f}")

            use_planner = try_planner_first or (label is None or score < 0.55)

            if use_planner:
                print("[Handler] Using planner fallback…")
                p = plan(t)
                print("[Planner] result:", p)
                if p and "tool" in p:
                    tool = (p["tool"] or "").strip()
                    args = p.get("args", {}) or {}
                    tool_map = {
                        "open_app": open_app,
                        "close_app": close_app,
                        "close_all_apps": close_all_apps,
                        "rescan_apps": rescan_apps,
                        "list_apps": list_available_apps,
                        "set_volume": set_volume,
                        "get_time": get_time,
                        "tell_joke": tell_joke,
                    }
                    fn = tool_map.get(tool)
                    if fn:
                        if tool == "open_app":
                            app = (args.get("name") or extract_app_name(t) or "").strip()
                            if app:
                                say(f"Opening {app}.")
                                _ = fn(app)
                                return
                        param = args.get("name") or args.get("filter") or args.get("percent") or t
                        reply = fn(param)
                        if tool == "list_apps":
                            ui.append(reply, is_torque=True)
                            say("I listed the apps in the panel.")
                        else:
                            say(reply)
                        return
                if p and "say" in p:
                    say(str(p["say"]))
                    return
                say("I'm not sure what you mean.")
                return

            # router confident
            if label == "open_app":
                app = extract_app_name(t)
                if app:
                    say(f"Opening {app}.")
                    _ = router.handlers[label](t)
                    return
            reply = router.handlers[label](t)
            say(reply)

        except Exception as e:
            print("[Handler] ERROR:", e)
            try:
                say("Something went wrong handling that request.")
            except Exception:
                pass

    def on_force_stop():
        ui.append("Force stopping current session.", is_system=True)
        force_stop_evt.set()
        try:
            r = active_rec["obj"]
            if r is not None:
                r.close()
        except Exception:
            pass
        try:
            stop_all_tts()
        except Exception:
            pass
        ui.set_listening(False)
        ui.set_speaking(False)
        ui.set_status("Ready — listening for wake word: 'torque'")

    ui = AssistantUI(root, on_submit=handle_text, title=assistant_name, on_force_stop=on_force_stop)
    ui.set_status("Ready — listening for wake word: 'torque'")
    ui.set_listening(True)
    say("Ready and listening for torque")

    # ---------- Wake listener ----------
    access_key   = os.getenv("PORCUPINE_ACCESS_KEY", "").strip()
    keyword_path = (os.getenv("PORCUPINE_KEYWORD_PATH") or "").strip()
    device_index_env = os.getenv("PORCUPINE_DEVICE_INDEX", "").strip()
    device_index = int(device_index_env) if device_index_env.isdigit() else None

    def start_wake_listener():
        if not access_key or not keyword_path:
            ui.append("Set PORCUPINE_ACCESS_KEY and PORCUPINE_KEYWORD_PATH for wake word 'torque'.", is_system=True)
            return
        old = wake_holder.get("obj")
        if old is not None:
            try: old.stop()
            except Exception: pass
            wake_holder["obj"] = None

        w = WakeWordListener(
            access_key=access_key,
            on_detect=on_wake,
            keyword=None,
            keyword_path=keyword_path,
            device_index=device_index,
            on_level=lambda lvl: root.after(0, lambda: ui.update_mic_level(lvl)),
        )
        wake_holder["obj"] = w
        w.start()

    # ---------- Voice session ----------
    def voice_session():
        force_stop_evt.clear()
        w = wake_holder.get("obj")
        if w is not None:
            try: w.stop()
            except Exception: pass
            wake_holder["obj"] = None

        root.after(0, lambda: (
            ui.set_status("Listening for command… (say 'sleep' or 'bye' to stop)"),
            ui.set_listening(True)
        ))

        rec = WhisperCommandRecognizer(
            model_size=os.getenv("WHISPER_MODEL", "tiny"),
            device="cpu",
            compute_type="int8",
            on_level=lambda lvl: root.after(0, lambda: ui.update_mic_level(lvl)),
        )
        active_rec["obj"] = rec
        STOP_WORDS = ("sleep","stop listening","hide window","goodbye","bye","quit","exit")

        try:
            while True:
                if force_stop_evt.is_set() or shutdown_evt.is_set():
                    ui.append("Session aborted.", is_system=True)
                    break

                text = rec.listen_once()
                if not text:
                    continue

                lower = text.lower().strip()
                root.after(0, lambda t=text: ui.set_caption(t))

                if any(sw in lower for sw in STOP_WORDS):
                    root.after(0, lambda: ui.append("Going to sleep…", is_system=True))
                    break

                root.after(0, lambda t=text: ui.append(t, is_torque=False))
                handle_text(text)
        finally:
            try: rec.close()
            except Exception: pass
            active_rec["obj"] = None
            root.after(0, lambda: (
                ui.set_listening(False),
                ui.set_status("Ready — listening for wake word: 'torque'"),
                ui.set_caption("")
            ))
            start_wake_listener()

    # ---------- Wake verification ----------
    def on_wake():
        if shutdown_evt.is_set():
            return

        w = wake_holder.get("obj")
        if w is not None:
            try: w.stop()
            except Exception: pass
            wake_holder["obj"] = None

        ui.set_status("Verifying speaker…")
        time.sleep(0.05)
        sample = record_seconds(2.0, device_index=AUTH_DEVICE_INDEX)

        if not os.path.exists(VOICE_MODEL_PATH):
            ui.append("No speaker model available → enrolling automatically.", is_system=True)
            say("No model found. Starting quick enrollment.")
            run_enrollment(model_path=VOICE_MODEL_PATH)
            start_wake_listener()
            return

        ok, score, thr = verify_svm(sample, VOICE_MODEL_PATH, threshold=0.55)  # ⬅️ slightly lower threshold
        print(f"[Auth] verify score={score:.3f} thr={thr:.3f} ok={ok}")

        if ok:
            ui.append(f"Access granted (score={score:.2f} ≥ {thr:.2f}).", is_system=True)
            say("Access granted, my master.")
            say("Hi master")
            threading.Thread(target=voice_session, daemon=True).start()
        else:
            ui.append(f"Access denied (score={score:.2f} < {thr:.2f}).", is_system=True)
            say("Access denied.")
            start_wake_listener()

    start_wake_listener()

    def on_close():
        shutdown_evt.set()
        force_stop_evt.set()
        try:
            w = wake_holder.get("obj")
            if w: w.stop()
        except Exception:
            pass
        try:
            r = active_rec.get("obj")
            if r: r.close()
        except Exception:
            pass
        try:
            stop_all_tts()
        except Exception:
            pass
        try:
            root.quit()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
        import threading as _th, os as _os
        _th.Timer(0.6, lambda: _os._exit(0)).start()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
