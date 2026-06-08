"""Tests for auto-read project docs (issue #10).

Covers all acceptance criteria:
- AC1: With both AGENTS.md and CLAUDE.md in a scope dir, only AGENTS.md is injected.
- AC2: With only CLAUDE.md present, CLAUDE.md content is injected.
- AC3: Absent doc at a scope → no system message for that slot, no file created.
- AC4: Both scopes resolve independently: workspace doc + global doc both inject when both exist.
- AC5: Context.to_messages() order: system → soul → global_doc → workspace_doc → (MCP) → messages.
- AC6: Docs are read fresh each turn (re-resolving from disk).
- AC7: Prompt.md describes the autoread behavior (checked separately — presence of key terms).
"""

from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from sosa.graph.nodes.project_docs import resolve_project_doc


# ---------------------------------------------------------------------------
# Unit tests: resolve_project_doc helper
# ---------------------------------------------------------------------------


class TestResolveProjectDoc:
    def test_agents_md_preferred_over_claude_md(self, tmp_path: Path) -> None:
        """When both AGENTS.md and CLAUDE.md exist, AGENTS.md wins."""
        (tmp_path / "AGENTS.md").write_text("agents content")
        (tmp_path / "CLAUDE.md").write_text("claude content")
        result = resolve_project_doc(tmp_path)
        assert result is not None
        assert result.name == "AGENTS.md"

    def test_claude_md_fallback_when_only_claude(self, tmp_path: Path) -> None:
        """When only CLAUDE.md is present, it is returned."""
        (tmp_path / "CLAUDE.md").write_text("claude content")
        result = resolve_project_doc(tmp_path)
        assert result is not None
        assert result.name == "CLAUDE.md"

    def test_agents_md_only(self, tmp_path: Path) -> None:
        """When only AGENTS.md is present, it is returned."""
        (tmp_path / "AGENTS.md").write_text("agents content")
        result = resolve_project_doc(tmp_path)
        assert result is not None
        assert result.name == "AGENTS.md"

    def test_neither_returns_none(self, tmp_path: Path) -> None:
        """When neither doc exists, None is returned."""
        result = resolve_project_doc(tmp_path)
        assert result is None

    def test_no_file_created_when_absent(self, tmp_path: Path) -> None:
        """resolve_project_doc must never create files."""
        resolve_project_doc(tmp_path)
        assert not (tmp_path / "AGENTS.md").exists()
        assert not (tmp_path / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Integration tests: init node populates project docs in state
# ---------------------------------------------------------------------------


def _make_init_state(soul_memory_path: Path, workspace_path: Path) -> dict:
    """Minimal state dict for the init node."""
    return {
        "soul_memory_path": soul_memory_path,
        "workspace_path": workspace_path,
    }


class TestInitNodeProjectDocs:
    def test_global_doc_read_when_present(self, tmp_path: Path) -> None:
        """init node sets global_project_doc when AGENTS.md or CLAUDE.md is in soul_memory_path."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (soul_path / "AGENTS.md").write_text("# Global agents doc")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "global_project_doc" in result
        assert result["global_project_doc"] is not None
        assert "Global agents doc" in result["global_project_doc"]

    def test_workspace_doc_read_when_present(self, tmp_path: Path) -> None:
        """init node sets workspace_project_doc when a project doc is in workspace_path."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (workspace / "CLAUDE.md").write_text("# Workspace claude doc")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "workspace_project_doc" in result
        assert result["workspace_project_doc"] is not None
        assert "Workspace claude doc" in result["workspace_project_doc"]

    def test_absent_global_doc_sets_none(self, tmp_path: Path) -> None:
        """init node sets global_project_doc=None when no doc exists in soul_memory_path."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result.get("global_project_doc") is None

    def test_absent_workspace_doc_sets_none(self, tmp_path: Path) -> None:
        """init node sets workspace_project_doc=None when no doc exists in workspace_path."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result.get("workspace_project_doc") is None

    def test_agents_md_preferred_in_global_scope(self, tmp_path: Path) -> None:
        """When both docs exist in soul_memory_path, only AGENTS.md is injected."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (soul_path / "AGENTS.md").write_text("agents global")
        (soul_path / "CLAUDE.md").write_text("claude global")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result["global_project_doc"] is not None
        assert "agents global" in result["global_project_doc"]
        assert "claude global" not in result["global_project_doc"]

    def test_agents_md_preferred_in_workspace_scope(self, tmp_path: Path) -> None:
        """When both docs exist in workspace_path, only AGENTS.md is injected."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (workspace / "AGENTS.md").write_text("agents workspace")
        (workspace / "CLAUDE.md").write_text("claude workspace")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result["workspace_project_doc"] is not None
        assert "agents workspace" in result["workspace_project_doc"]
        assert "claude workspace" not in result["workspace_project_doc"]

    def test_both_scopes_independent(self, tmp_path: Path) -> None:
        """Both scopes resolve independently: both inject when both have docs."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (soul_path / "AGENTS.md").write_text("global doc content")
        (workspace / "CLAUDE.md").write_text("workspace doc content")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result["global_project_doc"] is not None
        assert "global doc content" in result["global_project_doc"]
        assert result["workspace_project_doc"] is not None
        assert "workspace doc content" in result["workspace_project_doc"]

    def test_no_file_created_when_absent(self, tmp_path: Path) -> None:
        """init node must not create any project doc files."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (soul_path / "AGENTS.md").exists()
        assert not (soul_path / "CLAUDE.md").exists()
        assert not (workspace / "AGENTS.md").exists()
        assert not (workspace / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Init memory file behavior (issue #12 / issue #16)
# ---------------------------------------------------------------------------


class TestInitMemoryFiles:
    def test_universal_memory_not_created_on_fresh_soul_path(self, tmp_path: Path) -> None:
        """init must NOT create soul_memory_path/memory.md (retired in issue #16)."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (soul_path / "memory.md").exists(), (
            "init must not create memory.md — that file is retired (issue #16)"
        )

    def test_universal_memory_not_overwritten_when_present(self, tmp_path: Path) -> None:
        """init does not overwrite <soul_memory_path>/memory.md when it already exists."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (soul_path / "memory.md").write_text("# Existing Universal Memory\nexisting content\n")

        state = _make_init_state(soul_path, workspace)
        init(state)

        content = (soul_path / "memory.md").read_text()
        assert "existing content" in content

    def test_workspace_memory_not_created_on_fresh_workspace(self, tmp_path: Path) -> None:
        """init must NOT create <workspace_path>/memory.md (issue #12)."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (workspace / "memory.md").exists()

    def test_existing_workspace_memory_left_untouched(self, tmp_path: Path) -> None:
        """init must not delete or modify an existing <workspace_path>/memory.md."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        original = "# Workspace Memory\nsome project notes\n"
        (workspace / "memory.md").write_text(original)

        state = _make_init_state(soul_path, workspace)
        init(state)

        # File must still exist with original content
        assert (workspace / "memory.md").exists()
        assert (workspace / "memory.md").read_text() == original


# ---------------------------------------------------------------------------
# Context.to_messages() ordering and injection
# ---------------------------------------------------------------------------


def _make_context_state(
    soul_path: Path,
    workspace_path: Path,
    soul_content: str = "soul content",
    global_doc: str | None = None,
    workspace_doc: str | None = None,
    messages: list | None = None,
    has_mcp: bool = False,
) -> dict:
    """Build a minimal AgentState-like dict for Context tests."""
    from unittest.mock import MagicMock

    tools = []
    if has_mcp:
        mock_tool = MagicMock()
        mock_tool.name = "search_tools"
        tools = [mock_tool]

    return {
        "system_prompt": "system prompt content",
        "soul": soul_content,
        "soul_memory_path": soul_path,
        "workspace_path": workspace_path,
        "messages": messages or [],
        "tools": tools,
        "global_project_doc": global_doc,
        "workspace_project_doc": workspace_doc,
    }


class TestContextToMessagesOrder:
    def test_order_without_docs_without_mcp(self, tmp_path: Path) -> None:
        """system → soul → messages (no docs, no MCP)."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hello")
        state = _make_context_state(soul_path, workspace, messages=[human_msg])
        ctx = Context(state)
        msgs = ctx.to_messages()

        assert len(msgs) == 3
        assert isinstance(msgs[0], SystemMessage)
        assert "system prompt content" in msgs[0].content
        assert isinstance(msgs[1], SystemMessage)
        assert "soul content" in msgs[1].content
        assert msgs[2] is human_msg

    def test_order_with_global_doc_only(self, tmp_path: Path) -> None:
        """system → soul → global_doc → messages."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            global_doc="global doc text",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        assert len(msgs) == 4
        assert isinstance(msgs[0], SystemMessage)  # system
        assert isinstance(msgs[1], SystemMessage)  # soul
        assert isinstance(msgs[2], SystemMessage)  # global doc
        assert "global doc text" in msgs[2].content
        assert msgs[3] is human_msg

    def test_order_with_workspace_doc_only(self, tmp_path: Path) -> None:
        """system → soul → workspace_doc → messages."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            workspace_doc="workspace doc text",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        assert len(msgs) == 4
        assert isinstance(msgs[0], SystemMessage)  # system
        assert isinstance(msgs[1], SystemMessage)  # soul
        assert isinstance(msgs[2], SystemMessage)  # workspace doc
        assert "workspace doc text" in msgs[2].content
        assert msgs[3] is human_msg

    def test_order_with_both_docs(self, tmp_path: Path) -> None:
        """system → soul → global_doc → workspace_doc → messages."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            global_doc="global text",
            workspace_doc="workspace text",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        assert len(msgs) == 5
        assert isinstance(msgs[0], SystemMessage)  # system
        assert isinstance(msgs[1], SystemMessage)  # soul
        assert isinstance(msgs[2], SystemMessage)  # global doc
        assert "global text" in msgs[2].content
        assert isinstance(msgs[3], SystemMessage)  # workspace doc
        assert "workspace text" in msgs[3].content
        assert msgs[4] is human_msg

    def test_order_with_both_docs_and_mcp(self, tmp_path: Path) -> None:
        """system → soul → global_doc → workspace_doc → MCP addendum → messages."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            global_doc="global text",
            workspace_doc="workspace text",
            messages=[human_msg],
            has_mcp=True,
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        assert len(msgs) == 6
        assert isinstance(msgs[0], SystemMessage)  # system
        assert isinstance(msgs[1], SystemMessage)  # soul
        assert isinstance(msgs[2], SystemMessage)  # global doc
        assert "global text" in msgs[2].content
        assert isinstance(msgs[3], SystemMessage)  # workspace doc
        assert "workspace text" in msgs[3].content
        assert isinstance(msgs[4], SystemMessage)  # MCP addendum
        assert msgs[5] is human_msg

    def test_global_doc_absent_no_slot(self, tmp_path: Path) -> None:
        """When global_project_doc is None, no slot is emitted for it."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            global_doc=None,
            workspace_doc="workspace text",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # system + soul + workspace_doc + human = 4
        assert len(msgs) == 4
        assert "workspace text" in msgs[2].content

    def test_workspace_doc_absent_no_slot(self, tmp_path: Path) -> None:
        """When workspace_project_doc is None, no slot is emitted for it."""
        from langchain_core.messages import HumanMessage
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path, workspace,
            global_doc="global text",
            workspace_doc=None,
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # system + soul + global_doc + human = 4
        assert len(msgs) == 4
        assert "global text" in msgs[2].content


# ---------------------------------------------------------------------------
# Fresh read each turn
# ---------------------------------------------------------------------------


class TestFreshReadEachTurn:
    def test_doc_content_reflects_disk_change_next_turn(self, tmp_path: Path) -> None:
        """If the doc changes on disk between calls to init, the new content appears."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = soul_path / "AGENTS.md"
        doc.write_text("version 1")

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        assert result1["global_project_doc"] is not None
        assert "version 1" in result1["global_project_doc"]

        # Simulate doc changing between turns
        doc.write_text("version 2")

        result2 = init(state)
        assert result2["global_project_doc"] is not None
        assert "version 2" in result2["global_project_doc"]
        assert "version 1" not in result2["global_project_doc"]

    def test_doc_appearing_between_turns_is_picked_up(self, tmp_path: Path) -> None:
        """A doc that didn't exist on turn 1 appears on turn 2 if created in between."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        assert result1.get("global_project_doc") is None

        # Doc appears between turns
        (soul_path / "CLAUDE.md").write_text("late arrival")

        result2 = init(state)
        assert result2["global_project_doc"] is not None
        assert "late arrival" in result2["global_project_doc"]


# ---------------------------------------------------------------------------
# AgentState fields
# ---------------------------------------------------------------------------


class TestAgentStateFields:
    def test_global_project_doc_field_exists(self) -> None:
        """AgentState must declare global_project_doc field."""
        import typing
        from sosa.schemas.AgentState import AgentState

        hints = typing.get_type_hints(AgentState, include_extras=True)
        assert "global_project_doc" in hints, (
            "AgentState must have a global_project_doc field"
        )

    def test_workspace_project_doc_field_exists(self) -> None:
        """AgentState must declare workspace_project_doc field."""
        import typing
        from sosa.schemas.AgentState import AgentState

        hints = typing.get_type_hints(AgentState, include_extras=True)
        assert "workspace_project_doc" in hints, (
            "AgentState must have a workspace_project_doc field"
        )


# ---------------------------------------------------------------------------
# Prompt.md describes the autoread behavior
# ---------------------------------------------------------------------------


class TestPromptMdDescribesAutoread:
    def _read_prompt(self) -> str:
        prompt_path = (
            Path(__file__).parent.parent / "sosa" / "prompts" / "Prompt.md"
        )
        return prompt_path.read_text()

    def test_agents_md_mentioned(self) -> None:
        assert "AGENTS.md" in self._read_prompt()

    def test_claude_md_mentioned(self) -> None:
        assert "CLAUDE.md" in self._read_prompt()

    def test_precedence_described(self) -> None:
        content = self._read_prompt()
        # Should mention that AGENTS.md takes precedence over CLAUDE.md
        assert "AGENTS.md" in content and "CLAUDE.md" in content
        # Check that precedence/fallback language is present
        assert any(word in content.lower() for word in ("prefer", "precedence", "fall back", "fallback", "first"))

    def test_both_scopes_described(self) -> None:
        content = self._read_prompt()
        # Should mention both workspace and global/soul scopes
        assert any(w in content for w in ("soul_memory_path", "workspace_path", "global", "workspace"))

    def test_autoread_described(self) -> None:
        content = self._read_prompt()
        # Should describe the autoread (injected/auto-read/loaded) behavior
        assert any(w in content.lower() for w in ("auto", "inject", "preload", "loaded", "each turn"))


# ---------------------------------------------------------------------------
# Issue #11: hash-track project docs in file_hashes (AC1–AC4)
# ---------------------------------------------------------------------------


class TestInitNodeRegistersProjectDocHashes:
    """init node must populate file_hashes for each resolved project doc.

    AC1: After a turn, each resolved project-doc path is present in file_hashes
         with its current content hash.
    AC3: A project doc that does not exist is not registered (no phantom tracking).
    AC4: Hash registration works for both workspace and global resolved docs.
    """

    def test_global_doc_hash_registered(self, tmp_path: Path) -> None:
        """Global project doc path → hash must appear in init return value."""
        from sosa.graph.nodes.init import init
        from sosa.tools.hashing import hash_file

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = soul_path / "AGENTS.md"
        doc.write_text("# Global AGENTS doc")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "file_hashes" in result, "init must return file_hashes when project docs exist"
        assert str(doc) in result["file_hashes"], (
            f"global doc path '{doc}' must be in file_hashes"
        )
        assert result["file_hashes"][str(doc)] == hash_file(doc)

    def test_workspace_doc_hash_registered(self, tmp_path: Path) -> None:
        """Workspace project doc path → hash must appear in init return value."""
        from sosa.graph.nodes.init import init
        from sosa.tools.hashing import hash_file

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = workspace / "CLAUDE.md"
        doc.write_text("# Workspace CLAUDE doc")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "file_hashes" in result, "init must return file_hashes when project docs exist"
        assert str(doc) in result["file_hashes"], (
            f"workspace doc path '{doc}' must be in file_hashes"
        )
        assert result["file_hashes"][str(doc)] == hash_file(doc)

    def test_both_docs_registered(self, tmp_path: Path) -> None:
        """Both global and workspace docs must be registered when both exist."""
        from sosa.graph.nodes.init import init
        from sosa.tools.hashing import hash_file

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        global_doc = soul_path / "AGENTS.md"
        global_doc.write_text("# Global AGENTS")
        workspace_doc = workspace / "AGENTS.md"
        workspace_doc.write_text("# Workspace AGENTS")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "file_hashes" in result
        assert str(global_doc) in result["file_hashes"]
        assert str(workspace_doc) in result["file_hashes"]
        assert result["file_hashes"][str(global_doc)] == hash_file(global_doc)
        assert result["file_hashes"][str(workspace_doc)] == hash_file(workspace_doc)

    def test_absent_global_doc_not_registered(self, tmp_path: Path) -> None:
        """When global doc does not exist, no phantom hash is registered for it."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # No doc in soul_path
        workspace_doc = workspace / "CLAUDE.md"
        workspace_doc.write_text("workspace only")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        file_hashes = result.get("file_hashes", {})
        for key in file_hashes:
            assert not key.startswith(str(soul_path)), (
                f"Phantom hash registered for absent global doc: {key}"
            )

    def test_absent_workspace_doc_not_registered(self, tmp_path: Path) -> None:
        """When workspace doc does not exist, no phantom hash is registered for it."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # No doc in workspace
        global_doc = soul_path / "AGENTS.md"
        global_doc.write_text("global only")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        file_hashes = result.get("file_hashes", {})
        for key in file_hashes:
            assert not key.startswith(str(workspace)), (
                f"Phantom hash registered for absent workspace doc: {key}"
            )

    def test_no_docs_no_file_hashes_entry(self, tmp_path: Path) -> None:
        """When neither scope has a doc, file_hashes need not be set (or may be empty)."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        file_hashes = result.get("file_hashes", {})
        assert file_hashes == {}, (
            "file_hashes must be empty (or absent) when no project docs exist"
        )


# ---------------------------------------------------------------------------
# Issue #11: AC2 — staleness notice emitted when project doc changes externally
# ---------------------------------------------------------------------------


class TestProjectDocStalenessNotice:
    """Editing a tracked project doc externally drives staleness node to emit a notice.

    This test drives the real init → staleness pipeline (without a live model)
    to verify that the hash registered by init feeds into staleness on the next call.
    """

    def test_changed_global_doc_triggers_staleness(self, tmp_path: Path) -> None:
        """Editing the global project doc between turns produces a staleness SystemMessage."""
        from sosa.graph.nodes.init import init
        from sosa.graph.nodes.staleness import staleness
        from sosa.schemas.AgentState import merge_file_hashes

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = soul_path / "AGENTS.md"
        doc.write_text("version 1")

        # Turn 1: init registers the hash
        state = _make_init_state(soul_path, workspace)
        init_result = init(state)
        file_hashes = merge_file_hashes({}, init_result.get("file_hashes", {}))

        # External edit between turns
        doc.write_text("version 2 — externally changed")

        # Turn 2 staleness check
        staleness_state = {"file_hashes": file_hashes, "messages": []}
        staleness_result = staleness(staleness_state)

        sys_msgs = [
            m for m in staleness_result.get("messages", [])
            if hasattr(m, "content")
            and "changed" in m.content.lower()
        ]
        assert sys_msgs, (
            "Expected a staleness SystemMessage after externally editing the global project doc. "
            f"staleness_result: {staleness_result}"
        )
        combined = " ".join(m.content for m in sys_msgs)
        assert doc.name in combined or str(doc) in combined, (
            f"Staleness message should name the changed doc. Got: {combined}"
        )

    def test_changed_workspace_doc_triggers_staleness(self, tmp_path: Path) -> None:
        """Editing the workspace project doc between turns produces a staleness SystemMessage."""
        from sosa.graph.nodes.init import init
        from sosa.graph.nodes.staleness import staleness
        from sosa.schemas.AgentState import merge_file_hashes

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = workspace / "CLAUDE.md"
        doc.write_text("workspace v1")

        state = _make_init_state(soul_path, workspace)
        init_result = init(state)
        file_hashes = merge_file_hashes({}, init_result.get("file_hashes", {}))

        # External edit
        doc.write_text("workspace v2 — changed externally")

        staleness_state = {"file_hashes": file_hashes, "messages": []}
        staleness_result = staleness(staleness_state)

        sys_msgs = [
            m for m in staleness_result.get("messages", [])
            if hasattr(m, "content")
            and "changed" in m.content.lower()
        ]
        assert sys_msgs, (
            "Expected a staleness SystemMessage after externally editing the workspace project doc."
        )
        combined = " ".join(m.content for m in sys_msgs)
        assert doc.name in combined or str(doc) in combined

    def test_unchanged_project_doc_no_staleness(self, tmp_path: Path) -> None:
        """If the project doc is not changed between turns, no staleness notice is emitted."""
        from sosa.graph.nodes.init import init
        from sosa.graph.nodes.staleness import staleness
        from sosa.schemas.AgentState import merge_file_hashes

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        doc = soul_path / "AGENTS.md"
        doc.write_text("stable content")

        state = _make_init_state(soul_path, workspace)
        init_result = init(state)
        file_hashes = merge_file_hashes({}, init_result.get("file_hashes", {}))

        # No edit — call staleness directly
        staleness_state = {"file_hashes": file_hashes, "messages": []}
        staleness_result = staleness(staleness_state)

        sys_msgs = staleness_result.get("messages", [])
        assert not sys_msgs, (
            f"Expected no staleness message for unchanged project doc. Got: {sys_msgs}"
        )
