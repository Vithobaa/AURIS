import csv
from datetime import datetime
import psutil

LOG_FILE = "auris_experiment_log.csv"

def log_event(trial, module, value, unit="ms"):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%H:%M:%S"),
            trial,
            module,
            round(value, 4),
            unit
        ])
import sys, os
import socket

def is_online(host="8.8.8.8", port=53, timeout=1.5):
    """Check if we have an active internet connection."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False

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
from src.ai.planner import plan, synthesize_answer

# --- Voice authentication (SVM-based) ---
from src.voice_auth.recorder import record_seconds
from src.voice_auth.svm_auth import verify_svm
from src.voice_auth.enroll_ui import run_enrollment

GLOBAL_TOOL_MAP = {}

# -----------------------------------------------------------
def build_router() -> IntentRouter:
    router = IntentRouter(threshold=0.52)
    
    # --- WAKE WORD BYPASS (Fixes "Hey Torque" going to Ollama) ---
    router.add_intent("wake_check",
        ["hey torque", "torque", "hello torque", "hi torque"],
        lambda _t: "I'm here. What do you need?")

    from src.tools.registry import load_all_tools
    load_all_tools(router, GLOBAL_TOOL_MAP)

    router.build()
    return router

# -----------------------------------------------------------
def main():
    settings = load_settings()
    assistant_name = "AURIS"

    # --- Speaker verification model ---
    VOICE_MODEL_PATH = os.getenv("VOICE_MODEL_PATH", "voice_auth_svm.joblib").strip()
    AUTH_DEVICE_INDEX = int(os.getenv("AUTH_DEVICE_INDEX", "0"))

    # Initialize global Tcl interpreter root early
    root = tk.Tk()
    root.withdraw() # hide it during wizards
    try:
        import ttkbootstrap as tb
        _ = tb.Style("darkly")
    except Exception as e:
        print("[Setup] Could not load ttkbootstrap theme globally:", e)

    # === FIRST-RUN SETUP WIZARD ===
    
    # 1. Voice Enrollment
    if not os.path.exists(VOICE_MODEL_PATH):
        print("[Setup] No voice model found. Starting automatic enrollment...")
        run_enrollment(
            model_path=VOICE_MODEL_PATH,
            samples_count=int(os.getenv("AUTH_ENROLL_SAMPLES", "5")),
            sample_seconds=float(os.getenv("AUTH_ENROLL_SECONDS", "2.0")),
            device_index=AUTH_DEVICE_INDEX,
            speak_fn=speak_now,
        )
        print("[Setup] Enrollment finished, model saved.")
        time.sleep(1.0)
        
    # 2. Ollama Graphical Setup
    if not os.getenv("OLLAMA_MODEL"):
        print("[Setup] Ollama config missing. Launching AI Brain Setup...")
        from src.ui.setup_ollama_ui import run_ollama_setup_ui
        run_ollama_setup_ui()
        time.sleep(1.0)
        # Reload environment variables freshly after installation
        from dotenv import load_dotenv
        load_dotenv(override=True)

    # Build UI
    root.deiconify() # Reveal it
    from src.ui.app import AssistantUI

    router = build_router()

    shutdown_evt = threading.Event()
    force_stop_evt = threading.Event()
    typing_busy_evt = threading.Event() # Logic lock for typed commands
    active_rec = {"obj": None}
    wake_holder = {"obj": None}
    
    # Keep track of the last few queries for fallback memory ("who is ceo of google" -> "then microsoft")
    conversation_history = []
    
    def log_history(u_text: str, t_name: str):
        conversation_history.append({"user": u_text, "tool": t_name})
        if len(conversation_history) > 6:
            conversation_history.pop(0)

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
             # Stop TTS for silence
            stop_all_tts()
        except: pass

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

    def _handle_text_inner(text: str):
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

        online = is_online()
        
        try:
            # 1. ALWAYS RUN ML CLASSIFIER FIRST (Hybrid Intent Architecture)
            label, score = router.route(t)
            print(f"[Router] label={label} score={score:.2f}")
            
            ML_THRESHOLD = 0.60

            if score >= ML_THRESHOLD and label is not None:
                # --- HIGH CONFIDENCE: DIRECT ML EXECUTION ---
                print(f"[Handler] High confidence ML match ({score:.2f} >= {ML_THRESHOLD}). Direct execution.")
                
                # Intent-based explicit web search (bypasses planner)
                if label == "web_search":
                    say("Let me look that up online...")
                    query = t.replace("search for","").replace("web search","").replace("google","").replace("look up","").replace("find online","").strip()
                    
                    if len(conversation_history) > 0:
                        query_with_context = " ".join([h.get("user", "") for h in conversation_history[-2:] if isinstance(h, dict)]) + " " + query
                    else:
                        query_with_context = query
                        
                    raw_results = search_web(query_with_context)
                    final_answer = synthesize_answer(t, raw_results, fast_mode=online)
                    say(final_answer)
                    log_history(t, "web_search")
                    return

                # Wi-Fi connect handler
                if label == "wifi_connect":
                    import re
                    nums = re.findall(r"\b(\d+)\b", t)
                    if nums:
                        reply = connect_wifi_by_number(int(nums[0]))
                        say(reply)
                    else:
                        say("Say a number after 'connect'.")
                    log_history(t, "wifi_connect")
                    return

                # Normal router intents
                reply = router.handlers[label](t)
                say(str(reply))
                log_history(t, str(label))
                return

            else:
                # --- LOW CONFIDENCE: LLM FALLBACK ---
                print("[Handler] Complex command (Low ML confidence). Asking Planner (LLM)...")
                
                llm_start = time.time()
                p = plan(t, history=conversation_history)
                llm_end = time.time()

                llm_latency = (llm_end - llm_start) * 1000
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                log_event("llm_trial", "cpu_usage", cpu_usage, "percent")
                log_event("llm_trial", "memory_usage", memory_usage, "percent")
                log_event("llm_trial", "llm_latency", llm_latency, "ms")
                print("[Planner] result:", p)

                if p and "tool" in p:
                    tool = p["tool"].strip()
                    args = p.get("args", {}) or {}
                    tool_map = GLOBAL_TOOL_MAP
                    
                    if tool == "none":
                        if p.get("say"):
                            say(str(p["say"]))
                        else:
                            say("I didn't quite catch that.")
                        log_history(t, "none")
                        return
                        
                    fn = tool_map.get(tool)
                    if fn:
                        if tool in ["open_app", "close_app"]:
                            app = args.get("name") or extract_app_name(t)
                            if app:
                                say(f"Opening {app}." if tool == "open_app" else f"Closing {app}.")
                                fn(app)
                                return
                                
                        elif tool in ["connect_wifi", "connect_bluetooth"]:
                            import re
                            match = re.search(r"connect.*?(\d+)", t)
                            if match:
                                idx=int(match.group(1))
                                say(f"Connecting to device {idx}.")
                                say(str(fn(idx)))
                            else:
                                if tool == "connect_bluetooth":
                                    say(str(fn("")))
                                else:
                                    say("Which network number to connect to?")
                            log_history(t, str(tool))
                            return
                            
                        # Handle functions that take no arguments
                        if tool in ["wifi_on", "wifi_off", "list_wifi", "rescan_apps", "close_all_apps", "media_play_pause", "media_next", "media_prev", "get_time", "tell_joke", "check_system", "read_clipboard", "get_news", "bluetooth_on", "bluetooth_off", "list_bluetooth", "connect_bluetooth"]:
                            reply = fn()
                            if reply:
                                say(str(reply))
                            log_history(t, str(tool))
                            return
                        
                        param = str(args.get("name") or args.get("filter") or args.get("percent") or args.get("query") or args.get("city") or args.get("path") or t)
                        
                        # --- HYBRID WEB SEARCH ---
                        if tool == "web_search" or tool == "weather":
                            say("Let me check that for you...")
                            raw_results = fn(param)
                            final_answer = synthesize_answer(t, raw_results)
                            say(final_answer)
                            log_history(t, str(tool))
                            return
                        
                        reply = fn(param)
                        if reply:
                            say(str(reply))
                        log_history(t, str(tool))
                        return

                if p and "say" in p:
                    say(str(p["say"]))
                    log_history(t, "none")
                    return

                # Planner failed or returned None. If it looks like a question, try direct web search.
                if looks_like_qa:
                    print("[Handler] Planner failed but it's a question. Forcing web search fallback.")
                    say("Let me look that up online...")
                    raw_results = search_web(t)
                    final_answer = synthesize_answer(t, raw_results, fast_mode=True)
                    say(final_answer)
                    return

                say("I see. (Offline mode)")
                return

        except Exception as e:
            print("[Handler] ERROR:", e)
            say("Something went wrong handling that request.")
    def handle_text(text: str):
        # Pause mic (and block voice loop) while processing typed command
        typing_busy_evt.set()
        pause_mic()
        try:
            _handle_text_inner(text)
        finally:
            typing_busy_evt.clear()

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

                pipeline_start = time.time()
                text = rec.listen_once()
                pipeline_end = time.time()

                if text:
                    total_latency = (pipeline_end - pipeline_start) * 1000
                    log_event("pipeline_trial", "stt_pipeline_latency", total_latency, "ms")

                # immediately pause mic so Torque does not hear itself
                pause_mic()

                if not text:
                    # If text is empty (maybe mic paused by typed command?), wait for lock
                    while typing_busy_evt.is_set():
                        time.sleep(0.1)
                    
                    # If recorder was closed while we were waiting (e.g. sleep command), exit loop
                    if active_rec["obj"] != rec:
                         break

                    # resume and continue listening
                    resume_mic()
                    continue

                lower = text.lower().strip()

                root.after(0, lambda t=text: ui.set_caption(t))
                root.after(0, lambda t=text: ui.append(t))

                # if user says a stop word while in voice session, break loop
                if any(sw == lower or lower.startswith(sw + " ") or (" " + sw + " ") in (" " + lower + " ") for sw in STOP_WORDS):
                    root.after(0, lambda: ui.append("Sleeping…", is_system=True))
                    # DO NOT call enter_sleep() here, just break. 
                    # The finally block will handle cleanup and restart wake listener.
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
            if not shutdown_evt.is_set():
                start_wake_listener()

    # Wake handler
    def on_wake(audio_data=None):
        import time
        print("[MEASURE] on_wake() started at:", time.time())
        if shutdown_evt.is_set():
            return

        w = wake_holder.get("obj")
        if w:
            try: w.stop()
            except: pass
            wake_holder["obj"] = None

        if audio_data is not None:
            # Seamless rolling buffer used
            ui.set_status("Verifying speaker (Seamless)")
            sample = audio_data
        else:
            # Legacy fallback
            ui.set_status("Verifying speaker…")
            sample = record_seconds(2.0, device_index=AUTH_DEVICE_INDEX)

        t0 = time.time()
        ok, score, thr = verify_svm(sample, VOICE_MODEL_PATH, threshold=float(os.getenv("AUTH_VERIFY_THRESHOLD", "0.60")))
        t1 = time.time()

        auth_latency = (t1 - t0) * 1000
        log_event("auth_trial", "authentication_latency", auth_latency, "ms")
        log_event("auth_trial", "auth_score", score, "prob")
        log_event("wake_trial", "wake_trigger", 1, "event")
        print("[MEASURE] SVM verification time:", auth_latency)
        print(f"[Auth] score={score:.3f} thr={thr:.3f} ok={ok}")
        print("[MEASURE] SVM verification time:", t1 - t0)

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

        # try:
        #     r = active_rec.get("obj")
        #     if r: r.close()
        # except: pass

        # try: stop_all_tts()
        # except: pass

        try: root.quit()
        except: pass

        try: root.destroy()
        except: pass

        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        try: os._exit(0)
        except: pass
