"""Tests for the core memory pipe (issue #16).

Covers all acceptance criteria:
- AC1: init() with a temp soul_memory_path whose memory/ holds well-formed fixture files
        produces a MEMORY.md with correct ## sections grouped by type and correct
        - [name](memory/name.md) — <description> links.
- AC2: Context.to_messages() injects the MEMORY.md index content when present, and omits
        the slot when no memory files / no index exist.
- AC3: No memory.md file is created by init under any path.
- Ordering: suggested types appear first; arbitrary types after; alphabetical within group.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from sosa.graph.nodes.memory_index import build_memory_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_memory_file(directory: Path, stem: str, type_: str, description: str, body: str = "") -> Path:
    """Write a memory/<stem>.md file with YAML frontmatter."""
    memory_dir = directory / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\ndescription: {description}\ntype: {type_}\n---\n{body}"
    path = memory_dir / f"{stem}.md"
    path.write_text(content)
    return path


def _make_init_state(soul_memory_path: Path, workspace_path: Path) -> dict:
    """Minimal state dict for the init node."""
    return {
        "soul_memory_path": soul_memory_path,
        "workspace_path": workspace_path,
    }


def _make_context_state(
    soul_path: Path,
    workspace_path: Path,
    soul_content: str = "soul content",
    memory_index: str | None = None,
    global_doc: str | None = None,
    workspace_doc: str | None = None,
    messages: list | None = None,
    has_mcp: bool = False,
) -> dict:
    """Build a minimal AgentState-like dict for Context tests."""
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
        "memory_index": memory_index,
    }


# ---------------------------------------------------------------------------
# Unit tests: build_memory_index helper
# ---------------------------------------------------------------------------


class TestBuildMemoryIndex:
    def test_single_file_produces_correct_section_and_link(self, tmp_path: Path) -> None:
        """One memory file → one ## section, one link."""
        _write_memory_file(tmp_path, "alice", "user", "Alice is the main user")

        result = build_memory_index(tmp_path)

        assert result is not None
        assert "# Memory" in result
        assert "## user" in result
        assert "- [alice](memory/alice.md) — Alice is the main user" in result

    def test_multiple_files_same_type_grouped(self, tmp_path: Path) -> None:
        """Two files of the same type appear under a single ## section."""
        _write_memory_file(tmp_path, "alice", "user", "Alice is the main user")
        _write_memory_file(tmp_path, "bob", "user", "Bob is a colleague")

        result = build_memory_index(tmp_path)

        assert result is not None
        assert result.count("## user") == 1
        assert "- [alice](memory/alice.md) — Alice is the main user" in result
        assert "- [bob](memory/bob.md) — Bob is a colleague" in result

    def test_multiple_types_get_separate_sections(self, tmp_path: Path) -> None:
        """Files of different types produce separate ## sections."""
        _write_memory_file(tmp_path, "alice", "user", "Alice is the user")
        _write_memory_file(tmp_path, "myproject", "project", "Main project")

        result = build_memory_index(tmp_path)

        assert result is not None
        assert "## user" in result
        assert "## project" in result

    def test_suggested_types_ordered_first(self, tmp_path: Path) -> None:
        """user/feedback/project/reference appear before arbitrary types."""
        _write_memory_file(tmp_path, "z_custom", "zzz_custom", "Custom entry")
        _write_memory_file(tmp_path, "proj", "project", "A project")
        _write_memory_file(tmp_path, "usr", "user", "A user")

        result = build_memory_index(tmp_path)

        assert result is not None
        user_pos = result.index("## user")
        project_pos = result.index("## project")
        custom_pos = result.index("## zzz_custom")

        assert user_pos < custom_pos, "suggested type 'user' must come before arbitrary type"
        assert project_pos < custom_pos, "suggested type 'project' must come before arbitrary type"

    def test_no_memory_dir_returns_none(self, tmp_path: Path) -> None:
        """When memory/ does not exist, returns None (no MEMORY.md written)."""
        result = build_memory_index(tmp_path)
        assert result is None

    def test_empty_memory_dir_returns_none(self, tmp_path: Path) -> None:
        """When memory/ is empty (no .md files), returns None."""
        (tmp_path / "memory").mkdir()
        result = build_memory_index(tmp_path)
        assert result is None

    def test_memory_md_written_to_soul_memory_path(self, tmp_path: Path) -> None:
        """build_memory_index writes MEMORY.md at soul_memory_path/MEMORY.md."""
        _write_memory_file(tmp_path, "fact", "reference", "An interesting fact")

        build_memory_index(tmp_path)

        assert (tmp_path / "MEMORY.md").exists()
        content = (tmp_path / "MEMORY.md").read_text()
        assert "# Memory" in content

    def test_memory_md_content_matches_return_value(self, tmp_path: Path) -> None:
        """The written MEMORY.md content matches what build_memory_index returns."""
        _write_memory_file(tmp_path, "fact", "reference", "A fact")

        result = build_memory_index(tmp_path)
        written = (tmp_path / "MEMORY.md").read_text()

        assert result == written

    def test_no_memory_dir_no_memory_md_written(self, tmp_path: Path) -> None:
        """When memory/ is absent, no MEMORY.md is written."""
        build_memory_index(tmp_path)
        assert not (tmp_path / "MEMORY.md").exists()

    def test_title_is_hash_memory(self, tmp_path: Path) -> None:
        """Index starts with '# Memory'."""
        _write_memory_file(tmp_path, "item", "user", "A user")
        result = build_memory_index(tmp_path)
        assert result is not None
        assert result.startswith("# Memory")

    def test_links_use_stem_not_filename(self, tmp_path: Path) -> None:
        """Link text is the filename stem (no .md extension)."""
        _write_memory_file(tmp_path, "my_note", "reference", "My note")
        result = build_memory_index(tmp_path)
        assert result is not None
        assert "[my_note]" in result
        # Ensure .md extension is not used as link text
        assert "[my_note.md]" not in result

    def test_all_suggested_types_in_order(self, tmp_path: Path) -> None:
        """user, feedback, project, reference appear in that order when all present."""
        _write_memory_file(tmp_path, "ref", "reference", "A ref")
        _write_memory_file(tmp_path, "fb", "feedback", "Some feedback")
        _write_memory_file(tmp_path, "usr", "user", "A user")
        _write_memory_file(tmp_path, "proj", "project", "A project")

        result = build_memory_index(tmp_path)
        assert result is not None

        user_pos = result.index("## user")
        feedback_pos = result.index("## feedback")
        project_pos = result.index("## project")
        reference_pos = result.index("## reference")

        assert user_pos < feedback_pos < project_pos < reference_pos


