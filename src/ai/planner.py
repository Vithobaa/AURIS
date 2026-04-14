# /mnt/data/ai/planner.py
import os, json, re, time, requests

def _host() -> str:
    h = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    return h if h.startswith("http") else ("http://" + h)

def _models_chain():
    primary = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b").strip()
    fallbacks = [
        "qwen2.5:0.5b",
        "llama3.2:3b",
    ]
    out, seen = [], set()
    for m in [primary, *fallbacks]:
        if m and m not in seen:
            out.append(m); seen.add(m)
    return out

def _payload(model: str, user_text: str, history: list = None):
    history_text = ""
    if history:
        history_text = "Recent context (use this to understand pronouns or vague follow-ups like 'turn it off' or 'now to 50'):\n"
        for item in history:
            history_text += f"User: {item['user']} -> System executed tool: {item['tool']}\n"
        history_text += "\n"
    prompt = (
        "You are AURIS, a desktop AI assistant.\n"
        "Identify the correct tool and return JSON ONLY. No explanation.\n\n"
        "STRICT RULES:\n"
        "- Always return valid JSON, nothing else\n"
        "- If using tool=none, keep 'say' to 1-2 short sentences MAX\n"
        "- Plain text only in 'say' — no markdown, no bullet points\n"
        "- Be direct and brief\n\n"
        "TOOLS:\n"
        "open_app, close_app, close_all_apps, rescan_apps, list_apps, list_browsers,\n"
        "wifi_on, wifi_off, list_wifi, connect_wifi,\n"
        "set_volume, set_brightness, get_time, tell_joke, check_system,\n"
        "read_clipboard, get_news, take_note, set_os_theme, open_settings,\n"
        "bluetooth_on, bluetooth_off, list_bluetooth, connect_bluetooth,\n"
        "web_search, weather, media_play_pause, media_next, media_prev,\n"
        "list_files, read_file, find_files, move_file, copy_file,\n"
        "delete_file, rename_file, file_info, organize_folder, find_duplicates, open_folder, none\n\n"
        "FORMAT: {\"tool\": \"<name>\", \"args\": {}, \"say\": \"<optional>\"}\n\n"
        "Examples:\n"
        "User: open chrome -> {\"tool\":\"open_app\",\"args\":{\"name\":\"chrome\"}}\n"
        "User: what is AI -> {\"tool\":\"none\",\"args\":{},\"say\":\"AI stands for Artificial Intelligence — machines that learn and reason.\"}\n"
        "User: turn wifi on -> {\"tool\":\"wifi_on\",\"args\":{}}\n\n"
        f"{history_text}"
        "User: " + str(user_text) + "\n"
        "Output:\n"
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.1")),
            "num_ctx": int(os.getenv("OLLAMA_CTX", "512")),
            "num_gpu": 999,
            "num_thread": int(os.getenv("OLLAMA_THREADS", "0")),
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "-1"),
            "num_predict": 80,  # Hard ceiling — keeps responses short and fast
        },
    }

_JSON_RE = re.compile(r"\{.*\}", re.S)                 # first JSON object
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)

def _extract_json(s: str):
    if not s:
        return None
    m = _FENCE_RE.search(s)
    if m:
        s = m.group(1)
    m2 = _JSON_RE.search(s)
    if not m2:
        return None
    try:
        obj = json.loads(m2.group(0))
    except Exception:
        return None
    tool = (obj.get("tool") or "none").strip()
    allowed = {
        "open_app","close_app","close_all_apps","rescan_apps",
        "list_apps","list_browsers","set_volume","get_time","tell_joke","none",
        "wifi_on","wifi_off","list_wifi","connect_wifi",
        "web_search","weather","media_play_pause","media_next","media_prev",
        "list_files","read_file","find_files","move_file","copy_file",
        "delete_file","rename_file","file_info","organize_folder","find_duplicates","open_folder",
        "check_system","set_brightness","read_clipboard","get_news","take_note",
        "set_os_theme","open_settings",
        "bluetooth_on","bluetooth_off","list_bluetooth","connect_bluetooth"
    }
    if tool not in allowed:
        tool = "none"
    obj["tool"] = tool
    if "args" not in obj or not isinstance(obj["args"], dict):
        obj["args"] = {}
    if "say" in obj and not isinstance(obj["say"], str):
        obj["say"] = str(obj["say"])
    return obj

