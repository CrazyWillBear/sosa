from pathlib import Path

from sosa.graph.nodes.project_docs import resolve_project_doc
from sosa.schemas.AgentState import AgentState
from sosa.tools.hashing import hash_file

_DEFAULT_SOUL = (Path(__file__).parent.parent.parent / "prompts" / "Soul.md").read_text()


def _read_project_doc(directory: Path) -> tuple[str | None, Path | None]:
    """Resolve and read the project doc for *directory*.

    Returns a (content_string, resolved_path) tuple.  Both elements are None
    when no matching doc exists in *directory*.
    """
    doc_path = resolve_project_doc(directory)
    if doc_path is None:
        return None, None
    return f"{doc_path}:\n```\n{doc_path.read_text()}\n```\n", doc_path


def init(state: AgentState) -> dict:
    """Initializes the agent's soul and ensures memory files exist.

    Also resolves and reads project documentation (AGENTS.md / CLAUDE.md) from
    both soul_memory_path (global scope) and workspace_path (workspace scope).
    Each doc is injected fresh every turn so changes appear on the next turn.

    Resolved doc paths are registered in ``file_hashes`` with their current
    content hash so the staleness node can detect external edits on subsequent
    turns.
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

    global_doc_content, global_doc_path = _read_project_doc(soul_memory_path)
    workspace_doc_content, workspace_doc_path = _read_project_doc(state["workspace_path"])

    # Register resolved project-doc paths in file_hashes so the staleness node
    # can detect external edits on subsequent turns.  Only paths that actually
    # exist are registered — absent docs are never phantom-tracked.
    file_hashes: dict[str, str] = {}
    for doc_path in (global_doc_path, workspace_doc_path):
        if doc_path is not None:
            file_hashes[str(doc_path)] = hash_file(doc_path)

    result: dict = {
        "soul": soul_path.read_text(),
        "global_project_doc": global_doc_content,
        "workspace_project_doc": workspace_doc_content,
    }
    if file_hashes:
        result["file_hashes"] = file_hashes
    return result
