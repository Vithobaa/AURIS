# src/voice_auth/svm_auth.py
import os
import numpy as np
import soundfile as sf
from joblib import dump, load
from python_speech_features import mfcc
from sklearn.svm import OneClassSVM

SR = 16000
N_MFCC = 20
MODEL_PATH = "voice_auth_svm.joblib"

# ---------------- FEATURE EXTRACTION ----------------
def extract_mfcc_features(y: np.ndarray, sr: int = SR) -> np.ndarray:
    """
    Extract MFCC features, keeping the temporal dimension.
    Returns shape: (n_frames, N_MFCC)
    """
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    
    # Extract MFCCs
    feats = mfcc(y, sr, numcep=N_MFCC, nfft=512)
    return feats

def get_speaker_features(wav_paths):
    """
    Computes all MFCC frames across all recorded samples to train the SVM.
    """
    all_frames = []
    for p in wav_paths:
        y_, sr = sf.read(p)
        frames = extract_mfcc_features(y_, sr)
        all_frames.append(frames)
        
    stacked_frames = np.vstack(all_frames)
    return stacked_frames

# ---------------- ENROLLMENT ----------------
def enroll_svm(wav_paths, model_path=MODEL_PATH):
    """
    Enroll the speaker by training a One-Class Support Vector Machine 
    over all MFCC frames collected across the noise conditions.
    """
    print(f"Extracting features from {len(wav_paths)} audio samples...")
    X = get_speaker_features(wav_paths)

    print(f"Training MFCC-SVM (OneClassSVM) on {len(X)} linguistic frames...")
    # 'nu' acts as an upper bound on fraction of margin errors (outliers in training set).
    # Since we strictly control training voice, we set this low. But not too low 
    # so we still map a tight boundary.
    svm = OneClassSVM(kernel='rbf', gamma='scale', nu=0.05)
    svm.fit(X)
    
    dump(svm, model_path)
    print(f"[Enroll] MFCC-SVM model saved -> {model_path}")
    return svm

# ---------------- VERIFICATION ----------------
def verify_svm(sample_wave: np.ndarray, model_path=MODEL_PATH, threshold=0.60):
    """
    Verify the voice using the trained MFCC-SVM. 
    It evaluates the anomaly score for every frame via decision_function.
    Return (ok, confidence, threshold)
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No SVM model found at {model_path}")

    model = load(model_path)
    feats = extract_mfcc_features(sample_wave, SR)
    
    if len(feats) == 0:
        return False, 0.0, threshold
        
    # Predict distances from the supporting plane. 
    # Positive scores imply inlier (you). Negative scores imply outlier (impostor/wrong background).
    scores = model.decision_function(feats)
    
    # Calculate robust mean of frame scores
    mean_score = float(np.mean(scores))
    
    # Standardize the unbounded decision values into a 0.0-1.0 confidence score 
    # using a sigmoid activation slope of 2.0. If score=0, conf=0.5.
    confidence = 1.0 / (1.0 + np.exp(-mean_score * 2.0))
    
    ok = confidence >= threshold
    
    return ok, confidence, threshold
