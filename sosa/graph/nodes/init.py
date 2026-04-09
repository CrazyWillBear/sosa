from pathlib import Path

from sosa.schemas.AgentState import AgentState

_DEFAULT_SOUL = (Path(__file__).parent.parent.parent / "prompts" / "Soul.md").read_text()


def init(state: AgentState) -> dict:
    """Initializes the agent's soul from soul.md in the workspace directory."""

    soul_path = state["workspace_path"] / "soul.md"

    if not soul_path.exists():
        soul_path.write_text(_DEFAULT_SOUL)

    memory_path = state["workspace_path"] / "memory.md"
    if not memory_path.exists():
        memory_path.write_text("# My Memory\n")

    return {"soul": soul_path.read_text()}
