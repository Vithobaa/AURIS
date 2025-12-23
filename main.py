
import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import time
import threading
import tkinter as tk
from dotenv import load_dotenv
load_dotenv()

# --- Local imports ---
from src.intent_router import IntentRouter
from src.wake.pvporcupine import WakeWordListener
from src.stt.leopard_recognizer import LeopardRecognizer

from src.settings import load_settings
from src.nlp_entities import extract_app_name
from src.tts.tts_local import speak_now, stop_all_tts
from src.ai.planner import plan

# --- Voice authentication (SVM-based) ---
from src.voice_auth.recorder import record_seconds
from src.voice_auth.svm_auth import verify_svm
from src.voice_auth.enroll_ui import run_enrollment

# --- Tools ---
from src.tools.system_tools import (
    open_app, close_app, rescan_apps, close_all_apps,
    list_available_apps, set_volume, get_time, tell_joke
)
from src.tools.wifi_tools import wifi_on, wifi_off, list_wifi, connect_wifi_by_number

# -----------------------------------------------------------
def build_router() -> IntentRouter:
    router = IntentRouter(threshold=0.52)

    router.add_intent("open_app",
        ["open notepad","launch calculator","start the browser",
         "open file explorer","open my files","start chrome","open spotify"],
        open_app)

    router.add_intent("close_app",
        ["close chrome","quit edge","exit notepad",
         "close visual studio code","kill spotify","stop browser"],
        close_app)

    router.add_intent("rescan_apps",
        ["rescan apps","scan apps","rebuild app index","refresh apps"],
        rescan_apps)

    router.add_intent("close_all_apps",
        ["close all the apps","close everything you opened",
         "close all apps","shut everything you started"],
        close_all_apps)

    router.add_intent("list_apps",
        ["what apps can you open","what can you open","list apps",
         "show installed apps","which apps can you launch"],
        list_available_apps)

    router.add_intent("get_time",
        ["what time is it","tell me the time","current time",
         "what day is it","date today"],
        get_time)

    router.add_intent("tell_joke",
        ["tell me a joke","make me laugh","joke please","say a joke"],
        tell_joke)

    router.add_intent("set_volume",
        ["set volume to 50%","volume 30","increase volume to 80",
         "decrease volume to 20"],
        set_volume)
    router.add_intent("wifi_on",
         ["turn on wifi", "enable wifi", "wifi on"],
         lambda _t: wifi_on())

    router.add_intent("wifi_off",
         ["turn off wifi", "disable wifi", "wifi off"],
         lambda _t: wifi_off())

    router.add_intent("wifi_list",
         ["list wifi", "scan wifi", "show wifi", "wifi networks","list out the wifi"],
         lambda _t: list_wifi())

    router.add_intent("wifi_connect",
         ["connect to wifi", "connect wifi", "connect to network"],
         lambda _t: "")  # handled later in main

    router.build()
    return router

