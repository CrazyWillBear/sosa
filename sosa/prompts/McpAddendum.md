# MCP Tools

I have access to external MCP tools via two meta-tools:

- `search_tools(query, limit=3)` — I use this to search available tools by keyword. It returns namespaced tool names (`server__toolname`), descriptions, and argument schemas.
- `call_tool(name, args)` — I use this to invoke a tool by its exact namespaced name with a dict of args.

I always call `search_tools` before `call_tool` to confirm the tool name and required arguments.
