# src/tools/files.py
import os
import re
import shutil
import hashlib
import subprocess
from pathlib import Path
from collections import defaultdict

# ── Common folder shortcuts ───────────────────────────────────────────────────
_HOME = Path.home()

FOLDER_ALIASES = {
    "desktop":    _HOME / "Desktop",
    "downloads":  _HOME / "Downloads",
    "documents":  _HOME / "Documents",
    "pictures":   _HOME / "Pictures",
    "music":      _HOME / "Music",
    "videos":     _HOME / "Videos",
    "appdata":    Path(os.getenv("APPDATA", str(_HOME / "AppData" / "Roaming"))),
    "temp":       Path(os.getenv("TEMP", str(_HOME / "AppData" / "Local" / "Temp"))),
    "home":       _HOME,
    "user":       _HOME,
    "c":          Path("C:\\"),
    "c drive":    Path("C:\\"),
    "d":          Path("D:\\"),
    "d drive":    Path("D:\\"),
}

# ── File type categories for organize ────────────────────────────────────────
FILE_CATEGORIES = {
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".heic", ".raw"},
    "Videos":    {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpeg", ".3gp"},
    "Music":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".csv"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "Code":      {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".cs", ".json", ".xml", ".yaml", ".yml", ".sh", ".bat", ".ps1"},
    "Executables": {".exe", ".msi", ".apk", ".dmg"},
}

MAX_LIST = 30  # max files to speak aloud

# ── Helpers ───────────────────────────────────────────────────────────────────
def _resolve_path(text: str) -> Path:
    """Turn a natural language path mention into an actual Path."""
    t = (text or "").strip().lower()

    # Check aliases first
    for alias, path in FOLDER_ALIASES.items():
        if alias in t:
            return path

    # Try to extract a path-like token (C:\..., ~/..., relative)
    match = re.search(r'[A-Za-z]:\\[^\s"\']+|~[^\s"\']*|\/[^\s"\']+', text)
    if match:
        p = Path(match.group(0)).expanduser()
        return p

    # Fall back to Downloads
    return FOLDER_ALIASES["downloads"]


def _safe_path(path: str) -> Path:
    return Path(os.path.abspath(path)) if path else Path(".")


