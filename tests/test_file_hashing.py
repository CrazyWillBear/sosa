"""Tests for file content hashing (issue #4).

Covers:
- Unit tests for sosa.tools.hashing.hash_file helper
- Integration tests for read_file recording hashes in agent state
"""

import hashlib
import tempfile
from pathlib import Path

import pytest

from sosa.tools.hashing import hash_file


# ---------------------------------------------------------------------------
# Unit tests: hash_file helper
# ---------------------------------------------------------------------------


class TestHashFile:
    def test_returns_hex_string(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        f.write_text("hello world")
        result = hash_file(f)
        # SHA-256 hex digest is 64 chars
        assert isinstance(result, str)
        assert len(result) == 64

    def test_matches_manual_sha256(self, tmp_path: Path) -> None:
        content = b"deterministic content"
        f = tmp_path / "det.txt"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert hash_file(f) == expected

    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        content = "identical content"
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text(content)
        b.write_text(content)
        assert hash_file(a) == hash_file(b)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("foo")
        b.write_text("bar")
        assert hash_file(a) != hash_file(b)

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        f = tmp_path / "p.txt"
        f.write_text("path object")
        # Should work with a Path as well as a str
        assert hash_file(f) == hash_file(str(f))

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "nonexistent.txt")

    def test_hash_changes_when_content_changes(self, tmp_path: Path) -> None:
        f = tmp_path / "mutable.txt"
        f.write_text("version 1")
        h1 = hash_file(f)
        f.write_text("version 2")
        h2 = hash_file(f)
        assert h1 != h2


# ---------------------------------------------------------------------------
# Integration tests: read_file records hashes in agent state
# ---------------------------------------------------------------------------


def _invoke_read_file(target: Path, tmp_path: Path, call_id: str):
    """Invoke read_file as LangChain expects when InjectedToolCallId is used.

    Tools with InjectedToolCallId must be invoked with a full ToolCall dict,
    not a plain args dict.
    """
    from sosa.tools.FileOps import read_file

    tool_call = {
        "name": "read_file",
        "args": {"file_path": str(target)},
        "id": call_id,
        "type": "tool_call",
    }
    # Provide injected state values separately via config
    config = {
        "configurable": {
            "workspace_path": tmp_path,
            "soul_memory_path": tmp_path,
            "approval_fn": lambda _: True,
            "file_hashes": {},
        }
    }
    return read_file.invoke(tool_call, config=config)


class TestReadFileRecordsHash:
    """Exercises the read_file tool and checks that file_hashes is populated."""

    def test_read_file_populates_hash(self, tmp_path: Path) -> None:
        """After read_file runs, the file's hash should be in state."""
        from langgraph.types import Command

        target = tmp_path / "notes.txt"
        target.write_text("some content")

        result = _invoke_read_file(target, tmp_path, "test-call-id-1")

        assert isinstance(result, Command), "read_file should return Command when hashing"
        update = result.update
        assert isinstance(update, dict)
        assert "file_hashes" in update
        assert str(target) in update["file_hashes"]

        stored_hash = update["file_hashes"][str(target)]
        assert stored_hash == hash_file(target)

    def test_read_file_updates_hash_when_content_changes(self, tmp_path: Path) -> None:
        """Calling read_file after content changes should yield the new hash."""
        from langgraph.types import Command

        target = tmp_path / "notes.txt"
        target.write_text("original")

        result1 = _invoke_read_file(target, tmp_path, "test-call-id-2a")
        assert isinstance(result1, Command)
        hash1 = result1.update["file_hashes"][str(target)]

        # Mutate the file
        target.write_text("modified")

        result2 = _invoke_read_file(target, tmp_path, "test-call-id-2b")
        assert isinstance(result2, Command)
        hash2 = result2.update["file_hashes"][str(target)]

        assert hash1 != hash2
        assert hash2 == hash_file(target)

    def test_read_file_tool_message_carries_content(self, tmp_path: Path) -> None:
        """The ToolMessage in Command.update should contain the file content."""
        from langgraph.types import Command
        from langchain_core.messages import ToolMessage

        target = tmp_path / "data.txt"
        content = "line one\nline two\n"
        target.write_text(content)

        result = _invoke_read_file(target, tmp_path, "test-call-id-3")

        assert isinstance(result, Command)
        messages = result.update.get("messages", [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert tool_msgs, "Command.update should have a ToolMessage"
        assert content in tool_msgs[0].content

    def test_file_hashes_reducer_merges(self) -> None:
        """The file_hashes reducer should merge dicts (not replace them)."""
        from sosa.schemas.AgentState import merge_file_hashes

        existing = {"a.txt": "hash1", "b.txt": "hash2"}
        update = {"b.txt": "hash2_new", "c.txt": "hash3"}
        result = merge_file_hashes(existing, update)
        assert result == {"a.txt": "hash1", "b.txt": "hash2_new", "c.txt": "hash3"}

    def test_agent_state_has_file_hashes_field(self) -> None:
        """AgentState TypedDict should declare the file_hashes field."""
        from sosa.schemas.AgentState import AgentState
        import typing
        hints = typing.get_type_hints(AgentState, include_extras=True)
        assert "file_hashes" in hints, "AgentState must have a file_hashes field"
