import os

def _safe_path(path: str) -> str:
    # Basic check to ensure we don't go exploring system folders rashly
    # For now, we trust the user or default to current dir if relative
    p = os.path.abspath(path)
    return p

def list_files(path: str) -> str:
    """Lists files in the specified directory."""
    p = _safe_path(path if path else ".")
    if not os.path.isdir(p):
        return f"Directory not found: {p}"
    
    try:
        items = os.listdir(p)
        if not items:
            return "Directory is empty."
        return f"Files in {p}:\n" + ", ".join(items[:50]) # limit output
    except Exception as e:
        return f"Error listing files: {e}"

def read_file(path: str) -> str:
    """Reads the content of a text file."""
    p = _safe_path(path)
    if not os.path.exists(p):
        return f"File not found: {p}"
    if not os.path.isfile(p):
        return f"Not a file: {p}"
        
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(1000) # limit characters
        return f"Content of {os.path.basename(p)}:\n{content}..."
    except Exception as e:
        return f"Error reading file: {e}"


def register(router, tool_map):
    tool_map.update({ "list_files": list_files, "read_file": read_file })
