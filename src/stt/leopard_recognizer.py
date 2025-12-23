import os
import time
import numpy as np
import pyaudio
import noisereduce as nr

from pvleopard import create


class LeopardRecognizer:
    """
    Optimized Leopard Offline STT
    - Faster reaction time
    - Better accuracy via:
        * Noise reduction
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
        start_threshold=4,        # more sensitive (previously 6)
        silence_threshold=3,      # slightly below start threshold
        silence_ms=450,           # faster stop → lower latency
        min_seconds=0.25,         # accept short commands
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

        self.engine = create(access_key=key)

        # ---------------------------
        # Audio System
        # ---------------------------
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=self.frame_samples,
            input_device_index=device_index
        )

    # ============================================================
    # Helper: compute mic level (0–100)
    # ============================================================
    def _amp_level(self, frame_bytes: bytes) -> int:
        data = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
        amp = np.mean(np.abs(data)) / 32768.0
        return int(min(1.0, amp * 3.0) * 100)

    # ============================================================
    # READ AUDIO UNTIL USER FINISHES SPEAKING
    # ============================================================
    def listen_once(self) -> str:
        speaking = False
        silence_count = 0
        frames = 0
        buf = bytearray()

        while frames < self.max_frames:
            try:
                frame = self._stream.read(self.frame_samples, exception_on_overflow=False)
            except OSError:
                continue

            frames += 1

            # UI mic level update
            if self.on_level:
                try:
                    self.on_level(self._amp_level(frame))
                except:
                    pass

            # Convert audio chunk for RMS check
            f = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
            amp = np.mean(np.abs(f))

            # --------------------------
            # VAD START
            # --------------------------
            if not speaking:
                if amp >= self.start_threshold:
                    speaking = True
                    buf.extend(frame)
            else:
                buf.extend(frame)

                # VAD STOP condition
                if amp < self.silence_threshold:
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

        pcm = np.frombuffer(bytes(buf), dtype=np.int16).astype(np.float32)

        # Step 1: Noise Reduction (major accuracy boost)
        pcm = nr.reduce_noise(y=pcm, sr=self.sample_rate)

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
    def close(self):
        try:
            self._stream.stop_stream()
            self._stream.close()
        except:
            pass
        try:
            self._pa.terminate()
        except:
            pass
