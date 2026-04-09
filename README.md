# Sosa

A LangGraph-based AI agent framework with a focus on safety, modularity, and ease of use. Sosa agents have a 
configurable workspace, per-workspace memory, external tools (including custom MCP servers), a built-in Bash 
terminal, and a persistent personality defined in `<workspace_dir>/soul.md`.

## CLI Usage

Requires Python 3.14+.

Build your virtual environment and install dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your OpenAI API key to a `.env` file in the project root:

```
OPENAI_API_KEY=your-key-here
```

Then run your agent in interactive CLI mode:

```bash
# to rerun in a different terminal session, run `source .venv/bin/activate` first to activate the virtual environment
python -m cli
```

Type your message at the `You ›` prompt and press Enter. The agent will respond and show any tool calls it makes inline. To exit, type `exit` or press `Ctrl+C`.

Commands that fall outside the built-in allowlist will pause and ask for your approval before running — enter `y` to allow or anything else to deny.

To customize the agent's personality or behavior, ask your agent to edit their `soul.md` file accordingly. Changes take effect on the next turn.

The agent also maintains a `memory.md` file in its workspace. It writes to this file to persist information across conversations — it's injected as context every turn, so anything stored there is always available to the agent.

## Developer Usage

```python
from langchain_core.messages import HumanMessage
from models.OpenAI import gpt_5_mini
from sosa.Sosa import Sosa

agent = Sosa(
    model=gpt_5_mini,
    prompt="You are a helpful assistant.",
    workspace_path="./workspace",
)

messages = []
messages.append(HumanMessage(content="Hello!"))
async for msg in agent.run(messages):
    messages.append(msg)
```

## Bash Command Approval

By default, the agent can only run commands from a pre-approved allowlist (see [COMMAND_POLICY.md](COMMAND_POLICY.md)). Any command containing a program not on that list is **denied automatically** unless you pass an `approval_fn`.

`approval_fn` is a function that receives the command string and returns `True` (allow) or `False` (deny). Without it, unapproved commands are always blocked.

```python
def approve(command: str) -> bool:
    answer = input(f"Allow command: {command} [y/N] ").strip().lower()
    return answer == "y"

agent = Sosa(
    model=gpt_5_mini,
    prompt="...",
    workspace_path="./workspace",
    approval_fn=approve,
)
```

## MCP Servers

Sosa supports external tools via the [Model Context Protocol](https://modelcontextprotocol.io). Define your servers and pass them to `build_agent()`.

```python
MCP_SERVERS = {
    "filesystem": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/your/path"],
    },
    "weather": {
        "transport": "sse",
        "url": "http://localhost:8000/mcp",
    },
}

async def main() -> None:
    async with build_agent(mcp_servers=MCP_SERVERS) as agent:
        await session.run(agent)
```

Each key is the server name — it becomes the namespace prefix for that server's tools (e.g. `filesystem__read_file`). The agent discovers tools at startup and exposes them via two meta-tools: `search_tools` to find tools by keyword, and `call_tool` to invoke them.

### Credentials

`stdio` servers are spawned as child processes and inherit a subset of your shell environment automatically, so credentials already in your shell (e.g. via `.env` or `export`) are usually available without any extra config. If you need to pass specific variables explicitly, use the `env` field:

```python
"github": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"]},
}
```

`sse`/`streamable_http` servers you run yourself, so credentials are handled however that server expects (headers, env, etc.).

### Supported transports

| Transport | Required fields |
|---|---|
| `stdio` | `command`, `args` — spawns a local process |
| `sse` | `url` — connects to a running HTTP server |
| `streamable_http` | `url` — connects to a running HTTP server |
| `websocket` | `url` — connects to a WebSocket server |

MCP requires the agent to be used as an async context manager:

```python
async with build_agent() as agent:
    await session.run(agent)
```