def _category_of(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in FILE_CATEGORIES.items():
        if ext in exts:
            return cat
    return "Other"


def _file_size_str(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ── Tools ─────────────────────────────────────────────────────────────────────

# Emoji map by file category
FILE_EMOJI = {
    "Images": "🖼️", "Videos": "🎬", "Music": "🎵",
    "Documents": "📄", "Archives": "🗜️", "Code": "💻",
    "Executables": "⚙️", "Other": "📎",
}

def _emoji_for(path: Path) -> str:
    if path.is_dir():
        return "📁"
    cat = _category_of(path.suffix)
    return FILE_EMOJI.get(cat, "📎")


def list_files(text: str = "") -> str:
    """List files in a folder, one per line with emoji."""
    folder = _resolve_path(text)
    if not folder.exists():
        return f"Folder not found: {folder}"
    if not folder.is_dir():
        return f"{folder} is not a folder."

    try:
        items = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not items:
            return f"{folder.name} is empty."

        dirs  = [p for p in items if p.is_dir()]
        files = [p for p in items if p.is_file()]
        total = len(items)

        lines = [f"📂  {folder.name}  —  {total} item(s)"]
        for p in dirs[:MAX_LIST]:
            lines.append(f"  📁  {p.name}/")
        for p in files[:MAX_LIST]:
            lines.append(f"  {_emoji_for(p)}  {p.name}")
        if total > MAX_LIST * 2:
            lines.append(f"  … and {total - MAX_LIST*2} more items.")
        return "\n".join(lines)
    except PermissionError:
        return f"Permission denied to read {folder}."
    except Exception as e:
        return f"Error listing files: {e}"


def read_file(text: str = "") -> str:
    """Read the content of a text file."""
    # Extract quoted filename or last path token
    match = re.search(r'"([^"]+)"|\'([^\']+)\'|(\S+\.\w+)', text)
    if match:
        raw = match.group(1) or match.group(2) or match.group(3)
    else:
        raw = text.strip()

    p = Path(raw).expanduser()
    if not p.exists():
        # Try common folders
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            candidate = folder / p.name
            if candidate.exists():
                p = candidate
                break

    if not p.exists():
        return f"File not found: {raw}"
    if not p.is_file():
        return f"Not a file: {raw}"

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(800)
        return f"'{p.name}': {content}" + ("…" if len(content) >= 800 else "")
    except Exception as e:
        return f"Error reading {p.name}: {e}"


def find_files(text: str = "") -> str:
    """Find files by extension or name pattern, one per line."""
    folder = _resolve_path(text)

    ext_match = re.findall(r'\b(\w+)\s*file', text.lower())
    ext_manual = re.findall(r'\.\w+', text)

    word_to_ext = {
        "pdf": ".pdf", "image": ".jpg", "images": ".jpg", "photo": ".jpg", "photos": ".jpg",
        "video": ".mp4", "videos": ".mp4", "music": ".mp3", "audio": ".mp3",
        "word": ".docx", "excel": ".xlsx", "powerpoint": ".pptx",
        "text": ".txt", "zip": ".zip", "python": ".py", "script": ".py",
        "executable": ".exe", "installer": ".exe",
    }

    target_exts = set()
    for w in ext_match:
        if w in word_to_ext:
            target_exts.add(word_to_ext[w])
    for e in ext_manual:
        target_exts.add(e.lower())

    name_pat = None
    name_match = re.search(r'"([^"]+)"|named?\s+(\S+)', text)
    if name_match:
        name_pat = (name_match.group(1) or name_match.group(2)).lower()

    if not folder.exists():
        return f"Folder not found: {folder}"

    try:
        results = []
        for p in folder.rglob("*"):
            if not p.is_file():
                continue
            if target_exts and p.suffix.lower() not in target_exts:
                continue
            if name_pat and name_pat not in p.name.lower():
                continue
            results.append(p)

        if not results:
            desc = ", ".join(target_exts) if target_exts else "matching"
            return f"No {desc} files found in {folder.name}."

        shown = results[:MAX_LIST]
        ext_label = "/".join(target_exts) if target_exts else "files"
        lines = [f"🔍  Found {len(results)} {ext_label} file(s) in {folder.name}"]
        for p in shown:
            lines.append(f"  {_emoji_for(p)}  {p.name}")
        if len(results) > MAX_LIST:
            lines.append(f"  … and {len(results) - MAX_LIST} more.")
        return "\n".join(lines)
    except PermissionError:
        return f"Permission denied searching {folder}."
    except Exception as e:
        return f"Error searching: {e}"


def move_file(text: str = "") -> str:
    """Move a file to another folder. Example: 'move report.pdf to documents'"""
    # Pattern: move <file> to <destination>
    m = re.search(r'move\s+"?([^"]+?)"?\s+to\s+(.+)', text, re.IGNORECASE)
    if not m:
        return "Please say: move <filename> to <folder>. Example: move report.pdf to documents"

    raw_src = m.group(1).strip()
    raw_dst = m.group(2).strip()

    # Resolve source
    src = Path(raw_src).expanduser()
    if not src.exists():
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            c = folder / src.name
            if c.exists():
                src = c
                break

    if not src.exists():
        return f"File not found: {raw_src}"

    # Resolve destination
    dst_folder = _resolve_path(raw_dst)
    if not dst_folder.exists():
        return f"Destination folder not found: {raw_dst}"

    dst = dst_folder / src.name
    if dst.exists():
        return f"A file named '{src.name}' already exists in {dst_folder.name}. Rename it first."

    try:
        shutil.move(str(src), str(dst))
        return f"Moved '{src.name}' to {dst_folder.name}."
    except Exception as e:
        return f"Failed to move '{src.name}': {e}"


def copy_file(text: str = "") -> str:
    """Copy a file to another folder. Example: 'copy report.pdf to desktop'"""
    m = re.search(r'copy\s+"?([^"]+?)"?\s+to\s+(.+)', text, re.IGNORECASE)
    if not m:
        return "Please say: copy <filename> to <folder>. Example: copy report.pdf to desktop"

    raw_src = m.group(1).strip()
    raw_dst = m.group(2).strip()

    src = Path(raw_src).expanduser()
    if not src.exists():
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            c = folder / src.name
            if c.exists():
                src = c
                break

    if not src.exists():
        return f"File not found: {raw_src}"

    dst_folder = _resolve_path(raw_dst)
    if not dst_folder.exists():
        return f"Destination not found: {raw_dst}"

    dst = dst_folder / src.name
    counter = 1
    while dst.exists():
        stem = src.stem
        dst = dst_folder / f"{stem} ({counter}){src.suffix}"
        counter += 1

    try:
        shutil.copy2(str(src), str(dst))
        size = _file_size_str(dst.stat().st_size)
        return f"Copied '{src.name}' to {dst_folder.name} ({size})."
    except Exception as e:
        return f"Failed to copy '{src.name}': {e}"


def delete_file(text: str = "") -> str:
    """Delete a file. Example: 'delete old_notes.txt'"""
    m = re.search(r'delete\s+"?([^"]+?)"?\s*$', text, re.IGNORECASE)
    if not m:
        match2 = re.search(r'"([^"]+)"|\b(\S+\.\w+)\b', text)
        raw = (match2.group(1) or match2.group(2)) if match2 else ""
    else:
        raw = m.group(1).strip()

    if not raw:
        return "Which file should I delete? Say: delete <filename>."

    src = Path(raw).expanduser()
    if not src.exists():
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            c = folder / src.name
            if c.exists():
                src = c
                break

    if not src.exists():
        return f"File not found: {raw}. Make sure the name is correct."
    if src.is_dir():
        return f"'{raw}' is a folder, not a file. I only delete files for safety."

    try:
        # Move to Recycle Bin instead of permanent delete if possible
        try:
            import send2trash
            send2trash.send2trash(str(src))
            return f"Moved '{src.name}' to Recycle Bin."
        except ImportError:
            src.unlink()
            return f"Deleted '{src.name}' permanently (Recycle Bin not available)."
    except Exception as e:
        return f"Failed to delete '{src.name}': {e}"


def rename_file(text: str = "") -> str:
    """Rename a file. Example: 'rename old.txt to new.txt'"""
    m = re.search(r'rename\s+"?([^"]+?)"?\s+to\s+"?([^"]+?)"?\s*$', text, re.IGNORECASE)
    if not m:
        return "Please say: rename <old name> to <new name>."

    old_name = m.group(1).strip()
    new_name = m.group(2).strip()

    src = Path(old_name).expanduser()
    if not src.exists():
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            c = folder / src.name
            if c.exists():
                src = c
                break

    if not src.exists():
        return f"File not found: {old_name}."

    dst = src.parent / new_name
    if dst.exists():
        return f"A file named '{new_name}' already exists in the same folder."

    try:
        src.rename(dst)
        return f"Renamed '{old_name}' to '{new_name}'."
    except Exception as e:
        return f"Failed to rename: {e}"


def file_info(text: str = "") -> str:
    """Get info about a file: size, type, dates. Example: 'info about video.mp4'"""
    match = re.search(r'"([^"]+)"|\b(\S+\.\w+)\b', text)
    raw = (match.group(1) or match.group(2)) if match else text.strip()

    src = Path(raw).expanduser()
    if not src.exists():
        for folder in [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]:
            c = folder / src.name
            if c.exists():
                src = c
                break

    if not src.exists():
        return f"File not found: {raw}."

    try:
        import datetime
        stat = src.stat()
        size = _file_size_str(stat.st_size)
        modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y, %I:%M %p")
        cat = _category_of(src.suffix)
        return (f"'{src.name}' — {cat}, {size}, "
                f"last modified {modified}, location: {src.parent}.")
    except Exception as e:
        return f"Could not get info for '{raw}': {e}"


def organize_folder(text: str = "") -> str:
    """Organize a folder by sorting files into subfolders by type.
    Example: 'organize my downloads folder'
    """
    folder = _resolve_path(text)
    if not folder.exists():
        return f"Folder not found: {folder}"
    if not folder.is_dir():
        return f"'{folder}' is not a folder."

    moved   = defaultdict(int)
    skipped = 0
    errors  = 0

    try:
        files = [p for p in folder.iterdir() if p.is_file()]
        if not files:
            return f"{folder.name} has no files to organize."

        for p in files:
            cat = _category_of(p.suffix)
            dest_dir = folder / cat
            dest_dir.mkdir(exist_ok=True)
            dest = dest_dir / p.name

            # Skip if already in a subfolder or name conflict
            if dest.exists():
                skipped += 1
                continue

            try:
                shutil.move(str(p), str(dest))
                moved[cat] += 1
            except Exception:
                errors += 1

        if not any(moved.values()):
            return f"Nothing to organize in {folder.name} (all files already sorted or conflicted)."

        summary = ", ".join(f"{n} → {cat}" for cat, n in sorted(moved.items()))
        result = f"Organized {folder.name}: {summary}."
        if skipped:
            result += f" {skipped} file(s) skipped (already exist)."
        if errors:
            result += f" {errors} file(s) failed."
        return result
    except PermissionError:
        return f"Permission denied to organize {folder}."
    except Exception as e:
        return f"Error organizing folder: {e}"


def find_duplicates(text: str = "") -> str:
    """Find duplicate files (by content hash) in a folder.
    Example: 'find duplicate files in downloads'
    """
    folder = _resolve_path(text)
    if not folder.exists():
        return f"Folder not found: {folder}"

    hashes = defaultdict(list)
    try:
        for p in folder.rglob("*"):
            if not p.is_file():
                continue
            try:
                h = hashlib.md5(p.read_bytes()).hexdigest()
                hashes[h].append(p)
            except Exception:
                continue

        dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
        if not dupes:
            return f"No duplicate files found in {folder.name}."

        total_dupes = sum(len(v) - 1 for v in dupes.values())
        wasted = sum(
            p.stat().st_size * (len(paths) - 1)
            for paths in dupes.values()
            for p in paths[:1]
        )
        groups = list(dupes.values())[:5]  # show max 5 groups
        examples = "; ".join(
            f"{paths[0].name} (×{len(paths)})"
            for paths in groups
        )
        return (f"Found {len(dupes)} duplicate group(s), {total_dupes} extra file(s) "
                f"wasting {_file_size_str(wasted)} in {folder.name}. "
                f"Examples: {examples}.")
    except PermissionError:
        return f"Permission denied scanning {folder}."
    except Exception as e:
        return f"Error finding duplicates: {e}"


def open_folder(text: str = "") -> str:
    """Open a folder in File Explorer. Example: 'open downloads folder'"""
    folder = _resolve_path(text)
    if not folder.exists():
        return f"Folder not found: {folder}"
    try:
        subprocess.Popen(["explorer", str(folder)])
        return f"Opened {folder.name} in File Explorer."
    except Exception as e:
        return f"Could not open folder: {e}"


# ── Registration ──────────────────────────────────────────────────────────────
def register(router, tool_map):
    router.add_intent("list_files", [
        "list files in downloads",
        "show files in documents",
        "what files are in my desktop",
        "list my downloads",
        "show me my documents folder",
        "what's in my downloads",
        "list files on desktop",
    ], list_files)

    router.add_intent("find_files", [
        "find all pdf files in documents",
        "search for images in downloads",
        "find python files",
        "look for videos in downloads",
        "find all zip files",
        "search for word documents",
        "find files named report",
    ], find_files)

    router.add_intent("move_file", [
        "move report.pdf to desktop",
        "move file to documents",
        "transfer this file to downloads",
        "move notes.txt to desktop",
    ], move_file)

    router.add_intent("copy_file", [
        "copy report.pdf to desktop",
        "copy file to documents",
        "make a copy of notes.txt in downloads",
        "duplicate this file to desktop",
    ], copy_file)

    router.add_intent("delete_file", [
        "delete old_file.txt",
        "remove notes.txt",
        "delete this file",
        "remove the file named report",
    ], delete_file)

    router.add_intent("rename_file", [
        "rename old.txt to new.txt",
        "rename report to final_report",
        "change the name of notes.txt to ideas.txt",
    ], rename_file)

    router.add_intent("file_info", [
        "info about video.mp4",
        "what is the size of report.pdf",
        "details of this file",
        "when was notes.txt last modified",
        "file info",
    ], file_info)

    router.add_intent("organize_folder", [
        "organize my downloads folder",
        "sort files in downloads",
        "clean up my downloads",
        "organize downloads by type",
        "sort my desktop files",
        "tidy up my downloads",
        "organize files in documents",
    ], organize_folder)

    router.add_intent("find_duplicates", [
        "find duplicate files in downloads",
        "check for duplicates in documents",
        "find repeated files",
        "are there any duplicate files",
        "find duplicate photos",
    ], find_duplicates)

    router.add_intent("open_folder", [
        "open downloads folder",
        "show my documents in explorer",
        "open desktop folder",
        "open the pictures folder",
        "browse my downloads",
        "open file explorer in downloads",
    ], open_folder)

    tool_map.update({
        "list_files":      list_files,
        "read_file":       read_file,
        "find_files":      find_files,
        "move_file":       move_file,
        "copy_file":       copy_file,
        "delete_file":     delete_file,
        "rename_file":     rename_file,
        "file_info":       file_info,
        "organize_folder": organize_folder,
        "find_duplicates": find_duplicates,
        "open_folder":     open_folder,
    })
