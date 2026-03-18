# test_svm_offline.py
import numpy as np
import soundfile as sf
import os
import shutil
from src.voice_auth.svm_auth import enroll_svm, verify_svm, SR, MODEL_PATH

def generate_tone(freq, duration, sr=SR):
    t = np.linspace(0, duration, int(sr * duration), False)
    # Generate a complex tone to act somewhat like speech formants
    tone = np.sin(freq * t * 2 * np.pi) + 0.5 * np.sin(freq * 2 * t * 2 * np.pi) + 0.25 * np.sin(freq * 3 * t * 2 * np.pi)
    return tone

def main():
    print("--- Voice Auth Offline Test ---")
    tmp_dir = "test_audio_tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    
    # 1. Create simulated User Voice (Frequency Base: 400Hz)
    user_paths = []
    print("Generating simulated user voice (400Hz base)...")
    for i in range(5):
        audio = generate_tone(400 + i*10, 2.0)
        path = os.path.join(tmp_dir, f"user_enroll_{i}.wav")
        sf.write(path, audio, SR)
        user_paths.append(path)
        
    # 2. Enroll User
    print("\nEnrolling user...")
    enroll_svm(user_paths, model_path=MODEL_PATH)
    
    # 3. Test Verify with User Voice (Should Pass)
    print("\nTesting Verification with User Voice...")
    user_test = generate_tone(405, 2.0)
    ok, score, th = verify_svm(user_test, MODEL_PATH, threshold=0.05)
    print(f"User Voice Result: {'PASSED' if ok else 'FAILED'} (Score: {score:.3f}, Required: >={th:.3f})")
    assert ok, "User voice was rejected!"
    
    # 4. Test Verify with Impostor Voice (Frequency Base: 800Hz)
    print("\nTesting Verification with Impostor Voice (800Hz base)...")
    impostor_test = generate_tone(800, 2.0)
    ok, score, th = verify_svm(impostor_test, MODEL_PATH, threshold=0.05)
    print(f"Impostor Voice Result: {'PASSED' if ok else 'FAILED'} (Score: {score:.3f}, Required: >={th:.3f})")
    assert not ok, "Impostor voice was improperly accepted!"
    
    # 5. Clean up
    print("\nCleaning up temporary files...")
    shutil.rmtree(tmp_dir)
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
    print("Offline tests passed successfully!")

if __name__ == "__main__":
    main()
