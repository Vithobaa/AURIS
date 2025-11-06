# AURIS
AURIS — AI Voice Desktop Assistant

Auris is a privacy-first desktop voice assistant built in Python. It runs offline using local models (Whisper STT, Ollama LLMs), supports wake word, speaker verification (MFCC+SVM), and a modern Tkinter/ttkbootstrap UI. Torque executes desktop tasks (open apps, control volume, tell time, jokes) and can answer factual questions via Wikipedia.

Features

Wake word (“Hey Torque”) with sleep/active states

Speaker verification: MFCC + SVM (enroll & verify flow)

Hybrid intelligence

Offline: local Whisper STT + local LLM via Ollama

Online (optional): Wikipedia summaries for factual Q&A

Natural command handling: intent router + LLM planner

TTS responses (pyttsx3 / OS TTS)

Modern UI (Tkinter + ttkbootstrap): status, captions, log, mic bar, hot actions

Pluggable tools: open/close apps, volume, time/date, jokes, app indexing

Configurable & portable: .env + JSON config

TASE (planned): Torque Adaptive Setup Engine to auto-detect hardware and pick the best local LLM model

AND I REQUEST YOU TO CREATE A PROJECT FOLDER LIKE THIS GIVEN BELOW:
torque/
├─ src/
│  ├─ main.py                # Orchestrator (wake → auth → stt → intent → act → tts)
│  ├─ intent_router.py       # Pattern rules + router to tools / wiki / planner
│  ├─ whisper_listener.py    # Whisper-based STT (chunks, captions)
│  ├─ pvporcupine.py         # Wake word detector (optional if using Whisper trigger)
│  ├─ tts_local.py           # TTS wrapper (pyttsx3 / SAPI)
│  ├─ system_tools.py        # Open apps, volume, time, jokes, app indexing
│  ├─ tools/
│  │   └─ wiki_tool.py       # Wikipedia summaries (optional)
│  ├─ ai/
│  │   └─ planner.py         # Ollama LLM planner (intent->tool JSON)
│  └─ voice_auth/
│      ├─ recorder.py        # Mic capture for enroll/verify
│      ├─ svm_auth.py        # MFCC + SVM train/verify
│      ├─ enroll.py          # CLI enrollment
│      └─ enroll_ui.py       # GUI enrollment
├─ models/                   # (kept out of git; downloaded on demand)
├─ scripts/
│  └─ download_models.py     # (optional) fetch models from remote
├─ .env.example
├─ requirements.txt
├─ README.md
└─ LICENSE
