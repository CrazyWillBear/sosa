"""Tests for the cleanup node (issue #20).

Covers:
- Non-memory read_file results are replaced with placeholder (stale cleanup works).
- read_file results for files under soul_memory_path/memory/ are pinned (not cleaned).
- write_file / edit_file args for memory/ files are pinned (content not cleared).
- write_file / edit_file args for non-memory files ARE cleared.
- No special-casing keyed on the literal 'memory.md' basename exists in cleanup.py.
"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from sosa.graph.nodes.cleanup import cleanup, _READ_PLACEHOLDER, _WRITE_PLACEHOLDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(messages: list, soul_memory_path: Path | None = None) -> dict:
    """Build a minimal state dict for cleanup tests."""
    state: dict = {"messages": messages}
    if soul_memory_path is not None:
        state["soul_memory_path"] = soul_memory_path
    return state


def _ai_tool_call(tc_id: str, name: str, args: dict) -> AIMessage:
    """Create an AIMessage with a single tool call."""
    return AIMessage(content="", tool_calls=[{"id": tc_id, "name": name, "args": args}])


def _tool_result(tc_id: str, content: str) -> ToolMessage:
    """Create a ToolMessage (tool result)."""
    return ToolMessage(content=content, tool_call_id=tc_id)


# ---------------------------------------------------------------------------
# AC: No 'memory.md' literal in cleanup.py
# ---------------------------------------------------------------------------


class TestNoMemoryMdLiteral:
    def test_no_memory_md_literal_in_source(self) -> None:
        """cleanup.py must not contain any special-casing keyed on 'memory.md'."""
        cleanup_source = Path(__file__).parent.parent / "sosa" / "graph" / "nodes" / "cleanup.py"
        source_text = cleanup_source.read_text()
        # The literal 'memory.md' must not appear as a hardcoded filename predicate
        assert '"memory.md"' not in source_text, (
            "cleanup.py still contains '\"memory.md\"' — dead special-casing that must be removed"
        )
        assert "'memory.md'" not in source_text, (
            "cleanup.py still contains \"'memory.md'\" — dead special-casing that must be removed"
        )


# ---------------------------------------------------------------------------
# AC: Non-memory reads are still cleaned (regression guard)
# ---------------------------------------------------------------------------


class TestNonMemoryReadsCleaned:
    def test_ordinary_read_file_is_replaced_with_placeholder(self, tmp_path: Path) -> None:
        """A read_file result for an ordinary file should be replaced with _READ_PLACEHOLDER."""
        soul_path = tmp_path / "soul"
        soul_path.mkdir()

        tc_id = "tc-read-1"
        ordinary_file = str(tmp_path / "workspace" / "some_file.txt")

        messages = [
            _ai_tool_call(tc_id, "read_file", {"file_path": ordinary_file}),
            _tool_result(tc_id, "file contents here"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        # result has removals + replacement messages
        all_msgs = result.get("messages", [])
        tool_msgs = [m for m in all_msgs if isinstance(m, ToolMessage) and m.tool_call_id == tc_id]
        assert tool_msgs, "Expected a ToolMessage replacement in cleanup result"
        assert tool_msgs[0].content == _READ_PLACEHOLDER

    def test_ordinary_write_file_content_is_cleared(self, tmp_path: Path) -> None:
        """A write_file for an ordinary file should have its content cleared."""
        soul_path = tmp_path / "soul"
        soul_path.mkdir()

        tc_id = "tc-write-1"
        ordinary_file = str(tmp_path / "workspace" / "output.txt")

        messages = [
            _ai_tool_call(tc_id, "write_file", {"file_path": ordinary_file, "content": "big content here"}),
            _tool_result(tc_id, "written"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        all_msgs = result.get("messages", [])
        ai_msgs = [m for m in all_msgs if isinstance(m, AIMessage)]
        assert ai_msgs, "Expected an AIMessage replacement in cleanup result"
        tc_args = ai_msgs[0].tool_calls[0]["args"]
        assert tc_args["content"] == _WRITE_PLACEHOLDER


# ---------------------------------------------------------------------------
# AC: memory/ files under soul_memory_path are pinned
# ---------------------------------------------------------------------------


class TestMemoryDirFilesPinned:
    def test_memory_dir_read_is_pinned(self, tmp_path: Path) -> None:
        """read_file for a soul_memory_path/memory/<name>.md must NOT be replaced."""
        soul_path = tmp_path / "soul"
        (soul_path / "memory").mkdir(parents=True)
        mem_file = str(soul_path / "memory" / "work_context.md")

        tc_id = "tc-mem-read-1"
        messages = [
            _ai_tool_call(tc_id, "read_file", {"file_path": mem_file}),
            _tool_result(tc_id, "fact: the project uses Python"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        # Either result is empty (no changes) or the ToolMessage was NOT replaced with placeholder
        all_msgs = result.get("messages", [])
        tool_msgs = [m for m in all_msgs if isinstance(m, ToolMessage) and m.tool_call_id == tc_id]
        # If there's a replacement for this tc_id, it must NOT be the placeholder
        for m in tool_msgs:
            assert m.content != _READ_PLACEHOLDER, (
                "memory/ file read was cleaned — it should be pinned"
            )

    def test_memory_dir_write_is_pinned(self, tmp_path: Path) -> None:
        """write_file for a soul_memory_path/memory/<name>.md must NOT have content cleared."""
        soul_path = tmp_path / "soul"
        (soul_path / "memory").mkdir(parents=True)
        mem_file = str(soul_path / "memory" / "new_fact.md")
        original_content = "---\ndescription: a fact\ntype: fact\n---\nbody"

        tc_id = "tc-mem-write-1"
        messages = [
            _ai_tool_call(tc_id, "write_file", {"file_path": mem_file, "content": original_content}),
            _tool_result(tc_id, "written"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        all_msgs = result.get("messages", [])
        ai_msgs = [m for m in all_msgs if isinstance(m, AIMessage)]
        # If there's a replacement, content must not be _WRITE_PLACEHOLDER
        for m in ai_msgs:
            for tc in m.tool_calls:
                if tc["id"] == tc_id:
                    assert tc["args"].get("content") != _WRITE_PLACEHOLDER, (
                        "memory/ file write was cleaned — it should be pinned"
                    )

    def test_memory_dir_edit_is_pinned(self, tmp_path: Path) -> None:
        """edit_file for a soul_memory_path/memory/<name>.md must NOT have args cleared."""
        soul_path = tmp_path / "soul"
        (soul_path / "memory").mkdir(parents=True)
        mem_file = str(soul_path / "memory" / "existing_fact.md")

        tc_id = "tc-mem-edit-1"
        messages = [
            _ai_tool_call(tc_id, "edit_file", {
                "file_path": mem_file,
                "string_to_replace": "old content",
                "replacement": "new content",
            }),
            _tool_result(tc_id, "edited"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        all_msgs = result.get("messages", [])
        ai_msgs = [m for m in all_msgs if isinstance(m, AIMessage)]
        for m in ai_msgs:
            for tc in m.tool_calls:
                if tc["id"] == tc_id:
                    assert tc["args"].get("string_to_replace") != _WRITE_PLACEHOLDER, (
                        "memory/ file edit string_to_replace was cleaned — it should be pinned"
                    )
                    assert tc["args"].get("replacement") != _WRITE_PLACEHOLDER, (
                        "memory/ file edit replacement was cleaned — it should be pinned"
                    )

    def test_only_most_recent_memory_op_pinned_per_file(self, tmp_path: Path) -> None:
        """Only the most recent op on a given memory/ file is pinned; older reads are cleaned."""
        soul_path = tmp_path / "soul"
        (soul_path / "memory").mkdir(parents=True)
        mem_file = str(soul_path / "memory" / "context.md")

        tc_read_old = "tc-mem-old"
        tc_write_new = "tc-mem-new"
        messages = [
            # Older read
            _ai_tool_call(tc_read_old, "read_file", {"file_path": mem_file}),
            _tool_result(tc_read_old, "old read content"),
            # Newer write — the read is now stale
            _ai_tool_call(tc_write_new, "write_file", {"file_path": mem_file, "content": "new body"}),
            _tool_result(tc_write_new, "written"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        all_msgs = result.get("messages", [])
        # Old read result should be replaced with placeholder
        tool_msgs = [m for m in all_msgs if isinstance(m, ToolMessage) and m.tool_call_id == tc_read_old]
        assert tool_msgs, "Expected replacement for the older read"
        assert tool_msgs[0].content == _READ_PLACEHOLDER, (
            "Older read on a memory/ file should be cleaned when a newer op exists"
        )

    def test_non_memory_subpath_not_pinned(self, tmp_path: Path) -> None:
        """A file at soul_memory_path/other/file.md is NOT under memory/ and must not be pinned."""
        soul_path = tmp_path / "soul"
        (soul_path / "other").mkdir(parents=True)
        non_mem_file = str(soul_path / "other" / "notes.md")

        tc_id = "tc-nonmem-1"
        messages = [
            _ai_tool_call(tc_id, "read_file", {"file_path": non_mem_file}),
            _tool_result(tc_id, "some notes"),
        ]
        state = _make_state(messages, soul_memory_path=soul_path)
        result = cleanup(state)

        all_msgs = result.get("messages", [])
        tool_msgs = [m for m in all_msgs if isinstance(m, ToolMessage) and m.tool_call_id == tc_id]
        assert tool_msgs, "Expected replacement for non-memory file"
        assert tool_msgs[0].content == _READ_PLACEHOLDER, (
            "File outside soul_memory_path/memory/ should be cleaned"
        )
