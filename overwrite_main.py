import os
import re

main_path = r"c:\Users\vitho\Downloads\auris\main.py"
with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove huge block of tool imports
# from line: `from src.tools.system_tools import (`
# until line: `from src.tools.bluetooth_tools import ...`
import_re = re.compile(r"# --- Tools ---.*?# -----------------------------------------------------------", re.DOTALL)
content = import_re.sub("GLOBAL_TOOL_MAP = {}\n\n# -----------------------------------------------------------", content)

# 2. Replace build_router completely
old_build_router = re.compile(r"def build_router\(\) -> IntentRouter:.*?    router\.build\(\)\n    return router\n", re.DOTALL)
new_build_router = """def build_router() -> IntentRouter:
    router = IntentRouter(threshold=0.52)
    
    # --- WAKE WORD BYPASS (Fixes "Hey Torque" going to Ollama) ---
    router.add_intent("wake_check",
        ["hey torque", "torque", "hello torque", "hi torque"],
        lambda _t: "I'm here. What do you need?")

    from src.tools.registry import load_all_tools
    load_all_tools(router, GLOBAL_TOOL_MAP)

    router.build()
    return router
"""
content = old_build_router.sub(new_build_router, content)

# 3. Replace the local tool_map inside handle_text_inner
old_tool_map = re.compile(r"tool_map = \{.*?\n                    \}", re.DOTALL)
new_tool_map = "tool_map = GLOBAL_TOOL_MAP"
content = old_tool_map.sub(new_tool_map, content)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated main.py successfully with modular architecture.")
