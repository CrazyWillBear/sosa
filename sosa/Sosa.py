from pathlib import Path
from typing import List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_core.tools import Tool, BaseTool
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from sosa.graph.nodes.cleanup import cleanup
from sosa.graph.nodes.compacter import compacter
from sosa.graph.nodes.init import init
from sosa.graph.nodes.react import react
from sosa.schemas.AgentState import AgentState
from sosa.tools.Bash import run_bash_command
from sosa.tools.FileOps import write_file, edit_file, read_file


_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "Prompt.md").read_text()
BASIC_TOOLS = [run_bash_command, write_file, edit_file, read_file]


def _add_basic_tools(tools: List[Tool | BaseTool] = None) -> List[Tool | BaseTool]:
    if tools is None:
        return list(BASIC_TOOLS)
    for tool in BASIC_TOOLS:
        if tool not in tools:
            tools.append(tool)
    return tools


class Sosa:
    """Sosa is a general agent framework built on top of LangGraph. It provides a structured way to build agents that
    can use tools, maintain a "soul" (a persistent state stored in soul.md), and operate within a workspace."""

    def __init__(
        self,
        model: BaseChatModel,
        prompt: str,
        workspace_path: Path | str,
        soul_memory_path: Path | str,
        tools: list[Tool | BaseTool] = None,
        include_basic_tools: bool = True,
        name: str = "Sosa",
        approval_fn: callable | None = None,
        mcp_servers: dict | None = None,
    ):
        self._base_model = model
        self.tools = _add_basic_tools(tools) if include_basic_tools else (tools or [])
        self.model = model.bind_tools(self.tools)
        self.workspace_path = Path(workspace_path).resolve()
        self.soul_memory_path = Path(soul_memory_path).resolve()
        self.name = name
        self._base_prompt = prompt
        self.system_prompt = self._build_system_prompt(prompt)
        self.approval_fn = approval_fn or (lambda _: False)
        self.mcp_servers = mcp_servers or {}
        self._mcp_client = None
        self.graph = None

    # ------------------------------------------------------------------
    # Async context manager (required when mcp_servers is set)
    # ------------------------------------------------------------------

    async def __aenter__(self):
        if self.mcp_servers:
            await self._setup_mcp()
        self.build()
        return self

    async def __aexit__(self, *args):
        self._mcp_client = None

    async def _setup_mcp(self):
        import os
        import mcp.client.stdio as _mcp_stdio
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from sosa.tools.mcp import ToolRegistry, make_mcp_tools

        # Suppress subprocess stderr (smithery/server debug output)
        _orig = _mcp_stdio.stdio_client
        _devnull = open(os.devnull, "w")
        _mcp_stdio.stdio_client = lambda server: _orig(server, errlog=_devnull)

        self._mcp_client = MultiServerMCPClient(self.mcp_servers)

        tools_by_server: dict = {}
        for server_name in self.mcp_servers:
            server_tools = await self._mcp_client.get_tools(server_name=server_name)
            tools_by_server[server_name] = server_tools

        registry = ToolRegistry(tools_by_server)
        search_tool, call_tool = make_mcp_tools(registry)

        self.tools = self.tools + [search_tool, call_tool]
        self.model = self._base_model.bind_tools(self.tools)

        return registry

    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------

    def _build_system_prompt(self, prompt: str) -> str:
        return (
            _PROMPT_TEMPLATE
            .replace("<name>", self.name)
            .replace("<system_prompt>", prompt)
            .replace("<workspace_path>", str(self.workspace_path))
            .replace("<soul_memory_path>", str(self.soul_memory_path))
        )

    def build(self):
        graph = StateGraph(AgentState)

        graph.add_node("init", init)
        graph.add_node("cleanup", cleanup)
        graph.add_node("compacter", compacter)
        graph.add_node("react", react)
        graph.add_node("tool_node", ToolNode(self.tools))

        graph.add_edge(START, "init")
        graph.add_edge("init", "cleanup")
        graph.add_edge("cleanup", "compacter")
        graph.add_edge("compacter", "react")
        graph.add_conditional_edges("react", tools_condition, {"tools": "tool_node", END: END})
        graph.add_edge("tool_node", "react")

        self.graph = graph.compile()

    async def run(self, messages: List[AnyMessage]):
        """Async generator that streams new messages as the agent works through its turn."""

        if self.graph is None:
            self.build()

        state: AgentState = {
            "system_prompt": self.system_prompt,
            "soul": "",
            "messages": messages,
            "workspace_path": self.workspace_path,
            "soul_memory_path": self.soul_memory_path,
            "name": self.name,
            "model": self.model,
            "base_model": self._base_model,
            "tools": self.tools,
            "approval_fn": self.approval_fn,
        }

        async for chunk in self.graph.astream(state, stream_mode="updates"):
            for node_name, update in chunk.items():
                updates = update if isinstance(update, list) else [update]
                for u in updates:
                    if not isinstance(u, dict):
                        continue
                    new_messages = u.get("messages", [])
                    if not isinstance(new_messages, list):
                        new_messages = [new_messages]
                    for msg in new_messages:
                        yield msg
