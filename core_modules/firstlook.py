import tkinter as tk
import threading
import queue
import json
import time
import whisper  # ← REPLACED VOSK WITH WHISPER
import sounddevice as sd
import pyttsx3
import os
import random
import re
import pvporcupine
import pyaudio
import struct
from datetime import datetime
import numpy as np

# ===== Config =====
USER_NAME = "Vithobaa"
# REMOVED VOSK MODEL PATH - No longer needed!
WAKE_WORD = "Hey DEPTO"

# ===== Setup Speech =====
tts = pyttsx3.init()
tts.setProperty("rate", 170)

def speak(text):
    # Run pyttsx3 in background to avoid blocking the UI
    def _speak_async(msg):
        try:
            local_tts = pyttsx3.init()
            local_tts.setProperty('rate', 170)
            local_tts.say(msg)
            local_tts.runAndWait()
        except Exception as e:
            print(f"TTS error: {e}")

    threading.Thread(target=_speak_async, args=(text,), daemon=True).start()

# ===== Whisper Speech-to-Text =====
class WhisperSTT:
    def __init__(self, model_size="base"):
        """Initialize Whisper model"""
        print("🔄 Loading Whisper model...")
        self.model = whisper.load_model(model_size)
        print("✅ Whisper model loaded!")
    
    def record_audio(self, duration=5, samplerate=16000):
        """Record audio from microphone"""
        print(f"🎤 Recording {duration} seconds of audio...")
        audio_data = sd.rec(int(duration * samplerate), 
                           samplerate=samplerate, channels=1, dtype='float32')
        sd.wait()  # Wait for recording to complete
        return audio_data.flatten()
    
    def transcribe(self, audio_array, samplerate=16000):
        """Transcribe audio using Whisper"""
        try:
            result = self.model.transcribe(audio_array, fp16=False)  # fp16=False for CPU
            return result["text"].strip()
        except Exception as e:
            print(f"❌ Whisper transcription error: {e}")
            return ""

# Initialize Whisper
whisper_engine = WhisperSTT("base")  # Use "tiny" for faster but less accurate, "small" for better accuracy

def listen_and_transcribe():
    """Listen for voice command using Whisper"""
    try:
        update_status("🎤 Listening... Speak your command!")
        update_caption("🎤 Recording audio... Speak now!")
        
        # Record audio
        audio_data = whisper_engine.record_audio(duration=6)  # Record 6 seconds
        
        update_caption("🎤 Processing speech...")
        update_status("🔄 Transcribing...")
        
        # Transcribe with Whisper
        text = whisper_engine.transcribe(audio_data)
        
        print(f"🎯 Whisper heard: '{text}'")
        return text
        
    except Exception as e:
        print(f"❌ Listening error: {e}")
        return ""

# ===== Wake Word Detection =====
class WakeWordDetector:
    def __init__(self):
        self.is_detected = False
        self.porcupine = None
        self.audio_stream = None
        self.setup_porcupine()
    
    def setup_porcupine(self):
        """Initialize Porcupine wake word detection"""
        try:
            self.porcupine = pvporcupine.create(
                access_key="Jrvxk4n4dcORLwUex3/UGmGUR/PqMLWSrwfayUytplAB26i1wUe2Ig==",
                keywords=['porcupine']
            )
            print("✅ Wake word detector ready")
        except Exception as e:
            print(f"❌ Porcupine setup failed: {e}")
            self.porcupine = None
    
    def listen_for_wake_word(self):
        """Listen continuously for wake word"""
        if self.porcupine is None:
            print("❌ Using manual activation (press button)")
            return False
        
        try:
            pa = pyaudio.PyAudio()
            self.audio_stream = pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
            
            print("Say 'Porcupine'")
            
            while not self.is_detected:
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    print("✅ Wake word detected!")
                    self.is_detected = True
                    return True
                
                time.sleep(0.01)
                
        except Exception as e:
            print(f"❌ Wake word listening error: {e}")
            return False
    
    def stop(self):
        """Cleanup wake word detector"""
        self.is_detected = True
        if self.audio_stream:
            self.audio_stream.close()
        if self.porcupine:
            self.porcupine.delete()

