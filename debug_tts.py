import pyttsx3
import traceback

print("Testing pyttsx3 init...")
try:
    engine = pyttsx3.init()
    print("Engine initialized.")
    
    voices = engine.getProperty('voices')
    print(f"Found {len(voices)} voices.")
    for v in voices:
        print(f" - {v.name}")

    print("Speaking test phrase...")
    engine.say("Testing audio. Can you hear this?")
    engine.runAndWait()
    print("Done speaking.")

except Exception:
    traceback.print_exc()
