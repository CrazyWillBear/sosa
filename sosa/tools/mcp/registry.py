from typing import Any

from langchain_core.tools import BaseTool


class ToolRegistry:

    def __init__(self, tools_by_server: dict[str, list[BaseTool]]):
        # Namespace every tool as {server}__{name}
        self._tools: dict[str, BaseTool] = {}
        self._servers: dict[str, str] = {}  # namespaced name → server label

        for server, tools in tools_by_server.items():
            for tool in tools:
                key = f"{server}__{tool.name}"
                self._tools[key] = tool
                self._servers[key] = server

        self._cache: dict[tuple[str, int], str] = {}

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 2) -> str:
        cache_key = (query.strip().lower(), limit)
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._do_search(query, limit)
        self._cache[cache_key] = result
        return result

    def _do_search(self, query: str, limit: int) -> str:
        query_words = query.lower().split()

        scored: list[tuple[int, str, BaseTool]] = []
        for name, tool in self._tools.items():
            text = (name + " " + (tool.description or "")).lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, name, tool))

        scored.sort(key=lambda x: -x[0])
        top = scored[:limit]

        if not top:
            return f"No tools found matching '{query}'. Try broader search terms."

        lines: list[str] = []
        for _, name, tool in top:
            server = self._servers[name]
            lines.append(f"{name}  [{server}]")
            if tool.description:
                lines.append(f"  {tool.description}")
            schema = _readable_schema(tool)
            if schema:
                lines.append("  args:")
                for field, info in schema.items():
                    lines.append(f"    {field}: {info}")
            lines.append("")

        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------
    # Call
    # ------------------------------------------------------------------

    async def call(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return (
                f"Unknown tool '{name}'. "
                "Use search_tools to find the correct namespaced tool name."
            )

        try:
            return str(await tool.ainvoke(args))
        except Exception as e:
            return f"Error calling '{name}': {e}"

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)


def _readable_schema(tool: BaseTool) -> dict[str, str]:
    """Return {field_name: human-readable type+description} from a tool's args schema."""
    if not tool.args_schema:
        return {}

    try:
        # Pydantic v2
        schema = tool.args_schema.model_json_schema()
    except AttributeError:
        try:
            schema = tool.args_schema.schema()
        except Exception:
            return {}

    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    out: dict[str, str] = {}

    for field, info in props.items():
        ftype = info.get("type") or _first_type(info.get("anyOf", []))
        req = "required" if field in required else "optional"
        desc = info.get("description", "")
        annotation = f"({ftype}, {req})"
        out[field] = f"{annotation} — {desc}" if desc else annotation

    return out


def _first_type(anyof: list[dict]) -> str:
    for entry in anyof:
        t = entry.get("type")
        if t and t != "null":
            return t
    return "any"
