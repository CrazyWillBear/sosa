from pathlib import Path

from langchain_core.tools import tool


@tool
def write_file(file_path: str, content: str) -> str:
    """Writes content to a file at the specified path. Overwrites the file if it already exists. Use absolute paths. ALWAYS READ A FILE BEFORE EDITING IT!!!"""
    if content == "<This content has been removed. Reread the file to see what you wrote.>":
        return "Error: content was stripped from history. Read the file first, then rewrite it with the full content."
    try:
        with open(file_path, 'w') as f:
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

_TOKEN_LIMIT = 5000  # ~4 chars per token
_CHAR_LIMIT = _TOKEN_LIMIT * 4

@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file at the specified path. Files over ~5000 tokens will be truncated. USE ABSOLUTE PATHS."""
    if Path(file_path).name == "memory.md":
        return "memory.md is already in your context as a system message. No need to read it."
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        if len(content) > _CHAR_LIMIT:
            content = content[:_CHAR_LIMIT]
            return content + f"\n\n[File truncated at ~5000 tokens. Use bash to read specific lines, e.g. sed -n '1,100p' {file_path}] or head or tail to read the beginning or end of the file.]"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"