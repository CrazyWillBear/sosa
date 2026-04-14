from pathlib import Path
from typing import Annotated, Callable

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


def _line_block_replace(content: str, needle: str, replacement: str) -> tuple[str, str | None]:
    """Replace the first line-block in content that matches needle line-by-line (stripped).
    Returns (new_content, error_msg). error_msg is None on success."""
    content_lines = content.splitlines()
    needle_lines = needle.strip().splitlines()

    if not needle_lines:
        return content, "string_to_replace is empty after stripping"

    stripped_needle = [l.strip() for l in needle_lines]
    stripped_content = [l.strip() for l in content_lines]
    n = len(needle_lines)

    matches = [i for i in range(len(content_lines) - n + 1) if stripped_content[i:i+n] == stripped_needle]

    if not matches:
        return content, "string_to_replace not found"
    if len(matches) > 1:
        return content, f"ambiguous: {len(matches)} matching blocks found — make string_to_replace more unique"

    i = matches[0]
    new_lines = content_lines[:i] + replacement.splitlines() + content_lines[i + n:]
    new_content = '\n'.join(new_lines)
    if content.endswith('\n'):
        new_content += '\n'
    return new_content, None


def _is_allowed(file_path: str, workspace_path: Path, soul_memory_path: Path) -> bool:
    """Returns True if file_path is within workspace_path or soul_memory_path."""
    resolved = Path(file_path).resolve()
    return (
        resolved == workspace_path or resolved.is_relative_to(workspace_path) or
        resolved == soul_memory_path or resolved.is_relative_to(soul_memory_path)
    )


@tool
def write_file(
    file_path: str,
    content: str,
    workspace_path: Annotated[Path, InjectedState("workspace_path")],
    soul_memory_path: Annotated[Path, InjectedState("soul_memory_path")],
    approval_fn: Annotated[Callable[[str], bool], InjectedState("approval_fn")],
    mode: str = "a",
) -> str:
    """Writes content to a file at the specified path. Use absolute paths.
    Mode: 'a' (default) appends to the file; 'w' overwrites the file entirely. ALWAYS READ A FILE BEFORE EDITING IT!!!"""
    if content == "<This content has been removed. Reread the file to see what you wrote.>":
        return "Error: content was stripped from history. Read the file first, then rewrite it with the full content."
    if mode not in ("a", "w"):
        return "Error: mode must be 'a' (append) or 'w' (overwrite)."
    if not _is_allowed(file_path, workspace_path, soul_memory_path):
        if not approval_fn(f"write_file: {file_path}"):
            return f"Write to '{file_path}' was not approved by the user."
    try:
        with open(file_path, mode) as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to '{file_path}' (mode='{mode}'): {str(e)}"


@tool
def edit_file(
    file_path: str,
    string_to_replace: str,
    replacement: str,
    workspace_path: Annotated[Path, InjectedState("workspace_path")],
    soul_memory_path: Annotated[Path, InjectedState("soul_memory_path")],
    approval_fn: Annotated[Callable[[str], bool], InjectedState("approval_fn")],
) -> str:
    """Edits a file at the specified path by replacing the string_to_replace with your replacement. Use absolute paths. ALWAYS READ A FILE BEFORE EDITING IT!!!"""
    if "<This content has been removed. Reread the file to see what you wrote.>" in (string_to_replace, replacement):
        return "Error: content was stripped from history. Read the file first, then edit it with the full content."
    if not string_to_replace:
        return "Error: string_to_replace cannot be empty. Use write_file with mode='a' to append content."
    if not _is_allowed(file_path, workspace_path, soul_memory_path):
        if not approval_fn(f"edit_file: {file_path}"):
            return f"Edit to '{file_path}' was not approved by the user."
    try:
        if not Path(file_path).exists():
            return f"Error: '{file_path}' does not exist."
        with open(file_path, 'r+') as f:
            content = f.read().replace('\r\n', '\n')
            replacement_norm = replacement.replace('\r\n', '\n')
            new_content, err = _line_block_replace(content, string_to_replace, replacement_norm)
            if err:
                return f"Error: {err} in '{file_path}'. Read the file to get the exact text to replace."
            f.seek(0)
            f.write(new_content)
            f.truncate()
        return f"Successfully edited {file_path}"
    except Exception as e:
        return f"Error editing '{file_path}': {str(e)}"


@tool
def read_file(file_path: str, start_line: int = 0, end_line: int = 200) -> str:
    """Reads the content of a file at the specified path. USE ABSOLUTE PATHS.
    start_line and end_line are 0-indexed line numbers (like Python list slicing).
    Defaults to the first 200 lines. For large files, paginate by adjusting these values."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        return ''.join(lines[start_line:end_line])
    except Exception as e:
        return f"Error reading '{file_path}': {str(e)}"