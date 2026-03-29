import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.join(BASE_DIR, "src") not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

# Force use of llama3.2:3b
os.environ["OLLAMA_MODEL"] = "llama3.2:3b"

from src.ai.planner import plan

if __name__ == "__main__":
    print("[TEST] Sending 'can you open the browser' to llama3.2:3b...")
    p = plan("can you open the browser")
    print("\nResult:")
    print(p)