# ---------------------------------------------------------------------------
# Integration tests: init node builds memory index
# ---------------------------------------------------------------------------


class TestInitNodeMemoryIndex:
    def test_init_returns_memory_index_when_memory_files_exist(self, tmp_path: Path) -> None:
        """init sets memory_index in its return dict when memory/ has files."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "alice", "user", "Alice is the user")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert "memory_index" in result
        assert result["memory_index"] is not None
        assert "alice" in result["memory_index"]

    def test_init_returns_none_memory_index_when_no_memory_dir(self, tmp_path: Path) -> None:
        """init sets memory_index=None when memory/ does not exist."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        assert result.get("memory_index") is None

    def test_init_writes_memory_md_to_soul_memory_path(self, tmp_path: Path) -> None:
        """init writes MEMORY.md to soul_memory_path when memory files exist."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "fact", "reference", "A fact")

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert (soul_path / "MEMORY.md").exists()

    def test_init_regenerates_memory_md_every_turn(self, tmp_path: Path) -> None:
        """MEMORY.md is overwritten unconditionally each call to init."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "fact1", "reference", "First fact")

        state = _make_init_state(soul_path, workspace)
        init(state)

        content1 = (soul_path / "MEMORY.md").read_text()
        assert "fact1" in content1

        # Add a new file between turns
        _write_memory_file(soul_path, "fact2", "reference", "Second fact")
        init(state)  # called again (next turn)

        content2 = (soul_path / "MEMORY.md").read_text()
        assert "fact1" in content2
        assert "fact2" in content2

    def test_init_does_not_create_memory_md_lower_case(self, tmp_path: Path) -> None:
        """AC3: init never creates soul_memory_path/memory.md (lower-case)."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (soul_path / "memory.md").exists(), (
            "init must NOT create memory.md (lower-case) — that file is retired"
        )


# ---------------------------------------------------------------------------
# AC3: No memory.md created anywhere
# ---------------------------------------------------------------------------


class TestNoMemoryMdCreated:
    def test_no_memory_md_in_soul_path_fresh(self, tmp_path: Path) -> None:
        """On a fresh soul_memory_path, init must not create memory.md."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (soul_path / "memory.md").exists()

    def test_no_memory_md_in_workspace_fresh(self, tmp_path: Path) -> None:
        """On a fresh workspace_path, init must not create memory.md."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        state = _make_init_state(soul_path, workspace)
        init(state)

        assert not (workspace / "memory.md").exists()


# ---------------------------------------------------------------------------
# AC2: Context.to_messages() injection
# ---------------------------------------------------------------------------


class TestContextMemoryIndexInjection:
    def test_memory_index_injected_when_present(self, tmp_path: Path) -> None:
        """Context.to_messages() includes memory_index content when set."""
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hello")
        state = _make_context_state(
            soul_path,
            workspace,
            memory_index="# Memory\n\n## user\n- [alice](memory/alice.md) — Alice\n",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # Should include a SystemMessage containing the index
        sys_contents = [m.content for m in msgs if isinstance(m, SystemMessage)]
        combined = "\n".join(sys_contents)
        assert "# Memory" in combined
        assert "alice" in combined

    def test_memory_index_omitted_when_none(self, tmp_path: Path) -> None:
        """Context.to_messages() omits the memory_index slot when memory_index is None."""
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hello")
        state = _make_context_state(
            soul_path,
            workspace,
            memory_index=None,
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # system + soul + human = 3 (no memory slot)
        assert len(msgs) == 3

    def test_memory_index_position_after_soul_before_global_doc(self, tmp_path: Path) -> None:
        """Memory index appears right after soul.md, before global project doc."""
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hello")
        state = _make_context_state(
            soul_path,
            workspace,
            memory_index="# Memory\n\n## user\n- [u](memory/u.md) — U\n",
            global_doc="global doc text",
            workspace_doc="workspace doc text",
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # Expected order: system(0), soul(1), memory_index(2), global_doc(3), workspace_doc(4), human(5)
        assert len(msgs) == 6
        assert isinstance(msgs[0], SystemMessage)   # system
        assert isinstance(msgs[1], SystemMessage)   # soul
        assert isinstance(msgs[2], SystemMessage)   # memory index
        assert "# Memory" in msgs[2].content
        assert isinstance(msgs[3], SystemMessage)   # global doc
        assert "global doc text" in msgs[3].content
        assert isinstance(msgs[4], SystemMessage)   # workspace doc
        assert "workspace doc text" in msgs[4].content
        assert msgs[5] is human_msg

    def test_memory_index_present_no_docs_order(self, tmp_path: Path) -> None:
        """Memory index after soul when no project docs: system→soul→memory→messages."""
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path,
            workspace,
            memory_index="# Memory\n\n## reference\n- [r](memory/r.md) — R\n",
            global_doc=None,
            workspace_doc=None,
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # system + soul + memory + human = 4
        assert len(msgs) == 4
        assert "# Memory" in msgs[2].content
        assert msgs[3] is human_msg

    def test_memory_index_with_mcp_full_order(self, tmp_path: Path) -> None:
        """Full order: system→soul→memory→global→workspace→MCP→messages."""
        from sosa.schemas.Context import Context

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        human_msg = HumanMessage(content="hi")
        state = _make_context_state(
            soul_path,
            workspace,
            memory_index="# Memory\n\n## user\n- [u](memory/u.md) — U\n",
            global_doc="global text",
            workspace_doc="workspace text",
            has_mcp=True,
            messages=[human_msg],
        )
        ctx = Context(state)
        msgs = ctx.to_messages()

        # system(0), soul(1), memory(2), global(3), workspace(4), MCP(5), human(6)
        assert len(msgs) == 7
        assert "# Memory" in msgs[2].content
        assert "global text" in msgs[3].content
        assert "workspace text" in msgs[4].content
        # msgs[5] is MCP addendum
        assert msgs[6] is human_msg


# ---------------------------------------------------------------------------
# AgentState field
# ---------------------------------------------------------------------------


class TestAgentStateMemoryIndexField:
    def test_memory_index_field_exists(self) -> None:
        """AgentState must declare memory_index field."""
        import typing
        from sosa.schemas.AgentState import AgentState

        hints = typing.get_type_hints(AgentState, include_extras=True)
        assert "memory_index" in hints, "AgentState must have a memory_index field"


# ---------------------------------------------------------------------------
# Issue #17: Hash-gated index regen + memory files ride staleness
# ---------------------------------------------------------------------------


class TestHashGatedRegen:
    """MEMORY.md is only written when memory files changed/added/deleted."""

    def test_unchanged_memory_set_does_not_rewrite_memory_md(self, tmp_path: Path) -> None:
        """When no memory file has changed, init must NOT rewrite MEMORY.md."""
        from sosa.graph.nodes.init import init
        from sosa.tools.hashing import hash_file

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mem_path = _write_memory_file(soul_path, "alice", "user", "Alice")
        # First call: no hashes stored yet — regen expected
        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        memory_md = soul_path / "MEMORY.md"
        mtime1 = memory_md.stat().st_mtime_ns

        # Second call: pass the file_hashes returned by the first call — nothing changed
        stored_hashes = result1.get("file_hashes", {})
        state2 = {**_make_init_state(soul_path, workspace), "file_hashes": stored_hashes}
        init(state2)
        mtime2 = memory_md.stat().st_mtime_ns

        assert mtime1 == mtime2, (
            "MEMORY.md must not be rewritten when no memory file changed"
        )

    def test_new_memory_file_triggers_regen(self, tmp_path: Path) -> None:
        """Adding a new memory file triggers a MEMORY.md rebuild."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "alice", "user", "Alice")

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        memory_md = soul_path / "MEMORY.md"
        mtime1 = memory_md.stat().st_mtime_ns

        # Add new file, pass stale hashes (only alice recorded)
        _write_memory_file(soul_path, "bob", "user", "Bob")
        stored_hashes = result1.get("file_hashes", {})
        state2 = {**_make_init_state(soul_path, workspace), "file_hashes": stored_hashes}
        result2 = init(state2)
        mtime2 = memory_md.stat().st_mtime_ns

        assert mtime1 != mtime2, "MEMORY.md must be rewritten when a new memory file appears"
        assert result2.get("memory_index") is not None
        assert "bob" in result2["memory_index"]

    def test_changed_memory_file_triggers_regen(self, tmp_path: Path) -> None:
        """Editing a memory file triggers a MEMORY.md rebuild."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mem_path = _write_memory_file(soul_path, "alice", "user", "Alice original")

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        memory_md = soul_path / "MEMORY.md"
        mtime1 = memory_md.stat().st_mtime_ns

        # Modify the file, pass old hashes
        mem_path.write_text("---\ndescription: Alice changed\ntype: user\n---\n")
        stored_hashes = result1.get("file_hashes", {})
        state2 = {**_make_init_state(soul_path, workspace), "file_hashes": stored_hashes}
        init(state2)
        mtime2 = memory_md.stat().st_mtime_ns

        assert mtime1 != mtime2, "MEMORY.md must be rewritten when a memory file content changes"

    def test_deleted_memory_file_triggers_regen(self, tmp_path: Path) -> None:
        """Deleting a memory file triggers a MEMORY.md rebuild."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mem_path = _write_memory_file(soul_path, "alice", "user", "Alice")
        _write_memory_file(soul_path, "bob", "user", "Bob")

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)
        memory_md = soul_path / "MEMORY.md"
        mtime1 = memory_md.stat().st_mtime_ns

        # Delete one file, pass old hashes
        mem_path.unlink()
        stored_hashes = result1.get("file_hashes", {})
        state2 = {**_make_init_state(soul_path, workspace), "file_hashes": stored_hashes}
        result2 = init(state2)
        mtime2 = memory_md.stat().st_mtime_ns

        assert mtime1 != mtime2, "MEMORY.md must be rewritten when a memory file is deleted"


