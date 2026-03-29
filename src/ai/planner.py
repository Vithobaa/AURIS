# /mnt/data/ai/planner.py
import os, json, re, time, requests

def _host() -> str:
    h = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    return h if h.startswith("http") else ("http://" + h)

def _models_chain():
    primary = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()
    fallbacks = [
        "llama3.2:3b",
        "qwen2.5:7b-instruct-q5_K_M",
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
        "You are AURIS, a secure desktop AI assistant.\n\n"
        "Your job is to:\n"
        "1. Understand user commands\n"
        "2. Decide the correct system action (tool)\n"
        "3. Return structured output in JSON\n\n"
        "STRICT RULES:\n"
        "- Always return JSON\n"
        "- Never explain unless needed\n"
        "- Use available tools when possible\n"
        "- If unsure, respond normally in \"say\"\n\n"
        "TOOLS:\n"
        "- open_app {name}\n"
        "- close_app {name}\n"
        "- close_all_apps {}\n"
        "- rescan_apps {}\n"
        "- list_apps {}\n"
        "- wifi_on {}\n"
        "- wifi_off {}\n"
        "- list_wifi {}\n"
        "- connect_wifi {index}\n"
        "- set_volume {percent}\n"
        "- get_time {}\n"
        "- tell_joke {}\n"
        "- check_system {}\n"
        "- set_brightness {percent}\n"
        "- read_clipboard {}\n"
        "- get_news {}\n"
        "- take_note {content}\n"
        "- set_os_theme {mode}\n"
        "- open_settings {panel}\n"
        "- bluetooth_on {}\n"
        "- bluetooth_off {}\n"
        "- list_bluetooth {}\n"
        "- connect_bluetooth {index}\n"
        "- web_search {query} (Use for general facts, queries, wikipedia)\n"
        "- weather {city}\n"
        "- media_play_pause {}\n"
        "- media_next {}\n"
        "- media_prev {}\n"
        "- list_files {path}\n"
        "- read_file {path}\n\n"
        "OUTPUT FORMAT:\n"
        "{\n"
        "  \"tool\": \"<tool_name or none>\",\n"
        "  \"args\": { ... },\n"
        "  \"say\": \"<optional response>\"\n"
        "}\n\n"
        "Examples:\n\n"
        "User: open chrome\n"
        "Output:\n"
        "{\"tool\":\"open_app\",\"args\":{\"name\":\"chrome\"}}\n\n"
        "User: turn on the wifi\n"
        "Output:\n"
        "{\"tool\":\"wifi_on\",\"args\":{}}\n\n"
        "User: what is AI\n"
        "Output:\n"
        "{\"tool\":\"none\",\"args\":{},\"say\":\"Artificial Intelligence is...\"}\n\n"
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
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.2")),
            "num_ctx": int(os.getenv("OLLAMA_CTX", "2048")), # Increased for hybrid search context
            "num_gpu": 999, # Try to force GPU offload if available
            "num_thread": int(os.getenv("OLLAMA_THREADS", "0")),  # 0 = auto
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "-1"),
            "num_predict": 120, # Hard ceiling on output length for blazing fast latency
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
        "list_apps","set_volume","get_time","tell_joke","none",
        "wifi_on","wifi_off","list_wifi","connect_wifi",
        "web_search","weather","media_play_pause","media_next","media_prev",
        "list_files","read_file",
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
            "You are AURIS, a helpful voice assistant.\n"
            "The user asked a question, but I have NO INTERNET access right now.\n"
            "Answer the question to the best of your INTERNAL KNOWLEDGE.\n"
            "If you truly don't know, just say 'I can't check online right now, and I'm not sure.'\n\n"
            "USER QUESTION:\n"
            f"{user_query}\n"
        )
    else:
        prompt = (
            "You are AURIS, a helpful voice assistant.\n"
            "CONTEXT from web search:\n"
            f"{search_context}\n\n"
            "USER QUESTION:\n"
            f"{user_query}\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer the user's question using ONLY the provided context.\n"
            "2. Keep it concise (2-3 sentences max) and conversational.\n"
            "3. If the context doesn't contain the answer, say 'I couldn't find that info in the top results.'\n"
            "4. Do not mention 'Based on the results' or 'The context says'. Just answer naturally.\n"
            "5. Do NOT use markdown. Just plain text.\n"
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
                "temperature": 0.3,
                "num_ctx": 2048,
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

