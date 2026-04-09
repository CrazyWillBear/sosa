from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage

from sosa.schemas.AgentState import AgentState

_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "Compacter.md").read_text()
_THRESHOLD = 70_000 * 4  # ~70k tokens in chars
_KEEP_LAST = 10


def compacter(state: AgentState):
    messages = state.get("messages", [])

    total_chars = sum(
        len(m.content) if isinstance(m.content, str) else sum(
            len(p.get("text", "")) for p in m.content if isinstance(p, dict)
        )
        for m in messages
    )

    if total_chars <= _THRESHOLD or len(messages) <= _KEEP_LAST:
        return {}

    to_summarize = messages[:-_KEEP_LAST]
    history_lines = []
    for msg in to_summarize:
        if isinstance(msg, HumanMessage):
            history_lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.content:
                history_lines.append(f"Agent: {msg.content}")
            for tc in msg.tool_calls:
                args_preview = {k: (v[:200] + "...") if isinstance(v, str) and len(v) > 200 else v
                                for k, v in tc["args"].items()}
                history_lines.append(f"Agent called {tc['name']}({args_preview})")
        elif isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            preview = content[:300] + "..." if len(content) > 300 else content
            history_lines.append(f"Tool result: {preview}")

    history_text = "\n".join(history_lines)

    model = state.get("base_model")
    response = model.invoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=history_text),
    ])

    removals = [RemoveMessage(id=m.id) for m in to_summarize]
    summary_msg = SystemMessage(content=f"Previous conversation summary:\n\n{response.content}")

    return {"messages": removals + [summary_msg]}
