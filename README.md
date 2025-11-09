# AURIS (In progress)
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
<img width="892" height="716" alt="Screenshot (2)" src="https://github.com/user-attachments/assets/db31cf5b-e7b3-4368-8846-c2b3ebffe61d" />

first create venv folder
  --> install python via windows
  --> create folder structure
  --> run this cmd >> python -m venv venv
  --> then run this cmd >> pip install -r requirement.txt