class TestInitRegistersMemoryFileHashes:
    """init() must register every memory file in file_hashes."""

    def test_init_returns_file_hashes_for_memory_files(self, tmp_path: Path) -> None:
        """init returns file_hashes containing each memory/*.md path."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        p1 = _write_memory_file(soul_path, "alice", "user", "Alice")
        p2 = _write_memory_file(soul_path, "bob", "user", "Bob")

        state = _make_init_state(soul_path, workspace)
        result = init(state)

        hashes = result.get("file_hashes", {})
        assert str(p1) in hashes, f"Expected {p1} in file_hashes"
        assert str(p2) in hashes, f"Expected {p2} in file_hashes"
        # Values must be non-empty SHA-256 hex strings
        assert len(hashes[str(p1)]) == 64
        assert len(hashes[str(p2)]) == 64

    def test_init_uses_remove_sentinel_for_deleted_memory_file(self, tmp_path: Path) -> None:
        """init returns REMOVE sentinel for a memory file that was deleted externally."""
        from sosa.graph.nodes.init import init
        from sosa.schemas.AgentState import REMOVE

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mem_path = _write_memory_file(soul_path, "alice", "user", "Alice")
        _write_memory_file(soul_path, "bob", "user", "Bob")

        state = _make_init_state(soul_path, workspace)
        result1 = init(state)

        # Delete alice, pass old hashes
        mem_path.unlink()
        stored_hashes = result1.get("file_hashes", {})
        state2 = {**_make_init_state(soul_path, workspace), "file_hashes": stored_hashes}
        result2 = init(state2)

        hashes2 = result2.get("file_hashes", {})
        assert hashes2.get(str(mem_path)) is REMOVE, (
            "Deleted memory file must have REMOVE sentinel in file_hashes update"
        )

    def test_refreshed_hashes_prevent_staleness_on_next_turn(self, tmp_path: Path) -> None:
        """After init regenerates, the returned hashes prevent the staleness node
        from re-flagging the just-written memory files on the same turn."""
        from sosa.graph.nodes.init import init
        from sosa.graph.nodes.staleness import staleness
        from sosa.schemas.AgentState import merge_file_hashes

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "alice", "user", "Alice")

        # Turn 1: init with no prior hashes
        state1 = _make_init_state(soul_path, workspace)
        result1 = init(state1)
        hashes_after_init = result1.get("file_hashes", {})

        # Simulate graph: merge the returned hashes into state, then run staleness
        merged = merge_file_hashes({}, hashes_after_init)
        staleness_state = {"file_hashes": merged, "messages": []}
        staleness_result = staleness(staleness_state)

        # No memory files should be flagged as changed — hashes were refreshed by init
        sys_msgs = [
            m for m in staleness_result.get("messages", [])
            if hasattr(m, "content") and "changed" in m.content.lower()
        ]
        assert not sys_msgs, (
            "Staleness node must not re-flag memory files written by init in the same turn. "
            f"Got messages: {sys_msgs}"
        )


class TestMemoryFilesRideStaleness:
    """Memory files registered in file_hashes are surfaced by the staleness node."""

    def test_externally_edited_memory_file_triggers_staleness(self, tmp_path: Path) -> None:
        """An external edit to a memory file is surfaced by the staleness node."""
        from sosa.graph.nodes.init import init
        from sosa.graph.nodes.staleness import staleness
        from sosa.schemas.AgentState import merge_file_hashes

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        mem_path = _write_memory_file(soul_path, "alice", "user", "Alice")

        # Turn 1: init registers memory file hash
        state1 = _make_init_state(soul_path, workspace)
        result1 = init(state1)
        hashes = merge_file_hashes({}, result1.get("file_hashes", {}))

        # External edit to memory file (between turns)
        mem_path.write_text("---\ndescription: Alice updated externally\ntype: user\n---\n")

        # Run staleness node with the stored hashes
        staleness_state = {"file_hashes": hashes, "messages": []}
        staleness_result = staleness(staleness_state)

        msgs = staleness_result.get("messages", [])
        assert msgs, "Staleness node must surface an externally-edited memory file"
        combined = " ".join(m.content for m in msgs if hasattr(m, "content"))
        assert str(mem_path) in combined or mem_path.name in combined, (
            f"Staleness message must name the changed memory file. Got: {combined}"
        )
        assert "changed" in combined.lower()


# ---------------------------------------------------------------------------
# Malformed frontmatter error handling (issue #18)
# ---------------------------------------------------------------------------


class TestMalformedFrontmatter:
    """build_memory_index raises MalformedMemoryFileError for broken files."""

    def test_missing_frontmatter_raises(self, tmp_path: Path) -> None:
        """A file with no --- block raises MalformedMemoryFileError naming the file."""
        from sosa.graph.nodes.memory_index import MalformedMemoryFileError

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        bad = memory_dir / "broken.md"
        bad.write_text("No frontmatter here, just plain text.\n")

        with pytest.raises(MalformedMemoryFileError) as exc_info:
            build_memory_index(tmp_path)

        assert "broken.md" in str(exc_info.value)

    def test_missing_description_raises(self, tmp_path: Path) -> None:
        """A file with frontmatter but no description field raises MalformedMemoryFileError."""
        from sosa.graph.nodes.memory_index import MalformedMemoryFileError

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        bad = memory_dir / "nodesc.md"
        bad.write_text("---\ntype: user\n---\nBody text.\n")

        with pytest.raises(MalformedMemoryFileError) as exc_info:
            build_memory_index(tmp_path)

        assert "nodesc.md" in str(exc_info.value)

    def test_missing_type_raises(self, tmp_path: Path) -> None:
        """A file with frontmatter but no type field raises MalformedMemoryFileError."""
        from sosa.graph.nodes.memory_index import MalformedMemoryFileError

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        bad = memory_dir / "notype.md"
        bad.write_text("---\ndescription: A note\n---\nBody text.\n")

        with pytest.raises(MalformedMemoryFileError) as exc_info:
            build_memory_index(tmp_path)

        assert "notype.md" in str(exc_info.value)

    def test_empty_frontmatter_raises(self, tmp_path: Path) -> None:
        """A file with an empty --- block raises MalformedMemoryFileError."""
        from sosa.graph.nodes.memory_index import MalformedMemoryFileError

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        bad = memory_dir / "empty_fm.md"
        bad.write_text("---\n---\nBody.\n")

        with pytest.raises(MalformedMemoryFileError) as exc_info:
            build_memory_index(tmp_path)

        assert "empty_fm.md" in str(exc_info.value)

    def test_well_formed_file_unaffected_by_bad_sibling(self, tmp_path: Path) -> None:
        """A bad file raises before the good file is silently dropped (fail loud)."""
        from sosa.graph.nodes.memory_index import MalformedMemoryFileError

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        # good file
        good = memory_dir / "alice.md"
        good.write_text("---\ndescription: Alice\ntype: user\n---\n")
        # bad file (comes first alphabetically)
        bad = memory_dir / "aaaa_bad.md"
        bad.write_text("no frontmatter\n")

        with pytest.raises(MalformedMemoryFileError) as exc_info:
            build_memory_index(tmp_path)

        assert "aaaa_bad.md" in str(exc_info.value)


class TestInitMalformedFrontmatter:
    """init node catches MalformedMemoryFileError and injects a recoverable SystemMessage."""

    def _make_state(self, soul_path: Path, workspace: Path) -> dict:
        return {
            "soul_memory_path": soul_path,
            "workspace_path": workspace,
        }

    def test_init_injects_system_message_on_bad_file(self, tmp_path: Path) -> None:
        """init returns a SystemMessage in messages when a memory file is malformed."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        memory_dir = soul_path / "memory"
        memory_dir.mkdir()
        bad = memory_dir / "broken.md"
        bad.write_text("no frontmatter here\n")

        state = self._make_state(soul_path, workspace)
        result = init(state)

        msgs = result.get("messages", [])
        if not isinstance(msgs, list):
            msgs = [msgs]
        sys_msgs = [m for m in msgs if isinstance(m, SystemMessage)]

        assert sys_msgs, "Expected a SystemMessage when a memory file is malformed"
        combined = " ".join(m.content for m in sys_msgs)
        assert "broken.md" in combined

    def test_init_does_not_crash_on_bad_file(self, tmp_path: Path) -> None:
        """init must not raise uncatchably when a memory file is malformed."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        memory_dir = soul_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "broken.md").write_text("no frontmatter here\n")

        state = self._make_state(soul_path, workspace)
        # Must not raise
        result = init(state)
        assert isinstance(result, dict)

    def test_init_names_file_in_error_message(self, tmp_path: Path) -> None:
        """The agent-visible error message names the offending file."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        memory_dir = soul_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "myfact.md").write_text("---\ntype: user\n---\n")  # missing description

        state = self._make_state(soul_path, workspace)
        result = init(state)

        msgs = result.get("messages", [])
        if not isinstance(msgs, list):
            msgs = [msgs]
        sys_msgs = [m for m in msgs if isinstance(m, SystemMessage)]
        combined = " ".join(m.content for m in sys_msgs)
        assert "myfact.md" in combined

    def test_good_files_build_index_when_no_bad_files(self, tmp_path: Path) -> None:
        """Well-formed files produce a correct index (unaffected by the error path)."""
        from sosa.graph.nodes.init import init

        soul_path = tmp_path / "soul"
        soul_path.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _write_memory_file(soul_path, "alice", "user", "Alice is the user")

        state = self._make_state(soul_path, workspace)
        result = init(state)

        assert result.get("memory_index") is not None
        assert "alice" in result["memory_index"]
        # No error message when files are well-formed
        msgs = result.get("messages", [])
        if not isinstance(msgs, list):
            msgs = [msgs]
        assert not msgs, "No messages expected when all memory files are well-formed"
