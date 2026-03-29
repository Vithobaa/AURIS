import time
from ddgs import DDGS

def search_web(query: str) -> str:
    """
    Searches the web for the given query using DuckDuckGo.
    Returns a summary of the top 3 results for LLM synthesis.
    Includes a resilient multi-backend retry loop to bypass
    Rust reqwest OS Error 11001 connection drops on certain ISPs.
    """
    backends = ["api", "html", "lite"]
    
    for backend in backends:
        try:
            results = DDGS().text(query, max_results=3, backend=backend)
            if not results:
                continue

            # Format results for the LLM
            context = []
            for i, res in enumerate(results, 1):
                body = res.get('body', '').strip()
                title = res.get('title', '').strip()
                if body:
                    context.append(f"Result {i}: {body} (Source: {title})")
            
            if context:
                return "\n\n".join(context)
                
        except Exception as e:
            print(f"[WebSearch] '{backend}' backend failed: {e}")
            time.sleep(0.5)
            continue
            
    print("[WebSearch] All backends failed or returned null. Yielding to internal LLM.")
    return ""


def register(router, tool_map):
    router.add_intent("web_search", ["search for", "web search", "google", "look up", "find online"], lambda t: search_web(t.replace("search for","").replace("web search","").replace("google","").replace("look up","").replace("find online","").strip()))
    tool_map.update({ "web_search": search_web })