# ===== Simple NLP Engine =====
def simple_nlp_understand(command):
    """Simple NLP that understands natural language patterns"""
    command = command.lower().strip()
    
    print(f"🔍 Processing command: '{command}'")
    
    # Patterns for common commands
    patterns = {
        # Open applications
        r"(open|launch|start|run).*(notepad|text editor)": "open_notepad",
        r"(can you |please )?open.*(notepad|text editor)": "open_notepad",
        r"(open|launch|start|run).*(calculator|calc)": "open_calculator", 
        r"(need|want) (to use|the) calculator": "open_calculator",
        r"(open|launch|start|run).*(chrome|browser|web browser|internet)": "open_browser",
        r"(open|launch|start|run).*(explorer|file explorer|files|folder)": "open_explorer",
        r"(show me|open) my (documents|files|folders)": "open_explorer",
        
        # Time and date
        r"(what.s?|tell me|what is).*(time|clock)": "get_time",
        r"(what.s?|tell me|what is).*(date|day|today)": "get_date", 
        r"(time|clock).*(now|current|is it)": "get_time",
        r"current time": "get_time",
        r"what day is it": "get_date",
        
        # System controls
        r"(volume|sound).*(up|increase|louder|higher)": "volume_up",
        r"(volume|sound).*(down|decrease|lower|softer)": "volume_down", 
        r"(mute|unmute|silence).*(volume|sound)": "volume_mute",
        r"turn up.*volume": "volume_up",
        r"turn down.*volume": "volume_down",
        
        # Fun commands
        r"(tell me|say|tell).*(joke|funny story)": "tell_joke",
        r"(how are you|how.you doing|how do you feel)": "greeting",
        r"(who are you|what are you)": "about",
        
        # Search commands
        r"(search|find|look up).*(for )?(.+)": "web_search",
        r"(what is|who is|where is).*(.+)": "web_search",
        r"(google|search for).*(.+)": "web_search",
        
        # Help
        r"(what can you do|help|commands)": "help",
        
        # Stop listening
        r"(stop|exit|quit|sleep)": "stop_listening"
    }
    
    for pattern, intent in patterns.items():
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            print(f"✅ Matched pattern: {pattern} -> {intent}")
            return intent, extract_parameters(pattern, command, match)
    
    print("❌ No pattern matched")
    return "not_understood", {"original": command}

def extract_parameters(pattern, command, match):
    """Extract specific details from the command"""
    params = {}
    
    if "search" in pattern or "what is" in pattern:
        for i in range(1, 4):
            if match.group(i) and len(match.group(i).strip()) > 3:
                params["query"] = match.group(i).strip()
                break
    
    elif "volume" in pattern:
        level_match = re.search(r"(\d+)", command)
        if level_match:
            params["level"] = int(level_match.group(1))
    
    return params

def execute_command(intent, parameters):
    """Execute commands based on NLP understanding"""
    
    if intent == "open_notepad":
        os.system("notepad")
        return "Opening Notepad for you"
    
    elif intent == "open_calculator":
        os.system("calc")
        return "Opening Calculator"
    
    elif intent == "open_browser":
        try:
            os.system("start chrome")
            return "Opening Chrome browser"
        except:
            return "Opening web browser"
    
    elif intent == "open_explorer":
        os.system("explorer")
        return "Opening File Explorer"
    
    elif intent == "get_time":
        current_time = time.strftime("%I:%M %p")
        return f"The current time is {current_time}"
    
    elif intent == "get_date":
        current_date = time.strftime("%A, %B %d, %Y")
        return f"Today is {current_date}"
    
    elif intent == "volume_up":
        return "Volume increased"
    
    elif intent == "volume_down":
        return "Volume decreased"
    
    elif intent == "tell_joke":
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the computer go to the doctor? It had a virus!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "I'm reading a book on anti-gravity. It's impossible to put down!"
        ]
        return random.choice(jokes)
    
    elif intent == "greeting":
        return "I'm doing great! Ready to help you with anything."
    
    elif intent == "about":
        return "I'm DEPTO, your desktop assistant. I can help you open apps, check time, and more!"
    
    elif intent == "web_search":
        query = parameters.get("query", "something")
        return f"I would search for: {query}. (Search feature coming soon!)"
    
    elif intent == "help":
        return "I can: open apps (notepad, calculator, browser), tell time/date, tell jokes, and more!"
    
    elif intent == "stop_listening":
        return "Going to sleep. Say 'Porcupine' to wake me up!"
    
    else:
        original = parameters.get("original", "that")
        return f"I'm not sure how to handle: '{original}'. Try saying things like 'open notepad' or 'what time is it?'"

def process_command(command):
    """Main command processor with NLP"""
    if not command or len(command.strip()) < 2:
        return "I didn't hear anything clearly. Please try again."
    
    intent, parameters = simple_nlp_understand(command)
    return execute_command(intent, parameters)

# ===== Tkinter UI =====
root = tk.Tk()
root.title("DEPTO - Voice Activated Assistant (Whisper)")
root.geometry("500x450")

# Make window always on top
root.attributes('-topmost', True)

# Thread-safe UI queue for background threads to request UI updates
ui_queue = queue.Queue()

# Status Label
status_label = tk.Label(root, text="🔊 DEPTO is Online - Say 'Porcupine' to activate", 
                       font=("Arial", 14), fg="green", bg="lightyellow")
