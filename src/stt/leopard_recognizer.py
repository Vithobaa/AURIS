
import os
import time
import numpy as np
import sounddevice as sd

try:
    import noisereduce as nr
    # _HAS_NR = True
    # Disable NR for speed (user requested lower latency)
    _HAS_NR = False
except ImportError:
    _HAS_NR = False
    print("[Leopard] 'noisereduce' not found. Noise reduction disabled.")

from pvleopard import create


class LeopardRecognizer:
    """
    Optimized Leopard Offline STT
    - Faster reaction time
    - Better accuracy via:
        * Noise reduction (optional)
        * Gain normalization
        * VAD-based buffering
        * Start-padding fix
    """

    def __init__(
        self,
        on_level=None,
        device_index=None,
        sample_rate=16000,
        frame_ms=30,
        start_threshold=4,        # more sensitive
        silence_threshold=3,      # slightly below start threshold
        silence_ms=250,           # faster stop → lower latency
        min_seconds=0.2,         # accept short commands
        max_seconds=6.0,          # limit long recordings
        language="en"
    ):
        self.on_level = on_level
        self.sample_rate = sample_rate
        self.frame_samples = int(sample_rate * (frame_ms / 1000.0))
        self.start_threshold = start_threshold
        self.silence_threshold = silence_threshold
        self.silence_frames_to_stop = max(1, int(silence_ms / frame_ms))
        self.min_frames = int((min_seconds * sample_rate) / self.frame_samples)
        self.max_frames = int((max_seconds * sample_rate) / self.frame_samples)

        self.language = language

        # ---------------------------
        #  Leopard Engine
        # ---------------------------
        key = os.getenv("PICOVOICE_LEOPARD_KEY", "").strip()
        if not key:
            raise RuntimeError("PICOVOICE_LEOPARD_KEY missing in .env")

        self.engine = None
        for attempt in range(3):
            try:
                self.engine = create(access_key=key)
                break
            except Exception as e:
                print(f"[Leopard] Initialization attempt {attempt+1} failed: {e}")
                time.sleep(0.15)
                
        if not self.engine:
            raise RuntimeError("Failed to initialize Leopard engine after 3 attempts.")

        # ---------------------------
        # Audio System (SoundDevice)
        # ---------------------------
        self.device_index = device_index
        # We will create the stream on demand or keep it open?
        # PyAudio allows explicit open. SD is similar.
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=self.frame_samples,
            device=self.device_index
        )
        self._stream.start()

    # ============================================================
    # Helper: compute mic level (0–100)
    # ============================================================
    def _amp_level(self, frame_int16: np.ndarray) -> int:
        # frame_int16 is already int16 numpy array
        f = frame_int16.astype(np.float32) / 32768.0
        amp = float(np.mean(np.abs(f)))  
        return int(min(1.0, amp * 3.0) * 100)

    # ============================================================
    # READ AUDIO UNTIL USER FINISHES SPEAKING
    # ============================================================
    def listen_once(self) -> str:
        if self._stream is None:
            return ""

        speaking = False
        silence_count = 0
        frames = 0
        buf = [] # list of numpy arrays

        try:
            # Do NOT auto-restart stream here. 
            # If it is paused (inactive), we should respect that or throw/return.
            if not self._stream.active:
                # If stream is inactive, we can't read. 
                # Should we return empty immediately?
                # Yes, returning empty lets the loop check for typing_busy_evt.
                return ""
        except:
            pass

        while frames < self.max_frames:
            try:
                # Read one frame
                # sd read returns (data, overflow)
                data, overflow = self._stream.read(self.frame_samples)
                if overflow:
                    pass
            except Exception as e:
                # Suppress "Stream is stopped" (PaErrorCode -9983) which happens on valid shutdown
                if "Stream is stopped" in str(e) or "-9983" in str(e):
                    break
                print("[Leopard] Stream read error:", e)
                break

            # data is (frames, channels) e.g. (512, 1) result is 2D
            frame = data.flatten() # 1D int16 array
            
            frames += 1

            # UI mic level update
            if self.on_level:
                try:
                    self.on_level(self._amp_level(frame))
                except:
                    pass

            # VAD check
            f_float = frame.astype(np.float32)
            amp_int = np.mean(np.abs(f_float)) # mean abs of int16 values

            # Scale amp to match previous PyAudio threshold logic (approx)
            # PyAudio bytes -> frombuffer -> mean(abs) 
            # If start_threshold=4 means int16 value ~4 (very sensitive?)
            # Or 4%? The original code did:
            # f = frombuffer(frame)...; amp = mean(abs(f))
            # Wait, original code:
            # f = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
            # amp = np.mean(np.abs(f))
            # Yes, so 'amp' is mean absolute value of int16 samples.
            
            # --------------------------
            # VAD START
            # --------------------------
            if not speaking:
                if amp_int >= self.start_threshold:
                    speaking = True
                    buf.append(frame)
            else:
                buf.append(frame)

                # VAD STOP condition
                if amp_int < self.silence_threshold:
                    silence_count += 1
                    if silence_count >= self.silence_frames_to_stop and frames >= self.min_frames:
                        break
                else:
                    silence_count = 0

        # No speech captured
        if not buf:
            return ""

        # ============================================================
        # PROCESS AUDIO CLEANING
        # ============================================================
        
        # Concatenate all frames
        if not buf:
            return ""
        
        pcm = np.concatenate(buf).astype(np.float32)

        # Step 1: Noise Reduction (major accuracy boost)
        if _HAS_NR:
            try:
                pcm = nr.reduce_noise(y=pcm, sr=self.sample_rate)
            except Exception:
                pass

        # Step 2: Gain Normalization (avoids too-quiet speech)
        max_val = np.max(np.abs(pcm))
        if max_val > 0:
            pcm = pcm / max_val

        # Step 3: Restore int16
        pcm_int16 = (pcm * 32767).astype(np.int16)

        # Step 4: Start-padding (fixes Leopard's first-word cut issue)
        pad = np.zeros(1600, dtype=np.int16)  # ~100ms silence
        pcm_int16 = np.concatenate([pad, pcm_int16])

        # Convert to list for pvleopard
        pcm_list = pcm_int16.tolist()

        # ============================================================
        # Run Leopard
        # ============================================================
        try:
            import time
            start = time.time()
            transcript, words = self.engine.process(pcm_list)
            end = time.time()
            print("[MEASURE] STT engine latency:", end - start)
        except Exception as e:
            print("[LeopardRecognizer] process error:", e)
            return ""

        text = transcript.strip()

        # Optional: reject low-confidence transcripts
        if words:
            avg_conf = sum(w.confidence for w in words) / len(words)
            if avg_conf < 0.35:
                return ""

        return text


    # ============================================================
    # ============================================================
    # ============================================================
    # ============================================================
    def pause(self):
        """Pause the audio stream."""
        try:
            if self._stream and self._stream.active:
                self._stream.stop()
        except Exception:
            pass

    def resume(self):
        """Resume the audio stream."""
        try:
            # Re-create stream if closed? No, stop() just pauses.
            # But sounddevice stop() might require start() to resume.
            if self._stream and not self._stream.active:
                self._stream.start()
        except Exception:
            pass

    def close(self):
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except:
            pass
        self._stream = None
        
        if self.engine:
            self.engine.delete()
            self.engine = None

