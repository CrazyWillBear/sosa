from langchain_core.messages import ToolMessage, AIMessage, RemoveMessage

from sosa.schemas.AgentState import AgentState

_READ_PLACEHOLDER = "<cleaned, read file again to see contents>"
_BASH_PLACEHOLDER = "<truncated to 250 tokens>"
_WRITE_PLACEHOLDER = "<This content has been removed. Reread the file to see what you wrote.>"
_BASH_CHAR_LIMIT = 250 * 4


def cleanup(state: AgentState):
    messages = state.get("messages", [])

    # Build map of tool_call_id -> tool_name from AIMessages
    tool_call_names = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls:
                tool_call_names[tc["id"]] = tc["name"]

    removals = []
    replacements = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_name = tool_call_names.get(msg.tool_call_id)

            if tool_name == "read_file" and msg.content != _READ_PLACEHOLDER:
                removals.append(RemoveMessage(id=msg.id))
                replacements.append(msg.model_copy(update={"content": _READ_PLACEHOLDER}))

            elif tool_name == "run_bash_command" and len(msg.content) > _BASH_CHAR_LIMIT:
                removals.append(RemoveMessage(id=msg.id))
                replacements.append(msg.model_copy(update={"content": msg.content[:_BASH_CHAR_LIMIT] + "\n[truncated]"}))

        elif isinstance(msg, AIMessage):
            new_tool_calls = []
            changed = False
            for tc in msg.tool_calls:
                if tc["name"] in ("write_file", "edit_file") and tc["args"].get("content") not in (None, _WRITE_PLACEHOLDER):
                    tc = {**tc, "args": {**tc["args"], "content": _WRITE_PLACEHOLDER}}
                    changed = True
                elif tc["name"] == "edit_file" and tc["args"].get("string_to_replace") not in (None, _WRITE_PLACEHOLDER):
                    tc = {**tc, "args": {**tc["args"], "string_to_replace": _WRITE_PLACEHOLDER, "replacement": _WRITE_PLACEHOLDER}}
                    changed = True
                new_tool_calls.append(tc)
            if changed:
                removals.append(RemoveMessage(id=msg.id))
                replacements.append(msg.model_copy(update={"tool_calls": new_tool_calls}))

    if not removals:
        return {}

    return {"messages": removals + replacements}
