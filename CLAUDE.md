# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Agent

**CLI (interactive chat):**
```bash
python -m cli
```

## Architecture

Sosa is a LangGraph-based ReAct agent. The core class is `sosa/Sosa.py`, which compiles a `StateGraph` and exposes a `run()` generator that yields new messages as the agent works through its turn.

### Graph Flow

```
START → init → cleanup → react → tool_node → (react | END)
```

- **init** (`sosa/graph/nodes/init.py`): Reads `soul.md` from the workspace (creating it from `sosa/prompts/Soul.md` if absent). Also ensures `memory.md` exists.
- **cleanup** (`sosa/graph/nodes/cleanup.py`): Stale `read_file` tool results are replaced with a placeholder each turn so they don't bloat context.
- **react** (`sosa/graph/nodes/react.py`): Invokes the model with the full context (system prompt + soul.md + memory.md + messages).
- **tool_node**: LangGraph's `ToolNode` dispatches tool calls. The loop ends when `end_turn` is called (sets `turn_over = True`) or when the model makes no tool calls.

### Context Construction

`sosa/schemas/Context.py` assembles what the model sees each turn: the system prompt (from `sosa/prompts/Prompt.md` template filled with name/prompt/workspace), `soul.md`, `memory.md`, and the message history. If MCP tools are loaded, a `McpAddendum.md` system message is appended.

### Basic Tools

By default, every agent includes: `run_bash_command`, `write_file`, `edit_file`, `read_file`. Additional tools can be passed to `Sosa(tools=[...])`. Pass `include_basic_tools=False` to opt out of these defaults entirely.

### Bash Command Policy

`sosa/tools/Bash.py` checks every program name in a command against an allowlist (`_ALLOWED`). Commands with non-allowlisted programs are passed to `approval_fn`. The allowlist mirrors `COMMAND_POLICY.md`. Output is capped at ~5000 tokens; cwd defaults to `workspace_path`.

### Persistent Memory

The agent maintains two files in its workspace:
- `workspace/soul.md` — personality/behavior config, editable to change agent character
- `workspace/memory.md` — injected as a system message every turn; the agent writes to it to persist information across conversations

### MCP Support

MCP servers are configured in `cli/config.py` (or inline) as a dict passed to `Sosa(mcp_servers=...)`. When present, the agent must be used as an async context manager (`async with build_agent() as agent`). MCP tools are namespaced by server name and exposed via two meta-tools: `search_tools` and `call_tool`.

### Models

`models/Groq.py` exports `oss_120b` (a `ChatGroq` instance). To use a different model, pass any `BaseChatModel` to `Sosa(model=...)`.

### CLI Layer

- `cli/config.py`: `build_agent()` factory — change model, prompt, or MCP servers here
- `cli/session.py`: async chat loop that calls `agent.run()` and delegates display
- `cli/display.py`: Rich-based rendering for tool calls, results, and agent responses
