import os
from pathlib import Path

from models.Groq import oss_120b
from models.OpenAI import gpt_5_mini, gpt_5, gpt_5_4, gpt_4o
from models.Anthropic import claude_opus_4_6, claude_sonnet_4_6, claude_haiku_4_5, claude_sonnet_3_7
from sosa.Sosa import Sosa
from cli import display

# This is your home directory, e.g., /home/username or C:\Users\username, provided to you for convenience.
HOME_DIR = Path.home()

# Set your soul and memory path here. This is where the agent will store its soul and universal memory.
SOUL_MEMORY_DIR = (HOME_DIR / "sosa").resolve()
SOUL_MEMORY_DIR.mkdir(exist_ok=True)

# Set your workspace path here. This is where the agent will store its per-workspace memory and any files/directories it creates.
WORKSPACE = Path("./workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)

# Set your model here.
# OpenAI:       gpt_5_mini, gpt_5, gpt_5_4, gpt_4o
# Anthropic:    claude_opus_4_6, claude_sonnet_4_6, claude_haiku_4_5, claude_sonnet_3_7
# Groq:         oss_120b
MODEL = gpt_5

# Set your agent's name and prompt.
AGENT_NAME = "Sosa"
BASE_PROMPT = "You are a general-purpose assistant. Help the user with whatever they need."

# Hook up any MCP servers you want to use here.
MCP_SERVERS = {
    "exa": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "exa-mcp-server"],
        "env": {"EXA_API_KEY": os.environ.get("EXA_API_KEY", "")},
    },
}

# WARNING!!! Don't touch this unless you know what you're doing.
def build_agent(mcp_servers: dict | None = None) -> Sosa:
    return Sosa(
        model=MODEL,
        prompt=BASE_PROMPT,
        workspace_path=WORKSPACE,
        soul_memory_path=SOUL_MEMORY_DIR,
        approval_fn=display.approval_prompt,
        name=AGENT_NAME,
        mcp_servers=mcp_servers
    )
