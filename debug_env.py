import sys
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv
load_dotenv()

from src.ai.planner import _models_chain, _model_exists
import requests

def debug():
    url = "http://127.0.0.1:11434"
    print("OLLAMA_MODEL from env:", os.getenv("OLLAMA_MODEL"))
    models = _models_chain()
    print("Models Chain:", models)
    try:
        r = requests.get(f"{url}/api/tags", timeout=6)
        r.raise_for_status()
        tags = r.json().get("models", [])
        print("\nAll Ollama Tag Names:")
        for t in tags:
            print(f"- '{t.get('name')}'")
    except Exception as e:
        print("Error fetching tags:", e)

    print("\nModel Exists Check:")
    for m in models:
        print(f"'{m}':", _model_exists(url, m))

if __name__ == "__main__":
    debug()
