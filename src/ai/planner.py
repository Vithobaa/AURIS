# /mnt/data/ai/planner.py
import os, json, re, time, requests

def _host() -> str:
    h = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    return h if h.startswith("http") else ("http://" + h)

def _models_chain():
    primary = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M").strip()
    fallbacks = [
        "qwen2.5:7b-instruct-q5_K_M",
        "llama3.2:3b-instruct-q4_K_M",
        "qwen2.5:3b-instruct-q4_K_M",
        "llama3.2:1b-instruct-q4_0",
    ]
    out, seen = [], set()
    for m in [primary, *fallbacks]:
        if m and m not in seen:
            out.append(m); seen.add(m)
    return out

def _payload(model: str, user_text: str):
    prompt = (
        "You are a STRICT tool router for a local desktop assistant.\n"
        "TOOLS:\n"
        "- open_app {name}\n- close_app {name}\n- close_all_apps {}\n"
        "- rescan_apps {}\n- list_apps {}\n- set_volume {percent}\n"
        "- get_time {}\n- tell_joke {}\n\n"
        "Return ONLY JSON (no commentary, no code fences) in this schema:\n"
        "{\"tool\":\"<one of: open_app|close_app|close_all_apps|rescan_apps|list_apps|set_volume|get_time|tell_joke|none>\","
        "\"args\":{...},\"say\":\"<optional short reply>\"}\n"
        "If it’s a general Q&A, set tool to \"none\" and put the answer in \"say\".\n"
        f"User: {user_text}\n"
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.2")),
            "num_ctx": int(os.getenv("OLLAMA_CTX", "1024")),
            "num_gpu": 0,
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
        "list_apps","set_volume","get_time","tell_joke","none"
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
