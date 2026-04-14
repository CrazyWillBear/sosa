from pathlib import Path
from typing import TypedDict, List, Annotated, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, Tool
from langgraph.graph import add_messages


class AgentState(TypedDict):


    # Context
    system_prompt: str                                  # System prompt, includes user prompt
    soul: str                                           # Soul.md
    messages: Annotated[List[AnyMessage], add_messages] # Includes tool calls and responses
    workspace_path: Path                                # Path to agent workspace (per-workspace files/memory)
    soul_memory_path: Path                              # Path to soul.md and universal memory.md

    # State
    name: str
    model: BaseChatModel | Runnable
    base_model: BaseChatModel
    tools: List[BaseTool | Tool]
    approval_fn: Callable[[str], bool]