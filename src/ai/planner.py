# /mnt/data/ai/planner.py
import os, json, re, time, requests

def _host() -> str:
    h = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    return h if h.startswith("http") else ("http://" + h)

def _models_chain():
    primary = os.getenv("OLLAMA_MODEL", "llama3.2:3b-instruct-q4_K_M").strip()
    fallbacks = [
        "qwen2.5:3b-instruct-q4_K_M",
        "llama3.2:1b-instruct-q4_0",
        "qwen2.5:7b-instruct-q5_K_M",
        "qwen2.5:14b-instruct-q4_K_M",
    ]
    out, seen = [], set()
    for m in [primary, *fallbacks]:
        if m and m not in seen:
            out.append(m); seen.add(m)
    return out

def _payload(model: str, user_text: str):
    prompt = (
        "You are 'AURIS', a smart, sentient desktop assistant.\n"
        "Your goal is to intelligently decide if a user's request requires a TOOL, a WEB SEARCH, or just a CHAT reply.\n"
        "TOOLS:\n"
        "- open_app {name}\n- close_app {name}\n- close_all_apps {}\n"
        "- rescan_apps {}\n- list_apps {}\n- set_volume {percent}\n"
        "- get_time {}\n- tell_joke {}\n"
        "- web_search {query} (Use this for: news, current events, weather, stock prices, or specific facts you might not know)\n"
        "- weather {city}\n"
        "- media_play_pause {}\n- media_next {}\n- media_prev {}\n"
        "- list_files {path}\n- read_file {path}\n\n"
        "RULES:\n"
        "1. If the user asks for current information (news, sports, stocks, weather), use 'web_search' or 'weather'.\n"
        "2. If the user asks a general knowledge question you are confident about (e.g. 'Who is Einstein?'), answering directly (tool='none') is fine, BUT using 'web_search' is safer for accuracy.\n"
        "3. If the user asks to perform an action on the PC, use the appropriate tool.\n"
        "4. If it is casual chat ('Hello', 'How are you'), set tool to 'none' and reply in 'say'.\n"
        "5. ARGUMENT EXTRACTION: Extract ONLY the specific entity. e.g. for 'weather in London', args.city='London' (NOT 'in London'). For 'search for cats', args.query='cats'.\n\n"
        "Return ONLY JSON (no commentary, no code fences) in this schema:\n"
        "{\"tool\":\"<tool_name_or_none>\",\"args\":{...},\"say\":\"<optional_reply>\"}\n"
        f"User: {user_text}\n"
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.2")),
            "num_ctx": int(os.getenv("OLLAMA_CTX", "2048")), # Increased for hybrid search context
            "num_gpu": 999, # Try to force GPU offload if available
            "num_thread": int(os.getenv("OLLAMA_THREADS", "0")),  # 0 = auto
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30s"),
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
        "web_search","weather","media_play_pause","media_next","media_prev",
        "list_files","read_file"
    }
    if tool not in allowed:
        obj["tool"] = "none"
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

def plan(user_text: str):
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

            payload = _payload(model, user_text)
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

