import os, pathlib, time, numpy as np, soundfile as sf
from .recorder import record_seconds
from .svm_auth import enroll_svm, SR

OUT = os.getenv("VOICE_MODEL_PATH", "voice_auth_svm.joblib")
SAMPLES = int(os.getenv("AUTH_ENROLL_SAMPLES", "5"))

def main():
    tmpdir = pathlib.Path(".voice_enroll_tmp")
    tmpdir.mkdir(exist_ok=True)
    paths = []
    print(f"Enrollment: record {SAMPLES} short samples. Speak naturally each time.")
    for i in range(SAMPLES):
        input(f"\n[{i+1}/{SAMPLES}] Press Enter and start speaking…")
        y = record_seconds(1.6)
        p = tmpdir / f"enroll_{i+1}.wav"
        sf.write(p.as_posix(), y, SR)
        paths.append(p.as_posix())
        print(f"Saved: {p.name}")
        time.sleep(0.4)
    enroll_svm(paths, OUT)
    print(f"\nEnrollment done. Model → {OUT}")

if __name__ == "__main__":
    main()
