from pathlib import Path
from typing import TypedDict, List, Annotated, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, Tool
from langgraph.graph import add_messages


# Sentinel value: return {path: REMOVE} in a state update to delete that path
# from file_hashes.  Non-sentinel values merge as usual.
#
# Usage in a graph node:
#   from sosa.schemas.AgentState import REMOVE
#   return {"file_hashes": {deleted_path: REMOVE}}
class _RemoveSentinel:
    """Singleton sentinel for file_hashes removal."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "REMOVE"


REMOVE = _RemoveSentinel()


def merge_file_hashes(existing: dict[str, str], update: dict[str, str]) -> dict[str, str]:
    """Reducer for file_hashes: merges update into existing (update wins on collision).

    If any value in *update* is the REMOVE sentinel, that key is deleted from
    the merged result rather than written.  All other keys merge as before.
    """
    merged = dict(existing)
    for key, value in update.items():
        if value is REMOVE:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


class AgentState(TypedDict):


    # Context
    system_prompt: str                                  # System prompt, includes user prompt
    soul: str                                           # Soul.md
    messages: Annotated[List[AnyMessage], add_messages] # Includes tool calls and responses
    workspace_path: Path                                # Path to agent workspace (per-workspace files/memory)
    soul_memory_path: Path                              # Path to soul.md and universal memory.md
    skills_path: Path                                   # Path to skills directory

    # State
    name: str
    model: BaseChatModel | Runnable
    base_model: BaseChatModel
    tools: List[BaseTool | Tool]
    approval_fn: Callable[[str], bool]

    # Per-session file content fingerprints: path → SHA-256 hex digest.
    # Populated by read_file; resets each new session.
    file_hashes: Annotated[dict[str, str], merge_file_hashes]