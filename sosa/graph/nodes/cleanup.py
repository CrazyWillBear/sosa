from pathlib import Path

from langchain_core.messages import ToolMessage, AIMessage, RemoveMessage

from sosa.schemas.AgentState import AgentState

_READ_PLACEHOLDER = "<cleaned, read file again to see contents>"
_WRITE_PLACEHOLDER = "<This content has been removed. Reread the file to see what you wrote.>"
_BASH_CHAR_LIMIT = 500 * 4
_MEMORY_OPS = {"read_file", "write_file", "edit_file"}
_BASH_STALE_WINDOW = 10  # bash outputs within this distance from the end are not truncated


def _is_memory_file(file_path: str) -> bool:
    return Path(file_path).name == "memory.md"


def cleanup(state: AgentState):
    messages = state.get("messages", [])

    # Build map of tool_call_id -> (tool_name, file_path) from AIMessages
    tool_call_info = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls:
                tool_call_info[tc["id"]] = (tc["name"], tc["args"].get("file_path", ""))

    # For each memory.md file, find the most recent operation (last one wins)
    latest_memory_op = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls:
                file_path = tc["args"].get("file_path", "")
                if file_path and _is_memory_file(file_path) and tc["name"] in _MEMORY_OPS:
                    latest_memory_op[file_path] = (tc["id"], tc["name"])

    # Track the most recent file operation (read/write/edit) per file path
    latest_op: dict[str, str] = {}  # file_path -> tool_call_id
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls:
                if tc["name"] in _MEMORY_OPS:
                    file_path = tc["args"].get("file_path", "")
                    if file_path:
                        latest_op[file_path] = tc["id"]

    # Only preserve a read if it's the most recent operation on that file AND preserve=True.
    # If a write/edit happened after the read, the read content is stale and should be cleared.
    latest_preserved_read: dict[str, str] = {}  # file_path -> tool_call_id
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls:
                if tc["name"] == "read_file" and tc["args"].get("preserve"):
                    file_path = tc["args"].get("file_path", "")
                    if file_path and latest_op.get(file_path) == tc["id"]:
                        latest_preserved_read[file_path] = tc["id"]

    preserve = {tc_id for tc_id, _ in latest_memory_op.values()}
    preserve.update(latest_preserved_read.values())

    bash_stale_cutoff = max(0, len(messages) - _BASH_STALE_WINDOW)
    removals = []
    replacements = []

    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage):
            tool_name, file_path = tool_call_info.get(msg.tool_call_id, (None, ""))

            if tool_name == "read_file":
                if msg.tool_call_id in preserve:
                    pass  # preserved — keep as-is
                elif msg.content != _READ_PLACEHOLDER:
                    removals.append(RemoveMessage(id=msg.id))
                    replacements.append(msg.model_copy(update={"content": _READ_PLACEHOLDER}))

            elif tool_name == "run_bash_command" and i < bash_stale_cutoff:
                if len(msg.content) > _BASH_CHAR_LIMIT:
                    removals.append(RemoveMessage(id=msg.id))
                    replacements.append(msg.model_copy(update={"content": msg.content[:_BASH_CHAR_LIMIT] + "\n[truncated]"}))

        elif isinstance(msg, AIMessage):
            new_tool_calls = []
            changed = False
            for tc in msg.tool_calls:
                if tc["id"] not in preserve:
                    if tc["name"] == "write_file" and tc["args"].get("content") not in (None, _WRITE_PLACEHOLDER):
                        tc = {**tc, "args": {**tc["args"], "content": _WRITE_PLACEHOLDER}}
                        changed = True
                    elif tc["name"] == "edit_file":
                        new_args = dict(tc["args"])
                        tc_changed = False
                        if new_args.get("string_to_replace") not in (None, _WRITE_PLACEHOLDER):
                            new_args["string_to_replace"] = _WRITE_PLACEHOLDER
                            tc_changed = True
                        if new_args.get("replacement") not in (None, _WRITE_PLACEHOLDER):
                            new_args["replacement"] = _WRITE_PLACEHOLDER
                            tc_changed = True
                        if tc_changed:
                            tc = {**tc, "args": new_args}
                            changed = True
                new_tool_calls.append(tc)
            if changed:
                removals.append(RemoveMessage(id=msg.id))
                replacements.append(msg.model_copy(update={"tool_calls": new_tool_calls}))

    if not removals:
        return {}

    return {"messages": removals + replacements}
