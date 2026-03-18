import requests
import json

try:
    r = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
    r.raise_for_status()
    models = r.json().get("models", [])
    print(f"Found {len(models)} models:")
    for m in models:
        print(f" - {m['name']}")
except Exception as e:
    print(f"Error checking Ollama: {e}")
