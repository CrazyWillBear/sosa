from pathlib import Path

from langchain_core.messages import SystemMessage

from sosa.graph.nodes.memory_index import MalformedMemoryFileError, build_memory_index
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
    """Initializes the agent's soul, builds the memory index, and reads project docs.

    On every turn:
    - Ensures soul.md exists (creating from the default template if absent).
    - Builds MEMORY.md from memory/ files under soul_memory_path and carries the
      index content through state so Context can inject it.
    - Resolves and reads project docs (AGENTS.md / CLAUDE.md) from both
      soul_memory_path (global scope) and workspace_path (workspace scope).

    Resolved doc paths are registered in ``file_hashes`` with their current
    content hash so the staleness node can detect external edits on subsequent
    turns.
    """

    soul_memory_path = state["soul_memory_path"]

    soul_path = soul_memory_path / "soul.md"
    if not soul_path.exists():
        soul_path.write_text(_DEFAULT_SOUL)

    memory_index_error: str | None = None
    try:
        memory_index = build_memory_index(soul_memory_path)
    except MalformedMemoryFileError as exc:
        memory_index = None
        memory_index_error = (
            f"[Memory index error] {exc} "
            f"Fix the frontmatter in the file above to restore the memory index."
        )

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
        "memory_index": memory_index,
        "global_project_doc": global_doc_content,
        "workspace_project_doc": workspace_doc_content,
    }
    if file_hashes:
        result["file_hashes"] = file_hashes
    if memory_index_error:
        result["messages"] = [SystemMessage(content=memory_index_error)]
    return result
