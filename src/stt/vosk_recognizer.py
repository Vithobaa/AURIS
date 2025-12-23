import os
import json
import numpy as np
import pyaudio
from vosk import Model, KaldiRecognizer

class VoskRecognizer:
    _loaded_model = None

    def __init__(self, model_path=None, on_level=None):
        self.on_level = on_level
        self.rate = 16000
        self.chunk = 4000

        model_path = model_path or os.getenv("VOSK_MODEL")

        if VoskRecognizer._loaded_model is None:
            print("[VOSK] Loading model once:", model_path)
            VoskRecognizer._loaded_model = Model(model_path)

        self.model = VoskRecognizer._loaded_model
        self.rec = KaldiRecognizer(self.model, self.rate)

        self.pa = pyaudio.PyAudio()
        self.stream = None
        self._open_stream()

    def _open_stream(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass

        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )

    def listen_once(self):
        while True:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
            except Exception:
                # Stream closed -> reopen safely
                self._open_stream()
                continue

            if self.on_level:
                lvl = int(np.abs(np.frombuffer(data, dtype=np.int16)).mean() / 300)
                self.on_level(min(100, lvl))

            if self.rec.AcceptWaveform(data):
                res = json.loads(self.rec.Result())
                return res.get("text", "").strip()

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()
        except:
            pass
