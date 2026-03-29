# src/tools/registry.py
import os
import importlib
import inspect

def load_all_tools(router, tool_map):
    """
    Scans the src/tools directory for any Python files, imports them,
    and calls their `register(router, tool_map)` function if it exists.
    """
    tools_dir = os.path.dirname(__file__)
    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and not filename.startswith("__") and filename != "registry.py":
            module_name = f"src.tools.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "register") and inspect.isfunction(module.register):
                    module.register(router, tool_map)
                    print(f"[Registry] Loaded plugin: {module_name}")
            except Exception as e:
                print(f"[Registry] Failed to load tool module {module_name}: {e}")
