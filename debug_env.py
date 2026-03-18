import sys
import os

print("--- DEBUG INFO ---")
print(f"CWD: {os.getcwd()}")
print(f"sys.executable: {sys.executable}")
print(f"sys.version: {sys.version}")
print("sys.path:")
for p in sys.path:
    print(f"  {p}")

print("\nImport Checks:")
try:
    import numpy
    print(f"numpy: {numpy.__file__}")
except ImportError as e:
    print(f"numpy failed: {e}")

try:
    import pyautogui
    print(f"pyautogui: {pyautogui.__file__}")
except ImportError as e:
    print(f"pyautogui failed: {e}")

try:
    import duckduckgo_search
    print(f"duckduckgo_search: {duckduckgo_search.__file__}")
except ImportError as e:
    print(f"duckduckgo_search failed: {e}")
