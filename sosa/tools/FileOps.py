from pathlib import Path

from langchain_core.tools import tool


@tool
def write_file(file_path: str, content: str, mode: str = "a") -> str:
    """Writes content to a file at the specified path. Use absolute paths. ALWAYS READ A FILE BEFORE EDITING IT!!!
    mode: 'a' (default) appends to the file; 'w' overwrites the file entirely."""
    if content == "<This content has been removed. Reread the file to see what you wrote.>":
        return "Error: content was stripped from history. Read the file first, then rewrite it with the full content."
    if mode not in ("a", "w"):
        return "Error: mode must be 'a' (append) or 'w' (overwrite)."
    try:
        with open(file_path, mode) as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

@tool
def edit_file(file_path: str, string_to_replace: str, replacement: str) -> str:
    """Edits a file at the specified path by replacing the string_to_replace with your replacement. Use absolute paths. ALWAYS READ A FILE BEFORE EDITING IT!!!"""
    if "<This content has been removed. Reread the file to see what you wrote.>" in (string_to_replace, replacement):
        return "Error: content was stripped from history. Read the file first, then edit it with the full content."
    try:
        if not Path(file_path).exists():
            return f"Error: file '{file_path}' does not exist."
        with open(file_path, 'r+') as f:
            content = f.read()
            content = content.replace(string_to_replace, replacement)
            f.seek(0)
            f.write(content)
            f.truncate()
        return f"Successfully edited {file_path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"

@tool
def read_file(file_path: str, start_line: int = 0, end_line: int = 200) -> str:
    """Reads the content of a file at the specified path. USE ABSOLUTE PATHS.
    start_line and end_line are 0-indexed line numbers (like Python list slicing).
    Defaults to the first 200 lines. For large files, paginate by adjusting these values."""
    if Path(file_path).name == "memory.md":
        return "memory.md is already in your context as a system message. No need to read it."
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        return ''.join(lines[start_line:end_line])
    except Exception as e:
        return f"Error reading file: {str(e)}"