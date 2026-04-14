from pathlib import Path

from sosa.schemas.AgentState import AgentState

_DEFAULT_SOUL = (Path(__file__).parent.parent.parent / "prompts" / "Soul.md").read_text()


def init(state: AgentState) -> dict:
    """Initializes the agent's soul and ensures memory files exist."""

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

    return {"soul": soul_path.read_text()}
