# src/voice_auth/svm_auth.py
import os
import numpy as np
import soundfile as sf
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from joblib import dump, load
from python_speech_features import mfcc
from pathlib import Path

SR = 16000
N_MFCC = 20
MODEL_PATH = "voice_auth_svm.joblib"

# ---------------- FEATURE EXTRACTION ----------------
def extract_mfcc_features(y: np.ndarray, sr: int = SR) -> np.ndarray:
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    feats = mfcc(y, sr, numcep=N_MFCC, nfft=512)
    # mean & std normalize
    feats = (feats - np.mean(feats, axis=0)) / (np.std(feats, axis=0) + 1e-8)
    return np.mean(feats, axis=0)

# ---------------- ENROLLMENT ----------------
def enroll_svm(wav_paths, model_path=MODEL_PATH):
    """
    wav_paths: list of file paths for YOUR samples (positive)
    We also generate simple 'negative' noise-like samples automatically.
    """
    X, y = [], []

    # Positive samples (your voice)
    for p in wav_paths:
        y_, sr = sf.read(p)
        X.append(extract_mfcc_features(y_, sr))
        y.append(1)

    # Synthetic 'negative' samples for background / impostor noise
    for _ in range(len(wav_paths) * 2):
        noise = np.random.normal(0, 0.5, SR * 2)
        X.append(extract_mfcc_features(noise, SR))
        y.append(0)

    X, y = np.array(X), np.array(y)

    # Normalize and train SVM
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    clf = SVC(kernel='rbf', probability=True, C=10, gamma='scale')
    clf.fit(Xs, y)

    model = {"svm": clf, "scaler": scaler}
    dump(model, model_path)
    print(f"[Enroll] SVM model saved → {model_path}")
    return model

# ---------------- VERIFICATION ----------------
def verify_svm(sample_wave: np.ndarray, model_path=MODEL_PATH, threshold=0.50):
    """
    Return (ok, prob, threshold)
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No SVM model found at {model_path}")

    model = load(model_path)
    clf, scaler = model["svm"], model["scaler"]

    feats = extract_mfcc_features(sample_wave, SR).reshape(1, -1)
    feats = scaler.transform(feats)

    prob = clf.predict_proba(feats)[0][1]  # probability of "your voice"
    ok = prob >= threshold
    return ok, float(prob), threshold
    

