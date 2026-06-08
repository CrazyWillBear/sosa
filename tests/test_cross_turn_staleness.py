"""Integration test for cross-turn staleness detection (issue #7).

Drives the real Sosa.run() graph across two turns with a mocked model to verify
that file_hashes recorded during turn N are visible to the staleness node on
turn N+1, without requiring live API keys.

Acceptance criteria exercised:
- AC1: Changed file → staleness SystemMessage naming it appears on turn 2.
- AC2: Deleted file → staleness SystemMessage naming it appears on turn 2.
- AC3: Unchanged file across turns → no staleness message; change reported once only.
- AC4: New Sosa instance starts with empty hash store.
- AC5: This test drives the real graph (not hand-built staleness() calls).
"""

import asyncio
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall

from sosa.Sosa import Sosa
from sosa.tools.hashing import hash_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_call_message(tool_name: str, args: dict, call_id: str) -> AIMessage:
    """Create an AIMessage that requests a single tool call."""
    tc = ToolCall(name=tool_name, args=args, id=call_id)
    return AIMessage(content="", tool_calls=[tc])


def _noop_ai_message() -> AIMessage:
    """An AIMessage with no tool calls — signals end of turn."""
    return AIMessage(content="Done.")


def _collect_staleness_messages(messages: list) -> list[SystemMessage]:
    """Filter messages for SystemMessages that contain staleness text."""
    return [
        m for m in messages
        if isinstance(m, SystemMessage)
        and ("changed" in m.content.lower() or "deleted" in m.content.lower())
        and "tracked files" in m.content.lower()
    ]


