# src/stt/whisper_recognizer.py
import os
import numpy as np
import pyaudio
from whispercpp import Whisper

class SpeechRecognizer:
    """
    Whisper.cpp speech recognizer using mic streaming.
    Loads Whisper model ONCE per process using Whisper.from_pretrained.
    """

    _model = None
    _loaded_name = None

    def __init__(self, on_level=None):
        self.on_level = on_level
        self.sample_rate = 16000
        self.chunk = 1600  # 100 ms chunks

        # Load model once globally
        SpeechRecognizer._preload_model()

        # Audio input
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk,
        )

    # ---------------------------------------------------------
    @classmethod
    def _preload_model(cls):
        """Loads Whisper.cpp model only once globally."""
        if cls._model:
            return

        name = os.getenv("WHISPER_CPP_MODEL", "small.en").strip()

        print(f"[Whisper.cpp] Loading model: {name}")
        cls._model = Whisper.from_pretrained(name)
        cls._loaded_name = name
        print(f"[Whisper.cpp] Loaded successfully: {name}")

    # ---------------------------------------------------------
    def _amp_level(self, data):
        """Mic level for UI."""
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        lvl = int(min(1.0, np.abs(arr).mean() / 2000) * 100)
        return lvl

    # ---------------------------------------------------------
    def listen_once(self):
        """
        Simple VAD-like mechanism:
        - Detect voice start
        - Record until silence
        - Transcribe
        """

        frames = []
        silence = 0
        started = False

        for _ in range(200):  # ~20 seconds max
            data = self.stream.read(self.chunk, exception_on_overflow=False)

            # UI mic level
            if self.on_level:
                self.on_level(self._amp_level(data))

            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            vol = np.abs(arr).mean()

            # start speech
            if not started:
                if vol > 150:
                    started = True
                    frames.append(arr)
                continue
            else:
                frames.append(arr)
                if vol < 80:
                    silence += 1
                    if silence > 8:  # 800 ms silence
                        break
                else:
                    silence = 0

        if not frames:
            return ""

        audio = np.concatenate(frames) / 32768.0

        # Whisper.cpp transcription
        result = SpeechRecognizer._model.transcribe(audio, language="en")
        text = result.get("text", "").strip()
        return text

    # ---------------------------------------------------------
    def pause(self):
        try:
            self.stream.stop_stream()
        except Exception:
            pass

    def resume(self):
        try:
            self.stream.start_stream()
        except Exception:
            pass

    # ---------------------------------------------------------
    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()
        except Exception:
            pass
