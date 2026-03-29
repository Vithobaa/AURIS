import sys
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.ai.planner import plan
import json

if __name__ == "__main__":
    result = plan("can you open the browser")
    print("\n[DEBUG] Final Planner output:")
    print(json.dumps(result, indent=2))
