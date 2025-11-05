import os
import time
from typing import Optional, Callable

import numpy as np
import pyaudio
from faster_whisper import WhisperModel


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except Exception:
        return default


class WhisperCommandRecognizer:
    """Record one utterance (speech until pause) and return its transcription text."""

    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
        sample_rate: int = 16000,
        frame_ms: int = 30,
        start_threshold: float = 0.015,  # amplitude to detect speech start
        silence_ms: int = 700,           # trailing silence to stop
        max_seconds: float = 8.0,
        min_seconds: float = 0.3,
        language: Optional[str] = "en",
        on_level: Optional[Callable[[int], None]] = None,
        input_device_index: Optional[int] = None,   # can be provided by caller
    ):
        self.sample_rate = sample_rate
        self.frame_samples = int(sample_rate * (frame_ms / 1000.0))
        self.start_threshold = start_threshold
        self.silence_frames_to_stop = max(1, int(silence_ms / frame_ms))
        self.max_frames = int((max_seconds * sample_rate) / self.frame_samples)
        self.min_frames = int((min_seconds * sample_rate) / self.frame_samples)
        self.language = language
        self.on_level = on_level

        # Device index: prefer explicit arg, else env, else default.
        env_idx = os.getenv("WHISPER_INPUT_DEVICE_INDEX", "").strip()
        self.input_device_index = (
            input_device_index
            if input_device_index is not None
            else (int(env_idx) if env_idx.isdigit() else None)
        )

        # ---- Model selection (local dir wins) ----
        local_dir = (os.getenv("WHISPER_LOCAL_DIR", "") or "").strip()
        model_id = local_dir if (local_dir and os.path.isdir(local_dir)) else (os.getenv("WHISPER_MODEL", model_size) or model_size)
        compute = os.getenv("WHISPER_COMPUTE", compute_type) or compute_type
        threads = _env_int("WHISPER_THREADS", 4)
        dev = os.getenv("WHISPER_DEVICE", device) or device

        # Model
        self._model = WhisperModel(
            model_id,
            device=dev,
            compute_type=compute,
            cpu_threads=threads,
        )

        # Audio IO
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._open_stream()

    def _open_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.frame_samples,
            input_device_index=self.input_device_index,
        )

    def close(self):
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            self._pa.terminate()
        except Exception:
            pass

    def _amp(self, frame_bytes: bytes) -> float:
        f = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return float(np.mean(np.abs(f)))

    def _amp_level_int(self, frame_bytes: bytes) -> int:
        amp = self._amp(frame_bytes)  # 0..~1
        return int(max(0.0, min(1.0, amp * 3.0)) * 100)

    def listen_once(self) -> str:
        buf = bytearray()
        speaking = False
        silence_count = 0
        frames = 0

        while frames < self.max_frames:
            if self._stream is None:
                self._open_stream()
            try:
                data = self._stream.read(self.frame_samples, exception_on_overflow=False)
            except OSError:
                self._open_stream()
                continue

            frames += 1
            amp = self._amp(data)

            if self.on_level:
                try:
                    self.on_level(self._amp_level_int(data))
                except Exception:
                    pass

            if not speaking:
                if amp >= self.start_threshold:
                    speaking = True
                    buf.extend(data)
                else:
                    continue
            else:
                buf.extend(data)
                if amp < self.start_threshold:
                    silence_count += 1
                    if silence_count >= self.silence_frames_to_stop and frames >= self.min_frames:
                        break
                else:
                    silence_count = 0

        if not buf:
            return ""

        audio = np.frombuffer(bytes(buf), dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=True,
            without_timestamps=True,
        )
        text = "".join(seg.text for seg in segments).strip()
        return text
