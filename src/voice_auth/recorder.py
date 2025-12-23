import sounddevice as sd
import numpy as np

def record_seconds(seconds=2.0, sample_rate=16000, device_index=None):
    print(f"[Recorder] Recording for {seconds:.1f} seconds...")
    rec = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype='float32', device=device_index)
    sd.wait()
    print("[Recorder] Recording complete.")
    return np.squeeze(rec)
