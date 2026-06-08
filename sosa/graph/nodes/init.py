from pathlib import Path

from sosa.graph.nodes.project_docs import resolve_project_doc
from sosa.schemas.AgentState import AgentState

_DEFAULT_SOUL = (Path(__file__).parent.parent.parent / "prompts" / "Soul.md").read_text()


def _read_project_doc(directory: Path) -> str | None:
    """Resolve and read the project doc for *directory*, or return None."""
    doc_path = resolve_project_doc(directory)
    if doc_path is None:
        return None
    return f"{doc_path}:\n```\n{doc_path.read_text()}\n```\n"


def init(state: AgentState) -> dict:
    """Initializes the agent's soul and ensures memory files exist.

    Also resolves and reads project documentation (AGENTS.md / CLAUDE.md) from
    both soul_memory_path (global scope) and workspace_path (workspace scope).
    Each doc is injected fresh every turn so changes appear on the next turn.
    """

    soul_memory_path = state["soul_memory_path"]

    soul_path = soul_memory_path / "soul.md"
    if not soul_path.exists():
        soul_path.write_text(_DEFAULT_SOUL)

    universal_memory_path = soul_memory_path / "memory.md"
    if not universal_memory_path.exists():
        universal_memory_path.write_text("# Universal Memory\n")

    workspace_memory_path = state["workspace_path"] / "memory.md"
    if not workspace_memory_path.exists():
        workspace_memory_path.write_text("# Workspace Memory\n")

    return {
        "soul": soul_path.read_text(),
        "global_project_doc": _read_project_doc(soul_memory_path),
        "workspace_project_doc": _read_project_doc(state["workspace_path"]),
    }
