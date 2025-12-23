import re
from typing import Optional, Dict, List

APP_SYNONYMS: Dict[str, List[str]] = {
    "notepad": ["notepad", "editor", "text editor"],
    "calculator": ["calculator", "calc"],
    "browser": ["browser", "chrome", "edge", "firefox"],
    "explorer": ["explorer", "file explorer", "files", "my computer"],
}

def extract_app_name(text: str) -> Optional[str]:
    t = text.lower()
    for app, syns in APP_SYNONYMS.items():
        for s in syns:
            if s in t:
                return app
    return None

def extract_volume_value(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})\s*%?", text)
    if m:
        v = int(m.group(1))
        return max(0, min(100, v))
    return None
def guess_app_query(text: str) -> str:
    """
    Pull probable app name from a sentence, e.g.
    'open the microsoft edge please' -> 'microsoft edge'
    """
    import re
    t = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    words = t.split()
    stop = {
        "open","launch","start","run","please","the","a","an","my","app","application",
        "program","software","now","me","to","hey","torque"
    }
    kept = [w for w in words if w not in stop]
    return " ".join(kept).strip()

