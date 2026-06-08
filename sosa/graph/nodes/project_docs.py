"""Helpers for resolving and reading project documentation files.

Each workspace scope (workspace_path and soul_memory_path) may contain a project
doc: AGENTS.md preferred, CLAUDE.md as fallback.  Only one doc per scope is ever
returned (never both).
"""

from pathlib import Path

_CANDIDATES = ("AGENTS.md", "CLAUDE.md")


def resolve_project_doc(directory: Path) -> Path | None:
    """Return the path of the first-matching project doc in *directory*, or None.

    Precedence: AGENTS.md > CLAUDE.md.  Returns None when neither exists.
    Never creates any files.
    """
    for name in _CANDIDATES:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None
