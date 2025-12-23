import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)

import struct
import threading
from typing import Callable, Optional

import numpy as np
import pyaudio
import pvporcupine


def _amp_level_int(samples_int16: bytes) -> int:
    """Mean absolute amplitude → int 0..100 (boosted for UI)."""
    f = np.frombuffer(samples_int16, dtype=np.int16).astype(np.float32) / 32768.0
    amp = float(np.mean(np.abs(f)))  # 0..~1
    return int(max(0.0, min(1.0, amp * 3.0)) * 100)


class WakeWordListener:
    """
    Porcupine-based wake word listener.
    Triggers on_detect() when the keyword is detected. Optional on_level(level 0..100).
    """

    def __init__(
        self,
        access_key: str,
        on_detect: Callable[[], None],
        keyword: Optional[str] = "jarvis",        # built-in keyword
        keyword_path: Optional[str] = None,       # custom .ppn (not needed now)
        device_index: Optional[int] = None,
        on_level: Optional[Callable[[int], None]] = None,
    ):
        if not access_key:
            raise ValueError("PORCUPINE_ACCESS_KEY is required for Porcupine.")
        self.access_key = access_key
        self.on_detect = on_detect
        self.keyword = keyword
        self.keyword_path = keyword_path
        self.device_index = device_index
        self.on_level = on_level

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _create_engine(self):
        if self.keyword_path:
            return pvporcupine.create(access_key=self.access_key, keyword_paths=[self.keyword_path])
        if self.keyword:
            return pvporcupine.create(access_key=self.access_key, keywords=[self.keyword])
        return pvporcupine.create(access_key=self.access_key, keywords=["jarvis"])

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        porcupine = self._create_engine()
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
            input_device_index=self.device_index,
        )
        try:
            while not self._stop.is_set():
                data = stream.read(porcupine.frame_length, exception_on_overflow=False)

                # update mic level in UI (optional)
                if self.on_level:
                    try:
                        self.on_level(_amp_level_int(data))
                    except Exception:
                        pass

                # Porcupine expects a sequence of int16
                pcm = struct.unpack_from("h" * porcupine.frame_length, data)
                result = porcupine.process(pcm)
                if result >= 0:
                    import time; print("[MEASURE] Wake word detected at:", time.time())
                    try:
                        self.on_detect()
                    except Exception:
                        pass
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            pa.terminate()
            porcupine.delete()
