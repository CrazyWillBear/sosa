import asyncio

from dotenv import load_dotenv
load_dotenv()

from cli import display
from cli.config import build_agent, AGENT_NAME, MCP_SERVERS
from cli import session


async def main() -> None:
    display.welcome(AGENT_NAME)

    if MCP_SERVERS:
        async with build_agent(mcp_servers=MCP_SERVERS) as agent:
            await session.run(agent)
    else:
        agent = build_agent()
        await session.run(agent)


if __name__ == "__main__":
    asyncio.run(main())