# -----------------------------------------------------------
def main():
    settings = load_settings()
    assistant_name = "AURIS"

    # --- Speaker verification model ---
    VOICE_MODEL_PATH = os.getenv("VOICE_MODEL_PATH", "voice_auth_svm.joblib").strip()
    AUTH_DEVICE_INDEX = int(os.getenv("AUTH_DEVICE_INDEX", "0"))

    # Auto-enroll if SVM missing
    if not os.path.exists(VOICE_MODEL_PATH):
        print("[Auth] No voice model found. Starting automatic enrollment...")
        run_enrollment(
            model_path=VOICE_MODEL_PATH,
            samples_count=int(os.getenv("AUTH_ENROLL_SAMPLES", "5")),
            sample_seconds=float(os.getenv("AUTH_ENROLL_SECONDS", "2.0")),
            device_index=AUTH_DEVICE_INDEX,
            speak_fn=speak_now,
        )
        print("[Auth] Enrollment finished, model saved.")
        time.sleep(1.0)

    # Build UI
    root = tk.Tk()
    from src.ui.app import AssistantUI

    router = build_router()

    shutdown_evt = threading.Event()
    force_stop_evt = threading.Event()
    active_rec = {"obj": None}
    wake_holder = {"obj": None}

    # Mic helpers
    def pause_mic():
        try:
            r = active_rec.get("obj")
            if r:
                if hasattr(r, "pause"):
                    try: r.pause(); return
                    except: pass
                if getattr(r, "stream", None):
                    try: r.stream.stop_stream(); return
                    except: pass
        except Exception:
            pass

    def resume_mic():
        try:
            r = active_rec.get("obj")
            if r:
                if hasattr(r, "resume"):
                    try: r.resume(); return
                    except: pass
                if getattr(r, "stream", None):
                    try: r.stream.start_stream(); return
                    except: pass
        except Exception:
            pass

    def say(text: str):
        if shutdown_evt.is_set():
            return
        text = (text or "").strip()
        if not text:
            return

        pause_mic()
        ui.append(text, is_torque=True)
        ui.set_speaking(True)
        try:
            speak_now(text)
        except Exception as e:
            print("[TTS] speak_now failed:", e)
        finally:
            ui.set_speaking(False)
            resume_mic()

    # central sleep helper (used for both typed and spoken stop-words)
    def enter_sleep():
        try:
            # stop any active recorder
            r = active_rec.get("obj")
            if r:
                try: r.close()
                except: pass
                active_rec["obj"] = None
        except Exception:
            pass

        # Update UI to sleeping mode
        try:
            ui.set_listening(False)
            ui.set_speaking(False)
            ui.set_status("Sleeping... Say 'Hey Torque' to wake.")
            ui.append("Entering sleep mode. Say the wake phrase to resume.", is_system=True)
        except Exception:
            pass

        # restart wake listener so wake word can wake assistant
        try:
            start_wake_listener()
        except Exception:
            pass

    def handle_text(text: str):
        t = text.strip()
        lower = t.lower()

        STOP_WORDS = ("sleep","stop listening","hide window","goodbye","bye","quit","exit")
        # if typed a stop-word, put assistant to sleep
        if any(sw == lower or lower.startswith(sw + " ") or (" " + sw + " ") in (" " + lower + " ") for sw in STOP_WORDS):
            enter_sleep()
            return

        looks_like_qa = (
            t.endswith("?")
            or lower.startswith(("what ","who ","how ","why ","when ","where ","tell me ","explain "))
        )

        try_planner_first = looks_like_qa

        try:
            label, score = (None, 0.0)
            if not try_planner_first:
                label, score = router.route(t)
            print(f"[Router] label={label} score={score:.2f}")

            use_planner = try_planner_first or (label is None or score < 0.55)

            # ---------------------------- PLANNER FALLBACK ------------------------
            if use_planner:
                print("[Handler] Using planner fallback…")
                p = plan(t)
                print("[Planner] result:", p)

                if p and "tool" in p:
                    tool = p["tool"].strip()
                    args = p.get("args", {}) or {}
                    tool_map = {
                        "open_app": open_app, "close_app": close_app,
                        "close_all_apps": close_all_apps, "rescan_apps": rescan_apps,
                        "list_apps": list_available_apps,
                        "set_volume": set_volume, "get_time": get_time,
                        "tell_joke": tell_joke,
                    }
                    fn = tool_map.get(tool)
                    if fn:
                        if tool == "open_app":
                            app = args.get("name") or extract_app_name(t)
                            if app:
                                say(f"Opening {app}.")
                                fn(app)
                                return
                        param = args.get("name") or args.get("filter") or args.get("percent") or t
                        reply = fn(param)
                        say(reply)
                        return

                if p and "say" in p:
                    say(str(p["say"]))
                    return

                say("I'm not sure what you mean.")
                return

            # --------------------- ROUTER INTENTS (CONFIDENT) --------------------

            # Wi-Fi connect handler
            if label == "wifi_connect":
                import re
                nums = re.findall(r"\b(\d+)\b", t)
                if nums:
                    reply = connect_wifi_by_number(int(nums[0]))
                    say(reply)
                else:
                    say("Say a number after 'connect'.")
                return

            # Normal router intents
            reply = router.handlers[label](t)
            say(str(reply))
            return

        except Exception as e:
            print("[Handler] ERROR:", e)
            say("Something went wrong handling that request.")

    def on_force_stop():
        ui.append("Force stopping current session.", is_system=True)
        force_stop_evt.set()

        # stop STT engine
        try:
            r = active_rec["obj"]
            if r:
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
    ui.set_status("Ready — listening for wake word: 'torque' (Leopard STT)")
    ui.set_listening(True)
    say("Ready and listening for torque. Using Leopard offline STT.")

    # Wake word listener config
    access_key   = os.getenv("PORCUPINE_ACCESS_KEY", "").strip()
    keyword_path = os.getenv("PORCUPINE_KEYWORD_PATH", "").strip()
    device_index_env = os.getenv("PORCUPINE_DEVICE_INDEX", "").strip()
    device_index = int(device_index_env) if device_index_env.isdigit() else None

    def start_wake_listener():
        # Ensure previous listener is stopped
        try:
            old = wake_holder.get("obj")
            if old:
                try: old.stop()
                except: pass
        except Exception:
            pass

        if not access_key or not keyword_path:
            ui.append("Missing PORCUPINE_ACCESS_KEY or KEYWORD_PATH", is_system=True)
            return

        try:
            w = WakeWordListener(
                access_key=access_key,
                on_detect=on_wake,
                keyword_path=keyword_path,
                device_index=device_index,
                on_level=lambda lvl: root.after(0, lambda: ui.update_mic_level(lvl)),
            )
            wake_holder["obj"] = w
            w.start()
        except Exception as e:
            print("[WAKE] start failed:", e)
            ui.append("Wake listener failed to start.", is_system=True)

    # Voice session
    def voice_session():
        force_stop_evt.clear()
        # stop wake listener while in voice session
        w = wake_holder.get("obj")
        if w:
            try: w.stop()
            except: pass
            wake_holder["obj"] = None

        root.after(0, lambda: (
            ui.set_status("Listening… say 'sleep' to stop."), ui.set_listening(True)
        ))

        # create Leopard recognizer (reads PICOVOICE_LEOPARD_KEY from env)
        rec = LeopardRecognizer(on_level=ui.update_mic_level, device_index=device_index)
        active_rec["obj"] = rec

        STOP_WORDS = ("sleep","stop listening","hide window","goodbye","bye","quit","exit")

        try:
            while True:
                if force_stop_evt.is_set() or shutdown_evt.is_set():
                    break

                text = rec.listen_once()

                # immediately pause mic so Torque does not hear itself
                pause_mic()

                if not text:
                    # resume and continue listening
                    resume_mic()
                    continue

                lower = text.lower().strip()

                root.after(0, lambda t=text: ui.set_caption(t))
                root.after(0, lambda t=text: ui.append(t))

                # if user says a stop word while in voice session, enter sleep mode
                if any(sw == lower or lower.startswith(sw + " ") or (" " + sw + " ") in (" " + lower + " ") for sw in STOP_WORDS):
                    root.after(0, lambda: ui.append("Sleeping…", is_system=True))
                    enter_sleep()
                    break

                try:
                    handle_text(text)
                finally:
                    resume_mic()

        finally:
            try: rec.close()
            except: pass
            active_rec["obj"] = None

            root.after(0, lambda: (
                ui.set_listening(False),
                ui.set_status("Ready — listening for wake word: 'torque'"),
                ui.set_caption("")
            ))
            # restart wake listener after voice session ends (unless shutdown)
            start_wake_listener()

    # Wake handler
    def on_wake():
        import time
        print("[MEASURE] on_wake() started at:", time.time())
        if shutdown_evt.is_set():
            return

        w = wake_holder.get("obj")
        if w:
            try: w.stop()
            except: pass
            wake_holder["obj"] = None

        ui.set_status("Verifying speaker…")
        sample = record_seconds(2.0, device_index=AUTH_DEVICE_INDEX)

        import time
        t0 = time.time()
        ok, score, thr = verify_svm(sample, VOICE_MODEL_PATH, threshold=float(os.getenv("AUTH_VERIFY_THRESHOLD", "0.55")))
        t1 = time.time()
        print("[MEASURE] SVM verification time:", t1 - t0)


        ok, score, thr = verify_svm(sample, VOICE_MODEL_PATH, threshold=float(os.getenv("AUTH_VERIFY_THRESHOLD", "0.55")))
        print(f"[Auth] score={score:.3f} thr={thr:.3f} ok={ok}")

        if ok:
            ui.append(f"Access granted (score={score:.2f}).", is_system=True)
            say("Access granted.")
            threading.Thread(target=voice_session, daemon=True).start()
        else:
            ui.append(f"Access denied (score={score:.2f}).", is_system=True)
            say("Access denied.")
            start_wake_listener()
        


    start_wake_listener()

    # Shutdown
    def on_close():
        shutdown_evt.set()
        force_stop_evt.set()

        try:
            w = wake_holder.get("obj")
            if w: w.stop()
        except: pass

        try:
            r = active_rec.get("obj")
            if r: r.close()
        except: pass

        try: stop_all_tts()
        except: pass

        try: root.quit()
        except: pass

        try: root.destroy()
        except: pass

        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
