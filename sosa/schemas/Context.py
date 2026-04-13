from pathlib import Path
from typing import List

from langchain_core.messages import AnyMessage, SystemMessage

from sosa.schemas.AgentState import AgentState

_MCP_ADDENDUM = (Path(__file__).parent.parent / "prompts" / "McpAddendum.md").read_text()


class Context:
    system_prompt: str
    soul: str
    memory_md: str
    messages: List[AnyMessage]
    has_mcp: bool

    def __init__(self, agent_state: AgentState):
        self.system_prompt = agent_state['system_prompt']
        self.soul = agent_state['soul']
        self.memory_md = (agent_state['workspace_path'] / "memory.md").read_text()
        self.messages = agent_state['messages']
        self.has_mcp = any(t.name == "search_tools" for t in agent_state.get('tools', []))

    def to_messages(self) -> List[AnyMessage]:
        """Converts the context to a list of Messages."""

        messages = [
            SystemMessage(content=self.system_prompt),
            SystemMessage(content=(
                f"soul.md:\n```\n{self.soul}\n```\n"
            )),
            SystemMessage(content=(
                f"memory.md:\n```\n{self.memory_md}\n```\n"
            )),
        ]

        if self.has_mcp:
            messages.append(SystemMessage(content=_MCP_ADDENDUM))

        messages.extend(self.messages)
        return messages