status_label.pack(pady=10, fill="x")

# Command Display
command_frame = tk.LabelFrame(root, text="Voice Assistant", font=("Arial", 12))
command_frame.pack(pady=10, fill="both", expand=True, padx=20)

caption_label = tk.Label(command_frame, text="Waiting for wake word...\n\nSay 'Porcupine' to activate me!", 
                        wraplength=460, font=("Arial", 11), justify="left", height=6)
caption_label.pack(padx=10, pady=10, fill="both", expand=True)

def update_status(text):
    """Queue a status update to be applied on the main thread."""
    ui_queue.put(('status', text))


def update_caption(text):
    """Queue a caption update to be applied on the main thread."""
    ui_queue.put(('caption', text))


def process_ui_queue():
    """Apply queued UI updates on the Tk main thread. Scheduled via root.after."""
    try:
        while True:
            item = ui_queue.get_nowait()
            if not item:
                continue
            typ, text = item
            if typ == 'status':
                status_label.config(text=text)
            elif typ == 'caption':
                caption_label.config(text=text)
    except queue.Empty:
        pass
    # Schedule next poll
    root.after(100, process_ui_queue)

# ===== Main Assistant Functions =====
def handle_user_command():
    """Handle one complete command cycle"""
    # Listen for command using Whisper
    command = listen_and_transcribe()
    update_caption(f"🎤 You said: {command if command else '[No speech detected]'}\n\nProcessing...")

    if command:
        update_status("🔄 Processing command...")
        response = process_command(command)
        update_caption(f"🎤 You said: {command}\n\n🤖 DEPTO: {response}")
        update_status("🗣️ Speaking response...")
        speak(response)
        
        # Check if user wants to stop
        if "stop" in command.lower() or "sleep" in command.lower():
            update_status("💤 Sleeping... Say 'Porcupine' to wake me")
            update_caption("💤 Assistant is sleeping...\n\nSay 'Porcupine' to activate!")
            return False  # Stop listening
    else:
        update_caption("❌ I didn't hear anything clearly")
        update_status("🗣️ Speaking...")
        speak("I didn't hear anything clearly. Please try again.")

    update_status("✅ Ready for next command")
    return True  # Continue listening

def wake_word_listener():
    """Continuous wake word detection loop"""
    wake_detector = WakeWordDetector()
    
    while True:
        try:
            # Listen for wake word
            update_status("💤 Sleeping... Say 'Porcupine' to activate")
            update_caption("💤 Assistant is sleeping...\n\nSay 'Porcupine' to wake me up!")
            
            wake_detected = wake_detector.listen_for_wake_word()
            
            if wake_detected:
                # Wake up sequence
                update_status("✅ Wake word detected!")
                update_caption("🎯 Wake word detected!\n\nI'm listening for your command...")
                speak("Yes? How can I help you?")
                
                # Handle commands until user says to stop
                continue_listening = True
                while continue_listening:
                    continue_listening = handle_user_command()
                
        except Exception as e:
            print(f"Error in wake word listener: {e}")
            update_status("❌ Error in wake word detection")
            time.sleep(2)

def manual_activation():
    """Manual activation via button (fallback)"""
    update_status("✅ Manual activation")
    update_caption("🎯 Manual activation!\n\nI'm listening for your command...")
    speak("Yes? How can I help you?")
    handle_user_command()

# ===== Buttons =====
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

manual_button = tk.Button(button_frame, text="🎤 Manual Activation", font=("Arial", 12),
                         command=lambda: threading.Thread(target=manual_activation).start(),
                         bg="blue", fg="white", padx=15, pady=8)
manual_button.pack(side="left", padx=5)

exit_button = tk.Button(button_frame, text="❌ Exit", font=("Arial", 12),
                       command=lambda: (root.destroy(), os._exit(0)),
                       bg="red", fg="white", padx=15, pady=8)
exit_button.pack(side="left", padx=5)

# Info label
info_label = tk.Label(root, text="Note: Say 'Porcupine' to activate voice commands", 
                     font=("Arial", 10), fg="gray")
info_label.pack(pady=5)

# ===== Startup =====
def start_assistant():
    """Start the assistant"""
    update_status("✅ DEPTO Started with Whisper")
    update_caption("🚀 DEPTO with Whisper Started!\n\nSay 'Porcupine' to activate!")
    speak(f"Welcome {USER_NAME}! DEPTO with Whisper is ready. Say Porcupine to activate me.")
    
    # Start wake word detection in background
    wake_thread = threading.Thread(target=wake_word_listener, daemon=True)
    wake_thread.start()

# ===== Run Application =====
if __name__ == "__main__":
    # Start assistant after UI loads
    root.after(1000, start_assistant)
    root.mainloop()