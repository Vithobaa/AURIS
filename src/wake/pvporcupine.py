import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*", category=UserWarning)

import struct
import threading
import collections
from typing import Callable, Optional

import numpy as np
# import pyaudio
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
        try:
            if self.keyword_path:
                print(f"[Porcupine] Loading keyword file: {self.keyword_path}")
                return pvporcupine.create(access_key=self.access_key, keyword_paths=[self.keyword_path])
        except Exception as e:
            print(f"[Porcupine] Failed to load custom keyword: {e}. Falling back to default 'jarvis'.")
        
        if self.keyword:
            try:
                return pvporcupine.create(access_key=self.access_key, keywords=[self.keyword])
            except: pass

        return pvporcupine.create(access_key=self.access_key, keywords=["porcupine"])

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
        try:
            porcupine = self._create_engine()
        except Exception as e:
            print("[WAKE] Failed to create Porcupine:", e)
            return

        import sounddevice as sd
        
        # Porcupine requires raw PCM (int16)
        blocksize = porcupine.frame_length
        dtype = 'int16'
        
        # Maintain a rolling buffer of exactly 2.5 seconds of audio
        buffer_seconds = 2.5
        max_blocks = int((buffer_seconds * porcupine.sample_rate) / blocksize)
        audio_buffer = collections.deque(maxlen=max_blocks)
        
        try:
            with sd.InputStream(
                samplerate=porcupine.sample_rate,
                channels=1,
                dtype=dtype,
                blocksize=blocksize,
                device=self.device_index
            ) as stream:
                
                while not self._stop.is_set():
                    # Read exactly one frame
                    data, overflowed = stream.read(blocksize)
                    if overflowed:
                        # ignore overflow for now
                        pass
                    
                    # 'data' is a numpy array of shape (512, 1) usually
                    # flatten it to 1D
                    pcm = data.flatten()
                    
                    # Append strictly to our rolling timeframe window
                    audio_buffer.append(pcm)

                    # update mic level in UI (optional)
                    if self.on_level:
                        try:
                            # Convert int16 to float level 0..100
                            # This mimics _amp_level_int but using existing numpy array
                            f = pcm.astype(np.float32) / 32768.0
                            amp = float(np.mean(np.abs(f)))
                            level = int(max(0.0, min(1.0, amp * 3.0)) * 100)
                            self.on_level(level)
                        except Exception:
                            pass

                    try:
                        result = porcupine.process(pcm)
                        if result >= 0:
                            import time; print("[MEASURE] Wake word detected at:", time.time())
                            
                            # Wake word detected: Snapshot the rolling buffer
                            full_audio_int16 = np.concatenate(audio_buffer)
                            # Convert to normalized float32 format expected by extractors
                            full_audio_float32 = full_audio_int16.astype(np.float32) / 32768.0
                            
                            try:
                                # First, try passing the audio data to the callback
                                self.on_detect(full_audio_float32)
                            except TypeError:
                                # Fallback if original callback takes no arguments
                                try: self.on_detect()
                                except: pass
                                
                    except Exception as e:
                        print(f"[WAKE] Process error: {e}")
                        break
                        
        except Exception as e:
            print("[WAKE] Stream error:", e)
        finally:
            porcupine.delete()

