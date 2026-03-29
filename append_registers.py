import os

mapping = {
    "system_tools.py": '''

def register(router, tool_map):
    router.add_intent("open_app", ["open notepad", "launch calculator", "start the browser", "open file explorer", "open my files", "start chrome", "open spotify", "open browser", "launch browser"], open_app)
    router.add_intent("close_app", ["close chrome", "quit edge", "exit notepad", "close visual studio code", "kill spotify", "stop browser", "close browser", "quit browser"], close_app)
    router.add_intent("rescan_apps", ["rescan apps", "scan apps", "rebuild app index", "refresh apps"], rescan_apps)
    router.add_intent("close_all_apps", ["close all the apps", "close everything you opened", "close all apps", "shut everything you started"], close_all_apps)
    router.add_intent("list_apps", ["what apps can you open", "what can you open", "list apps", "show installed apps", "which apps can you launch"], list_available_apps)
    router.add_intent("set_volume", ["set volume to 50%", "volume 30", "increase volume to 80", "decrease volume to 20", "set the volume to 100", "volume to 10", "now to 50"], set_volume)
    router.add_intent("get_time", ["what time is it", "tell me the time", "current time", "what day is it", "date today"], get_time)
    router.add_intent("tell_joke", ["tell me a joke", "make me laugh", "joke please", "say a joke"], tell_joke)

    tool_map.update({
        "open_app": open_app, "close_app": close_app,
        "rescan_apps": rescan_apps, "close_all_apps": close_all_apps,
        "list_apps": list_available_apps, "set_volume": set_volume,
        "get_time": get_time, "tell_joke": tell_joke
    })
''',
    "wifi_tools.py": '''

def register(router, tool_map):
    router.add_intent("wifi_on", ["turn on wifi", "enable wifi", "wifi on"], lambda _t: wifi_on())
    router.add_intent("wifi_off", ["turn off wifi", "disable wifi", "wifi off"], lambda _t: wifi_off())
    router.add_intent("wifi_list", ["list wifi", "scan wifi", "show wifi", "wifi networks", "list out the wifi"], lambda _t: list_wifi())
    router.add_intent("wifi_connect", ["connect to wifi", "connect wifi", "connect to network"], lambda _t: "")

    tool_map.update({
        "wifi_on": wifi_on, "wifi_off": wifi_off,
        "list_wifi": list_wifi, "connect_wifi": connect_wifi_by_number
    })
''',
    "weather.py": '''

def register(router, tool_map):
    router.add_intent("weather", ["weather in", "weather for", "check weather", "forecast"], lambda t: get_weather(t.replace("weather in","").replace("weather for","").replace("check weather","").replace("forecast","").strip()))
    tool_map.update({ "weather": get_weather })
''',
    "web_search.py": '''

def register(router, tool_map):
    router.add_intent("web_search", ["search for", "web search", "google", "look up", "find online"], lambda t: search_web(t.replace("search for","").replace("web search","").replace("google","").replace("look up","").replace("find online","").strip()))
    tool_map.update({ "web_search": search_web })
''',
    "media.py": '''

def register(router, tool_map):
    router.add_intent("media_play_pause", ["play music", "pause music", "stop music", "resume music", "toggle play"], media_play_pause)
    router.add_intent("media_next", ["next song", "skip song", "next track", "skip track"], media_next)
    router.add_intent("media_prev", ["previous song", "last song", "previous track", "go back a song"], media_prev)
    
    tool_map.update({
        "media_play_pause": media_play_pause,
        "media_next": media_next,
        "media_prev": media_prev
    })
''',
    "files.py": '''

def register(router, tool_map):
    tool_map.update({ "list_files": list_files, "read_file": read_file })
''',
    "advanced_tools.py": '''

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
''',
    "bluetooth_tools.py": '''

def register(router, tool_map):
    router.add_intent("bluetooth_on", ["turn on bluetooth", "enable bluetooth", "start bluetooth"], bluetooth_on)
    router.add_intent("bluetooth_off", ["turn off bluetooth", "disable bluetooth", "stop bluetooth"], bluetooth_off)
    router.add_intent("list_bluetooth", ["list bluetooth devices", "show bluetooth", "scan for bluetooth", "available bluetooth"], list_bluetooth)
    router.add_intent("connect_bluetooth", ["connect to bluetooth", "pair bluetooth", "connect bluetooth speaker"], connect_bluetooth)

    tool_map.update({
        "bluetooth_on": bluetooth_on, "bluetooth_off": bluetooth_off,
        "list_bluetooth": list_bluetooth, "connect_bluetooth": connect_bluetooth
    })
'''
}

for fname, content in mapping.items():
    path = os.path.join(r"c:\Users\vitho\Downloads\auris\src\tools", fname)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if "def register(" not in existing:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            print(f"Appended to {fname}")
        else:
            print(f"Skipped {fname} (already has register)")
