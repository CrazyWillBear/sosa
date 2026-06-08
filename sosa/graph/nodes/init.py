from pathlib import Path

from sosa.graph.nodes.memory_index import build_memory_index
from sosa.graph.nodes.project_docs import resolve_project_doc
from sosa.schemas.AgentState import AgentState, REMOVE
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


def _sync_memory_index(
    soul_memory_path: Path,
    stored_hashes: dict[str, str],
) -> tuple[str | None, dict[str, object]]:
    """Hash-gate MEMORY.md regeneration and compute per-file hash updates.

    Scans ``soul_memory_path/memory/`` for ``.md`` files and compares each
    file's current content hash against the baseline recorded in
    ``stored_hashes``.  The index is rebuilt only when the memory set has
    changed (file added, content changed, or file deleted).

    Returns:
        (memory_index, hash_updates) where:
        - *memory_index* is the rebuilt index string (or None when no files
          exist), reflecting the post-change state.  It is also None when
          nothing changed and the caller should retain the previous state value.
        - *hash_updates* is a ``file_hashes``-compatible dict: current-hash
          entries for existing files, ``REMOVE`` sentinels for deleted files.
          Only entries that differ from ``stored_hashes`` are included.
    """
    memory_dir = soul_memory_path / "memory"
    current_files: dict[str, str] = {}  # str(path) → current hash

    if memory_dir.exists():
        for path in memory_dir.glob("*.md"):
            current_files[str(path)] = hash_file(path)

    # Determine which stored keys covered memory files
    # (only paths inside memory_dir count as memory-file entries)
    stored_memory_keys = {
        k for k in stored_hashes
        if k.startswith(str(memory_dir) + "/") or k.startswith(str(memory_dir) + "\\")
    }

    # Compute hash updates: new/changed files and deleted files
    hash_updates: dict[str, object] = {}
    changed = False

    for path_str, current_hash in current_files.items():
        if stored_hashes.get(path_str) != current_hash:
            hash_updates[path_str] = current_hash
            changed = True

    for path_str in stored_memory_keys:
        if path_str not in current_files:
            hash_updates[path_str] = REMOVE
            changed = True

    if not changed:
        # Nothing changed — leave MEMORY.md as-is, emit only no-op updates
        return None, hash_updates

    # Rebuild the index (writes MEMORY.md when files exist)
    memory_index = build_memory_index(soul_memory_path)
    return memory_index, hash_updates


def init(state: AgentState) -> dict:
    """Initializes the agent's soul, builds the memory index, and reads project docs.

    On every turn:
    - Ensures soul.md exists (creating from the default template if absent).
    - Hash-gates MEMORY.md regeneration: rebuilds only when memory files
      were added, changed, or deleted since the last turn.
    - Registers every memory/*.md file in ``file_hashes`` so the staleness
      node surfaces external edits on subsequent turns.  Uses REMOVE for
      deleted files.
    - Resolves and reads project docs (AGENTS.md / CLAUDE.md) from both
      soul_memory_path (global scope) and workspace_path (workspace scope).

    Resolved doc paths are also registered in ``file_hashes`` so the staleness
    node can detect external edits on subsequent turns.
    """

    soul_memory_path = state["soul_memory_path"]

    soul_path = soul_memory_path / "soul.md"
    if not soul_path.exists():
        soul_path.write_text(_DEFAULT_SOUL)

    stored_hashes: dict[str, str] = state.get("file_hashes") or {}
    new_memory_index, memory_hash_updates = _sync_memory_index(
        soul_memory_path, stored_hashes
    )

    global_doc_content, global_doc_path = _read_project_doc(soul_memory_path)
    workspace_doc_content, workspace_doc_path = _read_project_doc(state["workspace_path"])

    # Register resolved project-doc paths in file_hashes so the staleness node
    # can detect external edits on subsequent turns.  Only paths that actually
    # exist are registered — absent docs are never phantom-tracked.
    file_hashes: dict[str, object] = dict(memory_hash_updates)
    for doc_path in (global_doc_path, workspace_doc_path):
        if doc_path is not None:
            file_hashes[str(doc_path)] = hash_file(doc_path)

    result: dict = {
        "soul": soul_path.read_text(),
        "global_project_doc": global_doc_content,
        "workspace_project_doc": workspace_doc_content,
    }

    # Only update memory_index in state when we actually rebuilt the index.
    # When nothing changed, keep the previous value (don't overwrite with None).
    if new_memory_index is not None:
        result["memory_index"] = new_memory_index

    if file_hashes:
        result["file_hashes"] = file_hashes
    return result
