from pathlib import Path
from typing import List

from langchain_core.messages import AnyMessage, SystemMessage, AIMessage

from sosa.schemas.AgentState import AgentState

_MCP_ADDENDUM = (Path(__file__).parent.parent / "prompts" / "McpAddendum.md").read_text()


class Context:
    system_prompt: str
    soul: str
    memory_index: str | None
    global_project_doc: str | None
    workspace_project_doc: str | None
    messages: List[AnyMessage]
    has_mcp: bool

    def __init__(self, agent_state: AgentState):
        self.system_prompt = agent_state['system_prompt']
        self.soul_path = agent_state['soul_memory_path'] / "soul.md"
        self.soul = agent_state['soul']
        self.memory_index = agent_state.get('memory_index')
        self.global_project_doc = agent_state.get('global_project_doc')
        self.workspace_project_doc = agent_state.get('workspace_project_doc')
        self.messages = agent_state['messages']
        self.has_mcp = any(t.name == "search_tools" for t in agent_state.get('tools', []))

    def to_messages(self) -> List[AnyMessage]:
        """Converts the context to a list of Messages.

        Injection order:
          1. System prompt
          2. soul.md
          3. MEMORY.md index — if memory files exist
          4. Global project doc (AGENTS.md / CLAUDE.md from soul_memory_path) — if present
          5. Workspace project doc (AGENTS.md / CLAUDE.md from workspace_path) — if present
          6. MCP addendum — if MCP tools are loaded
          7. Message history
        """

        messages = [
            SystemMessage(content=self.system_prompt),
            SystemMessage(content=(
                f"{self.soul_path}:\n```\n{self.soul}\n```\n"
            )),
        ]

        if self.memory_index is not None:
            messages.append(SystemMessage(content=self.memory_index))

        if self.global_project_doc is not None:
            messages.append(SystemMessage(content=self.global_project_doc))

        if self.workspace_project_doc is not None:
            messages.append(SystemMessage(content=self.workspace_project_doc))

        if self.has_mcp:
            messages.append(SystemMessage(content=_MCP_ADDENDUM))

        messages.extend(self.messages)
        return messages