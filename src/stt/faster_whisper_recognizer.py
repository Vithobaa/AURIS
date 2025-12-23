# src/stt/faster_whisper_recognizer.py
import os
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

class FasterWhisperRecognizer:
    _model = None  # static shared model

    def __init__(self, on_level=None):
        self.on_level = on_level
        self.sample_rate = 16000
        self.chunk = 16000 // 10  # 100ms
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk
        )

        if FasterWhisperRecognizer._model is None:
            self._load_model()

    @classmethod
    def _load_model(cls):
        path = os.getenv("FASTER_WHISPER_MODEL", "").strip()
        if not path or not os.path.isdir(path):
            raise RuntimeError("FASTER_WHISPER_MODEL not found")

        print(f"[FasterWhisper] Loading model from: {path}")

        cls._model = WhisperModel(
            model_size_or_path=path,
            device="cpu",
            compute_type="int8"  # FASTEST + small RAM
        )

    def _amp(self, data):
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        lvl = min(1.0, abs(arr).mean() / 16000)
        return int(lvl * 100)

    def listen_once(self):
        buf = []
        silence = 0
        speaking = False

        for _ in range(200):
            data = self.stream.read(self.chunk, exception_on_overflow=False)

            if self.on_level:
                self.on_level(self._amp(data))

            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            vol = abs(arr).mean()

            if not speaking:
                if vol > 200:     # start talking
                    speaking = True
                    buf.append(arr)
            else:
                buf.append(arr)
                if vol < 100:
                    silence += 1
                    if silence > 10:  # end of speech
                        break

        if not buf:
            return ""

        audio = np.concatenate(buf) / 32768.0

        segments, _ = self._model.transcribe(audio, beam_size=1)
        return " ".join([seg.text for seg in segments]).strip()

    def pause(self):
        try: self.stream.stop_stream()
        except: pass

    def resume(self):
        try: self.stream.start_stream()
        except: pass

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()
        except:
            pass
