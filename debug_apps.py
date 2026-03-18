from src.tools.system_tools import rescan_apps, list_available_apps, open_app, _APPS
import os

print("--- Testing App Indexer ---")
if not os.path.exists("src/apps/indexer.py"):
    print("Error: Run this from project root.")
    exit(1)

print("1. Rescanning apps...")
print(rescan_apps())

print("\n2. Listing available apps (sample)...")
print(list_available_apps())

print("\n3. Testing 'open_app' lookup for 'notepad'...")
# We use a dry run query - open_app would normally launch it.
# We will just print the result string.
print(open_app("notepad"))

print("\n4. Testing 'open_app' lookup for 'calculator'...")
print(open_app("calculator"))

print("\nDone.")
