from sosa.schemas.AgentState import AgentState
from sosa.schemas.Context import Context


def react(state: AgentState):
    """Reviews the agent's state and determines the next action. Optionally can end turn via tool call."""

    context = Context(state)
    context_messages = context.to_messages()

    total_chars = sum(
        len(m.content) if isinstance(m.content, str) else sum(
            len(p.get("text", "")) for p in m.content if isinstance(p, dict)
        )
        for m in context_messages
    )
    print(f"  [~{total_chars // 4:,} tokens in context]")

    model = state.get("model")
    response = model.invoke(context_messages)
    return {"messages": response}
