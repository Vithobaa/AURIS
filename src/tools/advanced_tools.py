import psutil
import re
import wmi
from duckduckgo_search import DDGS

def check_system(_: str = "") -> str:
    """Returns CPU, RAM, and Battery info."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    battery_info = ""
    try:
        battery = psutil.sensors_battery()
        if battery:
            plugged = "plugged in" if battery.power_plugged else "on battery"
            battery_info = f", and battery is at {battery.percent}% ({plugged})"
    except Exception:
        pass
    return f"System load: CPU {cpu}%, RAM {ram}%{battery_info}."

def set_brightness(user_text: str) -> str:
    """Sets screen brightness (0-100)."""
    m = re.search(r"(\d{1,3})", user_text)
    if not m:
        return "What brightness level should I set?"
    val = max(0, min(100, int(m.group(1))))
    try:
        c = wmi.WMI(namespace='wmi')
        methods = c.WmiMonitorBrightnessMethods()[0]
        methods.WmiSetBrightness(val, 0)
        return f"Screen brightness set to {val}%."
    except Exception as e:
        return f"Could not set window brightness: {e}"

def read_clipboard(_: str = "") -> str:
    """Reads current clipboard text."""
    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        if text:
            # truncate if it's too long to speak
            return f"Clipboard contents: {text[:200]}..." if len(text) > 200 else f"Clipboard contents: {text}"
        return "The clipboard is empty."
    except tk.TclError:
        return "The clipboard is empty or does not contain text."
    except Exception as e:
        return f"Couldn't read clipboard: {e}"

def get_news(_: str = "") -> str:
    """Fetches top 3 news headlines via DDGS."""
    try:
        results = DDGS().news("top world news", max_results=3)
        if results:
            titles = [r.get('title', '') for r in results]
            return "Here is the latest news: " + " ... ".join(titles)
        return "I couldn't find any recent news."
    except Exception as e:
        return f"Error fetching news: {e}"

def take_note(user_text: str) -> str:
    """Takes a quick note and saves it to notes.txt."""
    import os
    # Exclude the activation phrase
    import re
    clean = re.sub(r"^(take a note|write this down|remind me to|save a note that|note that)\s+", "", user_text, flags=re.I)
    if not clean.strip():
        return "What should I write down?"
        
    try:
        with open("notes.txt", "a", encoding="utf-8") as f:
            f.write(f"- {clean.strip()}\n")
        return "Note saved."
    except Exception as e:
        return f"Couldn't save note: {e}"

def set_os_theme(mode: str) -> str:
    """Sets the Windows 10/11 OS theme to dark or light."""
    import winreg
    mode = mode.lower()
    if "dark" in mode:
        theme = 0
    elif "light" in mode:
        theme = 1
    else:
        return "I can only switch to dark mode or light mode."

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, theme)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, theme)
        winreg.CloseKey(key)
        return "Switched to dark theme." if theme == 0 else "Switched to light theme."
    except Exception as e:
        return f"Couldn't change OS theme: {e}"

def open_settings(panel: str = "") -> str:
    """Opens Windows settings panels via ms-settings:."""
    import os
    panel = panel.lower()
    
    # Map common phrases to Windows settings URIs
    uri_map = {
        "display": "display",
        "screen": "display",
        "bluetooth": "bluetooth",
        "network": "network",
        "wifi": "network-wifi",
        "update": "windowsupdate",
        "power": "batterysaver",
        "battery": "batterysaver",
        "sound": "sound",
        "audio": "sound",
        "personalization": "personalization",
        "theme": "personalization-background",
    }
    
    target = "ms-settings:"
    matched = ""
    for key, val in uri_map.items():
        if key in panel:
            target += val
            matched = key
            break
            
    try:
        os.startfile(target)
        if target == "ms-settings:":
            return "Opening Windows Settings."
        return f"Opening Windows {matched.capitalize()} settings."
    except Exception as e:
        return f"Couldn't open settings: {e}"



def register(router, tool_map):
    router.add_intent("check_system", ["check system", "battery status", "how much battery is left", "cpu usage", "system ram", "check the battery"], check_system)
    router.add_intent("set_brightness", ["set brightness", "change screen brightness", "make the screen brighter", "dim the screen", "set brightness to 50", "brightness to 100", "brightness 75", "now to 10"], set_brightness)
    router.add_intent("read_clipboard", ["read clipboard", "what did I copy", "read my copied text"], read_clipboard)
    router.add_intent("get_news", ["news today", "latest news", "what is happening around the world", "top headlines"], get_news)
    router.add_intent("take_note", ["take a note", "write this down", "remember this", "save a note"], take_note)
    router.add_intent("set_os_theme", ["enable dark mode", "turn on dark mode", "switch to light theme", "switch to dark theme", "dark mode", "light mode", "change OS background"], set_os_theme)
    router.add_intent("open_settings", ["open settings", "show display settings", "open windows update", "bluetooth settings", "open network settings", "change settings", "open sound settings", "open wifi settings"], open_settings)

    tool_map.update({
        "check_system": check_system, "set_brightness": set_brightness,
        "read_clipboard": read_clipboard, "get_news": get_news, "take_note": take_note,
        "set_os_theme": set_os_theme, "open_settings": open_settings
    })