def _model_exists(url: str, name: str) -> bool:
    try:
        r = requests.get(f"{url}/api/tags", timeout=6)
        r.raise_for_status()
        tags = r.json().get("models", [])
        return any(m.get("name") == name for m in tags)
    except Exception:
        # if Ollama service is down or unreachable, treat as unavailable
        return False

def plan(user_text: str, history: list = None):
    url = f"{_host()}/api/chat"
    timeout = int(os.getenv("OLLAMA_TIMEOUT", "60") or 60)
    models = _models_chain()

    last_err = None
    for model in models:
        try:
            if not _model_exists(_host(), model):
                # model not present or Ollama unreachable
                print(f"[Planner] model {model} not found on host, skipping.")
                continue

            payload = _payload(model, user_text, history)
            for attempt in range(2):
                try:
                    start = time.time()
                    r = requests.post(url, json=payload, timeout=timeout)
                    end = time.time()
                    print("[MEASURE] Planner (Ollama) latency:", end - start)

                    if r.status_code != 200:
                        print(f"[Planner] Error {r.status_code}: {r.text}")
                    r.raise_for_status()
                    data = r.json()
                    content = (data.get("message") or {}).get("content") or ""
                    obj = _extract_json(content)
                    if obj:
                        return obj
                    if content.strip():
                        return {"tool": "none", "args": {}, "say": content.strip()}
                    return None
                except Exception as e:
                    last_err = e
                    time.sleep(0.5)
            # next model
        except Exception as e:
            last_err = e
            continue
    print(f"[Planner] all models failed: {last_err}")
    return None

def synthesize_answer(user_query: str, search_context: str, fast_mode: bool = False) -> str:
    """
    Uses Ollama to synthesize a natural answer based on search results.
    If search_context is empty, it falls back to internal LLM knowledge.
    If Ollama is offline (or fast_mode is True), it falls back to parsing the raw search_context.
    """
    # Fast mode (Online NO-Ollama mode)
    if fast_mode and search_context:
        match = re.search(r"Result 1:\s*(.*?)\s*\(Source:", search_context, re.IGNORECASE)
        if match:
            return f"{match.group(1).strip()}"
        return "I found some results online, but I couldn't read the summary."
    if not search_context:
        # Fallback: Ask LLM to answer from internal knowledge
        prompt = (
            "You are AURIS, a voice assistant.\n"
            "Answer in 1-2 short sentences only. Plain text, no markdown.\n"
            "If you don't know, say 'I'm not sure about that.'\n\n"
            f"Question: {user_query}\n"
            "Answer:"
        )
    else:
        prompt = (
            "You are AURIS, a voice assistant.\n"
            "Answer in 1-2 short sentences. Plain text only, no markdown.\n"
            "Use only the context below. If the answer isn't there, say 'I couldn't find that.'\n\n"
            f"Context: {search_context}\n\n"
            f"Question: {user_query}\n"
            "Answer:"
        )

    models = _models_chain()
    url = f"{_host()}/api/chat"
    timeout = int(os.getenv("OLLAMA_TIMEOUT", "60") or 60)

    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": int(os.getenv("OLLAMA_CTX", "512")),
                "num_predict": 80,  # Keep answers short
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                content = (data.get("message") or {}).get("content") or ""
                return content.strip()
        except Exception as e:
            print(f"[Synthesize] Model {model} failed: {e}")
            continue

    # Fallback when Ollama is completely offline
    if search_context:
        # Try to extract the first body snippet
        match = re.search(r"Result 1:\s*(.*?)\s*\(Source:", search_context, re.IGNORECASE)
        if match:
            snippet = match.group(1).strip()
            return f"{snippet}"
        return "I found some results online, but I'm having trouble reading them right now."

    return "I'm having trouble connecting to my brain right now."

