import requests
import json
import os

model = "qwen2.5:7b-instruct-q5_K_M"
url = "http://127.0.0.1:11434/api/chat"

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Hello, are you working?"}],
    "stream": False
}

print(f"Testing chat with model: {model}...")
try:
    r = requests.post(url, json=payload, timeout=60)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text[:200]}...") 
except Exception as e:
    print(f"Chat failed: {e}")
