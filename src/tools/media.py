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
