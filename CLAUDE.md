# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

Requires Python 3.14+.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add API keys to `.env` in the project root:
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GROQ_API_KEY=...
```

**CLI (interactive chat):**
```bash
python -m cli
```

## Running Tests

```bash
pytest
```

Tests live in `tests/`. This is the project's done-check — run it before declaring any change complete.

## Architecture

Sosa is a LangGraph-based ReAct agent. The core class is `sosa/Sosa.py`, which compiles a `StateGraph` and exposes a `run()` async generator that yields new messages as the agent works through its turn.

### Graph Flow

```
START → init → cleanup → compacter → staleness → react → tool_node → (react | END)
```

- **init** (`sosa/graph/nodes/init.py`): Reads `soul.md` from `soul_memory_path` (creating it from `sosa/prompts/Soul.md` if absent). Ensures both universal `memory.md` and workspace `memory.md` exist.
- **cleanup** (`sosa/graph/nodes/cleanup.py`): Stale `read_file` tool results are replaced with a placeholder each turn so they don't bloat context.
- **compacter** (`sosa/graph/nodes/compacter.py`): When message history exceeds ~70k tokens, summarizes all but the last 10 messages using the base model and replaces them with a `SystemMessage` summary.
- **staleness** (`sosa/graph/nodes/staleness.py`): Compares each tracked file's current on-disk hash against its stored baseline. Injects a single `SystemMessage` naming any changed or deleted files. Refreshes baselines so each change is reported only once.
- **react** (`sosa/graph/nodes/react.py`): Invokes the model with the full context (system prompt + soul.md + memory.md + messages).
- **tool_node**: LangGraph's `ToolNode` dispatches tool calls. The loop ends when the model makes no tool calls.

### Context Construction

`sosa/schemas/Context.py` assembles what the model sees each turn: the system prompt (from `sosa/prompts/Prompt.md` template filled with name/prompt/workspace), `soul.md`, `memory.md`, and the message history. If MCP tools are loaded, a `McpAddendum.md` system message is appended.

### Basic Tools

By default, every agent includes: `run_bash_command`, `write_file`, `edit_file`, `read_file`. Additional tools can be passed to `Sosa(tools=[...])`. Pass `include_basic_tools=False` to opt out of these defaults entirely.

### Bash Command Policy

`sosa/tools/Bash.py` checks every program name in a command against an allowlist (`_ALLOWED`). Commands with non-allowlisted programs are passed to `approval_fn`. The allowlist mirrors `COMMAND_POLICY.md`. Output is capped at ~5000 tokens; cwd defaults to `workspace_path`.

### Persistent Memory

Two separate memory locations, configured independently:

- **`soul_memory_path/`** (default `~/sosa/`) — shared across all workspaces:
  - `soul.md` — personality/behavior config, editable to change agent character
  - `memory.md` — universal memory injected every turn
- **`workspace_path/`** (default `./workspace/`) — per-workspace:
  - `memory.md` — workspace-specific memory injected every turn

Both `memory.md` files are injected as system messages every turn. The agent writes to them to persist information across conversations.

### Skills

`skills_path` (default `~/sosa/skills/`) points to a directory of subdirectories, each representing a skill. The skill names are listed in the system prompt so the agent knows what capabilities are available. Skills are not auto-invoked; the agent decides when to use them.

### MCP Support

MCP servers are configured in `cli/config.py` (or inline) as a dict passed to `Sosa(mcp_servers=...)`. When present, the agent must be used as an async context manager (`async with build_agent() as agent`). MCP tools are namespaced by server name and exposed via two meta-tools: `search_tools` and `call_tool`.

### Models

Any `BaseChatModel` can be passed to `Sosa(model=...)`. Pre-configured instances live in `models/`:

| File | Exports |
|------|---------|
| `models/Anthropic.py` | `claude_opus_4_6`, `claude_sonnet_4_6`, `claude_haiku_4_5`, `claude_sonnet_3_7` |
| `models/OpenAI.py` | `gpt_5_mini`, `gpt_5`, `gpt_5_4`, `gpt_4o` |
| `models/Groq.py` | `oss_120b` |
| `models/Ollama.py` | `llama_m` |

Active model is set via `MODEL` in `cli/config.py`.

### CLI Layer

- `cli/config.py`: `build_agent()` factory — change model, prompt, or MCP servers here
- `cli/session.py`: async chat loop that calls `agent.run()` and delegates display
- `cli/display.py`: Rich-based rendering for tool calls, results, and agent responses
