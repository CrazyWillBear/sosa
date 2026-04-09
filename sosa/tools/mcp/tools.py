import json

from langchain_core.tools import tool

from sosa.tools.mcp.registry import ToolRegistry


def make_mcp_tools(registry: ToolRegistry):
    """
    Returns (search_tools, call_tool) as LangChain tools bound to the given registry.
    These are the only two tools Sosa needs to interact with all connected MCP servers.
    """

    @tool
    def search_tools(query: str, limit: int = 2) -> str:
        """Search available MCP tools by keyword.
        Returns tool names (namespaced as server__toolname), descriptions, and arg schemas.
        Always call this before call_tool to find the correct tool name and understand its args."""
        return registry.search(query, limit=limit)

    @tool
    async def call_tool(name: str, arguments: str) -> str:
        """Invoke an MCP tool by its exact namespaced name (server__toolname).
        arguments must be a JSON string, e.g. '{"url": "https://example.com"}'.
        Always call search_tools first to confirm the tool name and required arguments."""
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as e:
            return f"Invalid JSON in arguments: {e}"
        return await registry.call(name, parsed)

    return search_tools, call_tool
