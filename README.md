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
<img width="214" height="607" alt="image" src="https://github.com/user-attachments/assets/3ddfdc02-b433-40ce-a382-ffdb8d942825" />


---

## ⚙️ Installation (Developer Mode)

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Vithobaa/AURIS.git
cd AURIS
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt (if doesnt work install everything one by one)

Picovoice Setup (Required)

Create a free Picovoice account and obtain an access key.

Add to .env:
PORCUPINE_ACCESS_KEY=your_key_here
PICOVOICE_LEOPARD_KEY=your_key_here
PORCUPINE_KEYWORD_PATH=HEY-TORQUE_en_windows_v3_0_0/HEY-TORQUE_en_windows_v3_0_0.ppn

Ollama Setup (Offline LLM)
Run:
python installer/ollama_installer.py
This will:
Detect system hardware
Install Ollama
Pull optimal local LLM
Configure .env automatically

then run auris
>> python main.py

