import subprocess
import sys
import os

req_file = "requirement.txt"
python_exe = sys.executable

print(f"Using python: {python_exe}")
print(f"Reading {req_file}...")

with open(req_file, "r") as f:
    lines = f.readlines()

failed = []
installed = []

for line in lines:
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    
    print(f"Installing: {line}")
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", line])
        installed.append(line)
        print(f"SUCCESS: {line}")
    except subprocess.CalledProcessError:
        print(f"FAILURE: {line}")
        failed.append(line)

print("\n--- SUMMARY ---")
print(f"Installed: {len(installed)}")
print(f"Failed: {len(failed)}")
for f in failed:
    print(f"  - {f}")
