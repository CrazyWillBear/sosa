# MCP Tools

You have access to external MCP tools via two meta-tools:

- `search_tools(query, limit=3)` — search available tools by keyword. Returns namespaced tool names (`server__toolname`), descriptions, and argument schemas.
- `call_tool(name, args)` — invoke a tool by its exact namespaced name with a dict of args.

Always call `search_tools` before `call_tool` to confirm the tool name and required arguments.
