# AURIS – Offline Voice Assistant for Desktop Systems

AURIS is a **fully offline-capable desktop voice assistant** designed for privacy-preserving, low-latency human–computer interaction.  
It integrates **wake-word detection**, **speaker verification**, **offline speech-to-text**, **local AI planning**, and **system-level automation** without relying on cloud-based speech services.

> 🎯 Built as a research-focused system suitable for academic publication and real-world deployment.

---

## 🔑 Key Features

### 🎤 Wake Word Detection
- Uses **Picovoice Porcupine**
- Custom wake-word support via `.ppn` files
- Low CPU usage, always-on listening

### 🧠 Offline Speech-to-Text (STT)
- Uses **Picovoice Leopard**
- No acoustic model downloads required
- Processes raw microphone PCM data locally
- Works fully offline after setup

### 🔐 Speaker Verification (Voice Biometrics)
- MFCC feature extraction
- SVM-based classifier
- Prevents unauthorized access
- Automatic enrollment on first run

### 🤖 Local AI Reasoning (Planner)
- Uses **Ollama (local LLM runtime)**
- Hardware-aware model fallback chain
- Structured JSON tool routing
- Zero cloud dependency

### 🖥️ System Control (Windows)
- Open / close applications
- Control system volume
- Wi-Fi ON / OFF / scan / connect
- Time, jokes, system queries

### 🪟 Desktop UI
- Built with Tkinter
- Floating, lightweight assistant window
- No browser or Electron dependency

---

## 🧩 System Architecture

