"""Staleness detection node for the Sosa graph (issue #5).

Runs before the model is invoked each turn.  Compares every tracked path in
``file_hashes`` against its current on-disk content:

- **Changed**: content differs from the stored hash → inject a notification,
  refresh the stored hash to the new value.
- **Deleted**: file no longer exists → inject a notification, drop the key via
  the REMOVE sentinel so the reducer removes it.
- **Unchanged**: hash matches → nothing emitted, nothing written.

A single ``SystemMessage`` is injected summarising all affected paths so the
agent can decide whether to re-read them.  When no files have changed, no
message is added and the state update is empty (falsy).
"""

from pathlib import Path

from langchain_core.messages import SystemMessage

from sosa.schemas.AgentState import AgentState, REMOVE
from sosa.tools.hashing import hash_file


def staleness(state: AgentState) -> dict:
    """Detect stale tracked files and notify the agent via a SystemMessage.

    Returns a state-update dict that may contain:
    - ``messages``: a list with a single ``SystemMessage`` (when files changed/deleted)
    - ``file_hashes``: mapping of refreshed hashes and REMOVE sentinels
    """
    file_hashes: dict[str, str] = state.get("file_hashes") or {}

    changed: list[str] = []
    deleted: list[str] = []
    hash_updates: dict[str, object] = {}

    for path_str, stored_hash in file_hashes.items():
        try:
            current_hash = hash_file(path_str)
        except FileNotFoundError:
            deleted.append(path_str)
            hash_updates[path_str] = REMOVE
            continue

        if current_hash != stored_hash:
            changed.append(path_str)
            hash_updates[path_str] = current_hash

    if not changed and not deleted:
        return {}

    # Build a single concise notification message
    lines: list[str] = [
        "The following tracked files have changed since you last read them."
        " Re-read any that are relevant to your current task."
    ]

    if changed:
        lines.append("\nChanged:")
        for p in changed:
            lines.append(f"  - {p} (changed)")

    if deleted:
        lines.append("\nDeleted:")
        for p in deleted:
            lines.append(f"  - {p} (deleted)")

    notice = SystemMessage(content="\n".join(lines))

    update: dict = {"messages": [notice]}
    if hash_updates:
        update["file_hashes"] = hash_updates

    return update