def _build_agent(model, tmp_path: Path) -> Sosa:
    """Build a minimal Sosa agent backed by a fake model and tmp dirs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    soul_path = tmp_path / "soul"
    soul_path.mkdir(exist_ok=True)
    return Sosa(
        model=model,
        prompt="test",
        workspace_path=workspace,
        soul_memory_path=soul_path,
        include_basic_tools=True,
        name="TestAgent",
    )


async def _run_turn(agent: Sosa, messages: list) -> list:
    """Run one agent turn and collect all yielded messages."""
    yielded = []
    async for msg in agent.run(messages):
        yielded.append(msg)
        messages.append(msg)
    return yielded


# ---------------------------------------------------------------------------
# Fake model that drives a scripted two-turn sequence
# ---------------------------------------------------------------------------


class ScriptedModel:
    """Fake BaseChatModel that replays a list of canned AIMessage responses.

    On each invoke() call it pops the next response from the queue.
    Also supports bind_tools() so Sosa can call model.bind_tools(tools).
    """

    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)
        self._index = 0

    def bind_tools(self, tools, **kwargs):
        """Return self — tools are already known; we ignore them in tests."""
        return self

    def invoke(self, messages, **kwargs) -> AIMessage:
        if self._index >= len(self._responses):
            return _noop_ai_message()
        resp = self._responses[self._index]
        self._index += 1
        return resp

    # LangChain sometimes checks model_name — provide a stub
    @property
    def model_name(self) -> str:
        return "fake-model"


# ---------------------------------------------------------------------------
# AC1: Changed file → staleness notification on turn 2
# ---------------------------------------------------------------------------


class TestChangedFileCrossTurn:
    def test_changed_file_reported_on_next_turn(self, tmp_path: Path) -> None:
        """Read a file in turn 1; edit it externally; turn 2 reports it changed."""
        target = tmp_path / "workspace" / "notes.txt"
        (tmp_path / "workspace").mkdir(exist_ok=True)
        target.write_text("original content")

        call_id = "read-call-1"
        model = ScriptedModel([
            # Turn 1, step 1: model asks to read the file
            _make_tool_call_message("read_file", {"file_path": str(target)}, call_id),
            # Turn 1, step 2: after tool result, model ends the turn
            _noop_ai_message(),
            # Turn 2: model ends immediately (no tool calls)
            _noop_ai_message(),
        ])

        agent = _build_agent(model, tmp_path)

        messages: list = [HumanMessage(content="Please read notes.txt")]
        asyncio.run(_run_turn(agent, messages))

        # External edit between turns
        target.write_text("modified content — different now")

        messages.append(HumanMessage(content="What changed?"))
        turn2_msgs = asyncio.run(_run_turn(agent, messages))

        staleness_msgs = _collect_staleness_messages(turn2_msgs)
        assert staleness_msgs, (
            "Expected a staleness SystemMessage on turn 2 after externally editing the file. "
            f"Turn 2 messages: {turn2_msgs}"
        )
        combined = " ".join(m.content for m in staleness_msgs)
        assert str(target) in combined or target.name in combined, (
            f"Staleness message should name '{target}', got: {combined}"
        )
        assert "changed" in combined.lower()

    def test_changed_file_not_re_reported_on_third_turn(self, tmp_path: Path) -> None:
        """After staleness is reported and baseline refreshed, turn 3 stays silent."""
        target = tmp_path / "workspace" / "doc.txt"
        (tmp_path / "workspace").mkdir(exist_ok=True)
        target.write_text("version 1")

        call_id = "read-call-3"
        model = ScriptedModel([
            _make_tool_call_message("read_file", {"file_path": str(target)}, call_id),
            _noop_ai_message(),  # end turn 1 after tool
            _noop_ai_message(),  # end turn 2
            _noop_ai_message(),  # end turn 3
        ])

        agent = _build_agent(model, tmp_path)

        messages: list = [HumanMessage(content="Read doc.txt")]
        asyncio.run(_run_turn(agent, messages))

        # Edit before turn 2
        target.write_text("version 2")
        messages.append(HumanMessage(content="Anything changed?"))
        turn2_msgs = asyncio.run(_run_turn(agent, messages))

        # Turn 2 should report the change
        staleness_t2 = _collect_staleness_messages(turn2_msgs)
        assert staleness_t2, "Expected staleness message on turn 2"

        # Turn 3: file is NOT edited again — baseline was refreshed to v2
        messages.append(HumanMessage(content="Check again"))
        turn3_msgs = asyncio.run(_run_turn(agent, messages))

        staleness_t3 = _collect_staleness_messages(turn3_msgs)
        assert not staleness_t3, (
            f"Expected no staleness message on turn 3 (no change since last report), "
            f"got: {staleness_t3}"
        )


# ---------------------------------------------------------------------------
# AC2: Deleted file → staleness notification on turn 2
# ---------------------------------------------------------------------------


class TestDeletedFileCrossTurn:
    def test_deleted_file_reported_on_next_turn(self, tmp_path: Path) -> None:
        """Read a file in turn 1; delete it externally; turn 2 reports it deleted."""
        target = tmp_path / "workspace" / "temp.txt"
        (tmp_path / "workspace").mkdir(exist_ok=True)
        target.write_text("some data")

        call_id = "del-call-1"
        model = ScriptedModel([
            _make_tool_call_message("read_file", {"file_path": str(target)}, call_id),
            _noop_ai_message(),
            _noop_ai_message(),
        ])

        agent = _build_agent(model, tmp_path)

        messages: list = [HumanMessage(content="Read temp.txt")]
        asyncio.run(_run_turn(agent, messages))

        # Delete the file between turns
        target.unlink()

        messages.append(HumanMessage(content="What happened?"))
        turn2_msgs = asyncio.run(_run_turn(agent, messages))

        staleness_msgs = _collect_staleness_messages(turn2_msgs)
        assert staleness_msgs, (
            "Expected a staleness SystemMessage on turn 2 after deleting the tracked file. "
            f"Turn 2 messages: {turn2_msgs}"
        )
        combined = " ".join(m.content for m in staleness_msgs)
        assert "deleted" in combined.lower()


# ---------------------------------------------------------------------------
# AC3: Unchanged file → no notification
# ---------------------------------------------------------------------------


class TestUnchangedFileCrossTurn:
    def test_unchanged_file_no_notification(self, tmp_path: Path) -> None:
        """Read a file in turn 1; leave it alone; turn 2 stays silent."""
        target = tmp_path / "workspace" / "stable.txt"
        (tmp_path / "workspace").mkdir(exist_ok=True)
        target.write_text("rock solid content")

        call_id = "unchanged-call-1"
        model = ScriptedModel([
            _make_tool_call_message("read_file", {"file_path": str(target)}, call_id),
            _noop_ai_message(),
            _noop_ai_message(),
        ])

        agent = _build_agent(model, tmp_path)

        messages: list = [HumanMessage(content="Read stable.txt")]
        asyncio.run(_run_turn(agent, messages))

        # No edit between turns
        messages.append(HumanMessage(content="Anything?"))
        turn2_msgs = asyncio.run(_run_turn(agent, messages))

        staleness_msgs = _collect_staleness_messages(turn2_msgs)
        assert not staleness_msgs, (
            f"Expected no staleness message for unchanged file, got: {staleness_msgs}"
        )


# ---------------------------------------------------------------------------
# AC4: New session starts with empty hash store
# ---------------------------------------------------------------------------


class TestNewSessionEmpty:
    def test_new_instance_has_empty_file_hashes(self, tmp_path: Path) -> None:
        """A freshly-constructed Sosa instance must have no tracked files."""
        model = ScriptedModel([_noop_ai_message()])
        agent = _build_agent(model, tmp_path)
        assert agent._file_hashes == {}, (
            "New Sosa instance must start with empty file_hashes"
        )

    def test_different_instances_dont_share_hashes(self, tmp_path: Path) -> None:
        """Two separate Sosa instances have independent hash stores."""
        target = tmp_path / "workspace" / "shared.txt"
        (tmp_path / "workspace").mkdir(exist_ok=True)
        target.write_text("content")

        call_id = "share-call-1"
        model1 = ScriptedModel([
            _make_tool_call_message("read_file", {"file_path": str(target)}, call_id),
            _noop_ai_message(),
        ])
        model2 = ScriptedModel([_noop_ai_message()])

        tmp2 = tmp_path / "session2"
        tmp2.mkdir()

        agent1 = _build_agent(model1, tmp_path)
        agent2 = _build_agent(model2, tmp2)

        messages1: list = [HumanMessage(content="Read shared.txt")]
        asyncio.run(_run_turn(agent1, messages1))

        # Agent1 should have recorded the hash; agent2 should still be empty
        assert str(target) in agent1._file_hashes, "Agent1 should have hash after reading"
        assert agent2._file_hashes == {}, "Agent2 should not share hashes with agent1"
