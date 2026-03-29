import pyautogui

def media_play_pause(_) -> str:
    pyautogui.press("playpause")
    return "Toggled play/pause."

def media_next(_) -> str:
    pyautogui.press("nexttrack")
    return "Skipped to next track."

def media_prev(_) -> str:
    pyautogui.press("prevtrack")
    return "Went back to previous track."


def register(router, tool_map):
    router.add_intent("media_play_pause", ["play music", "pause music", "stop music", "resume music", "toggle play"], media_play_pause)
    router.add_intent("media_next", ["next song", "skip song", "next track", "skip track"], media_next)
    router.add_intent("media_prev", ["previous song", "last song", "previous track", "go back a song"], media_prev)
    
    tool_map.update({
        "media_play_pause": media_play_pause,
        "media_next": media_next,
        "media_prev": media_prev
    })
