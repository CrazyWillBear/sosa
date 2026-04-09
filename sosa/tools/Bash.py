import os
import re
import subprocess
from pathlib import Path
from typing import Annotated, Callable

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


_CHAR_LIMIT = 3000 * 4  # ~3000 tokens

_ALLOWED = {
    "cat", "head", "tail", "less", "more",
    "ls", "find", "stat", "file",
    "grep", "rg", "awk", "sed", "cut", "sort", "uniq", "tr", "wc", "diff", "jq", "yq",
    "echo", "pwd", "which", "whereis", "type", "true", "false",
    "whoami", "id", "uname", "date", "uptime", "hostname", "env", "printenv", "ps", "pgrep",
    "python", "python3", "node",
    "pytest", "cargo", "go",
}


def _programs(command: str) -> list[str]:
    """Extract the program name from each segment of a shell command."""
    segments = re.split(r"[|;&]|\|\||\&\&", command)
    programs = []
    for seg in segments:
        seg = seg.strip()
        if seg:
            first = seg.split()[0]
            programs.append(os.path.basename(first))
    return programs


@tool
def run_bash_command(
    command: str,
    workspace_path: Annotated[Path, InjectedState("workspace_path")],
    approval_fn: Annotated[Callable[[str], bool], InjectedState("approval_fn")],
) -> str:
    """Execute a bash command. Output over ~3000 tokens will be truncated. Working directory is ALWAYS workspace by default. To execute in a different working directory, use 'cd <dir> && <command>'."""

    if not all(p in _ALLOWED for p in _programs(command)):
        if not approval_fn(command):
            return "Command not approved by user."

    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=workspace_path)
        output = result.stdout.decode('utf-8')
        if len(output) > _CHAR_LIMIT:
            output = output[:_CHAR_LIMIT] + "\n\n[Output truncated at ~5000 tokens]"
        return output
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.stderr.decode('utf-8')}"
