# src/voice_auth/svm_auth.py
import os
import numpy as np
import soundfile as sf
from joblib import dump, load
from python_speech_features import mfcc
from scipy.spatial.distance import cosine

SR = 16000
N_MFCC = 20
# Keeping the same filename for compatibility with the rest of the app, 
# although internally we are using centroid distance now for robustness.
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

def get_speaker_embedding(wav_paths):
    """
    Computes a single d-vector style embedding (the mean vector of all MFCC frames)
    representing the authorized speaker.
    """
    all_frames = []
    for p in wav_paths:
        y_, sr = sf.read(p)
        frames = extract_mfcc_features(y_, sr)
        all_frames.append(frames)
        
    stacked_frames = np.vstack(all_frames)
    
    # The speaker embedding is just the average of all CMS-normalized MFCC frames
    embedding = np.mean(stacked_frames, axis=0)
    
    return embedding

# ---------------- ENROLLMENT ----------------
def enroll_svm(wav_paths, model_path=MODEL_PATH):
    """
    Enroll the speaker by computing their average MFCC embedding.
    """
    print("Computing speaker embedding...")
    embedding = get_speaker_embedding(wav_paths)

    model = {"embedding": embedding}
    dump(model, model_path)
    print(f"[Enroll] Speaker Embedding model saved -> {model_path}")
    return model

# ---------------- VERIFICATION ----------------
def verify_svm(sample_wave: np.ndarray, model_path=MODEL_PATH, threshold=0.60):
    """
    Verify the voice using simple L2 distance against the enrolled embedding mean.
    threshold: The minimum acceptable confidence score (0.0 to 1.0)
               Strictly set to 0.60 per user request for tight secure access.
    Return (ok, score, threshold)
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No SVM model found at {model_path}")

    model = load(model_path)
    enrolled_embedding = model["embedding"]

    # Extract features for the new sample
    feats = extract_mfcc_features(sample_wave, SR)
    
    if len(feats) == 0:
        return False, 0.0, threshold
        
    # Compute the embedding for the sample
    sample_embedding = np.mean(feats, axis=0)

    # Compute Euclidean distance (L2)
    dist = float(np.linalg.norm(enrolled_embedding - sample_embedding))

    # Map L2 distance to a 0.0 - 1.0 "confidence score" for the UI
    max_dist = 60.0
    confidence = max(0.0, 1.0 - (dist / max_dist))
    
    # We want confidence to be GREATER THAN OR EQUAL TO the required threshold
    ok = confidence >= threshold
    
    return ok, confidence, threshold
