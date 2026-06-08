"""Integration tests for the staleness node (issue #5).

Covers:
- Changed file → system message injected naming it as changed, baseline refreshed
- Deleted file → system message injected naming it as deleted, key removed from file_hashes
- Unchanged file → no system message injected
- Multiple files changed → single summary message (not one per file)
- Only changed/deleted files mentioned → unchanged files absent from message
"""

from pathlib import Path

import pytest
from langchain_core.messages import SystemMessage

from sosa.graph.nodes.staleness import staleness
from sosa.tools.hashing import hash_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(file_hashes: dict, messages: list | None = None) -> dict:
    """Build a minimal hand-rolled AgentState-like dict for staleness tests."""
    return {
        "file_hashes": file_hashes,
        "messages": messages or [],
    }


def _system_messages(result: dict) -> list[SystemMessage]:
    msgs = result.get("messages", [])
    if not isinstance(msgs, list):
        msgs = [msgs]
    return [m for m in msgs if isinstance(m, SystemMessage)]


# ---------------------------------------------------------------------------
# Single changed file
# ---------------------------------------------------------------------------


class TestChangedFile:
    def test_changed_file_injects_system_message(self, tmp_path: Path) -> None:
        f = tmp_path / "tracked.txt"
        f.write_text("original")
        old_hash = hash_file(f)

        # Mutate file — simulate external change before next agent turn
        f.write_text("modified content")

        state = _make_state({str(f): old_hash})
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one SystemMessage for changed file"
        combined = " ".join(m.content for m in sys_msgs)
        assert str(f) in combined or f.name in combined
        assert "changed" in combined.lower()

    def test_changed_file_refreshes_baseline(self, tmp_path: Path) -> None:
        f = tmp_path / "tracked.txt"
        f.write_text("original")
        old_hash = hash_file(f)

        f.write_text("new content")
        new_hash = hash_file(f)

        state = _make_state({str(f): old_hash})
        result = staleness(state)

        updated = result.get("file_hashes", {})
        assert str(f) in updated
        assert updated[str(f)] == new_hash
        assert updated[str(f)] != old_hash

    def test_changed_file_not_re_reported_on_next_turn(self, tmp_path: Path) -> None:
        """After baseline is refreshed, second call should not report the file."""
        f = tmp_path / "stable.txt"
        f.write_text("original")
        old_hash = hash_file(f)

        f.write_text("changed once")

        state = _make_state({str(f): old_hash})
        result1 = staleness(state)
        # Extract the refreshed hash from the first call's update
        new_hashes = result1.get("file_hashes", {})
        # Simulate reducer applying the update: merge old + update
        from sosa.schemas.AgentState import merge_file_hashes
        merged = merge_file_hashes({str(f): old_hash}, new_hashes)

        # Second turn — file unchanged since last baseline
        state2 = _make_state(merged)
        result2 = staleness(state2)

        sys_msgs2 = _system_messages(result2)
        assert not sys_msgs2, "No message expected when file hasn't changed since last baseline"


# ---------------------------------------------------------------------------
# Deleted file
# ---------------------------------------------------------------------------


class TestDeletedFile:
    def test_deleted_file_injects_system_message(self, tmp_path: Path) -> None:
        f = tmp_path / "will_be_deleted.txt"
        f.write_text("some content")
        old_hash = hash_file(f)

        f.unlink()  # delete it

        state = _make_state({str(f): old_hash})
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one SystemMessage for deleted file"
        combined = " ".join(m.content for m in sys_msgs)
        assert str(f) in combined or f.name in combined
        assert "deleted" in combined.lower()

    def test_deleted_file_removed_from_baselines(self, tmp_path: Path) -> None:
        f = tmp_path / "gone.txt"
        f.write_text("data")
        old_hash = hash_file(f)
        f.unlink()

        state = _make_state({str(f): old_hash})
        result = staleness(state)

        from sosa.schemas.AgentState import merge_file_hashes, REMOVE
        updated = result.get("file_hashes", {})
        # Apply the reducer to confirm REMOVE sentinel drops the key
        merged = merge_file_hashes({str(f): old_hash}, updated)
        assert str(f) not in merged


# ---------------------------------------------------------------------------
# Unchanged file
# ---------------------------------------------------------------------------


class TestUnchangedFile:
    def test_unchanged_file_no_message(self, tmp_path: Path) -> None:
        f = tmp_path / "steady.txt"
        f.write_text("stable content")
        current_hash = hash_file(f)

        state = _make_state({str(f): current_hash})
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert not sys_msgs, "No SystemMessage expected when nothing changed"

    def test_unchanged_file_no_baseline_update(self, tmp_path: Path) -> None:
        f = tmp_path / "steady.txt"
        f.write_text("stable content")
        current_hash = hash_file(f)

        state = _make_state({str(f): current_hash})
        result = staleness(state)

        updated = result.get("file_hashes", {})
        # Should not re-write the hash for unchanged files
        assert str(f) not in updated

    def test_empty_file_hashes_no_message(self) -> None:
        state = _make_state({})
        result = staleness(state)
        sys_msgs = _system_messages(result)
        assert not sys_msgs


# ---------------------------------------------------------------------------
# Mixed: changed + deleted + unchanged
# ---------------------------------------------------------------------------


class TestMixedFiles:
    def test_only_changed_and_deleted_mentioned(self, tmp_path: Path) -> None:
        changed_f = tmp_path / "changed.txt"
        deleted_f = tmp_path / "deleted.txt"
        unchanged_f = tmp_path / "unchanged.txt"

        changed_f.write_text("v1")
        deleted_f.write_text("exists")
        unchanged_f.write_text("same")

        old_changed = hash_file(changed_f)
        old_deleted = hash_file(deleted_f)
        current_unchanged = hash_file(unchanged_f)

        # Simulate changes
        changed_f.write_text("v2")
        deleted_f.unlink()

        state = _make_state({
            str(changed_f): old_changed,
            str(deleted_f): old_deleted,
            str(unchanged_f): current_unchanged,
        })
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one message"
        combined = " ".join(m.content for m in sys_msgs)

        # changed and deleted paths are named
        assert changed_f.name in combined or str(changed_f) in combined
        assert deleted_f.name in combined or str(deleted_f) in combined
        # unchanged should not appear
        assert unchanged_f.name not in combined

    def test_multiple_changes_single_or_few_messages(self, tmp_path: Path) -> None:
        """Many changed files should produce a summarized single message, not one per file."""
        files = []
        hashes = {}
        for i in range(10):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(f"original {i}")
            hashes[str(f)] = hash_file(f)
            files.append(f)

        # Change all of them
        for f in files:
            f.write_text("modified")

        state = _make_state(hashes)
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one message"
        # Summarized — not 10 separate messages
        assert len(sys_msgs) == 1, f"Expected 1 summary message, got {len(sys_msgs)}"


# ---------------------------------------------------------------------------
# Summarization: large vs small change sets
# ---------------------------------------------------------------------------


class TestSummarization:
    """Tests for threshold-based summarization of large change sets."""

    def test_large_changeset_is_summarized(self, tmp_path: Path) -> None:
        """When affected paths exceed the threshold, message is bounded (not one line per file).

        Verifies:
        - The total count appears in the message.
        - Not every individual path is enumerated (bounded size).
        - The message line count does not grow one-per-file.
        """
        from sosa.graph.nodes.staleness import _SUMMARY_THRESHOLD

        n = _SUMMARY_THRESHOLD + 10  # well above threshold
        files = []
        hashes = {}
        for i in range(n):
            f = tmp_path / f"large_file_{i}.txt"
            f.write_text(f"original {i}")
            hashes[str(f)] = hash_file(f)
            files.append(f)

        # Change all of them
        for f in files:
            f.write_text("modified")

        state = _make_state(hashes)
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one SystemMessage"
        assert len(sys_msgs) == 1, "Expected a single summary message"

        content = sys_msgs[0].content

        # The total count must appear in the message
        assert str(n) in content, (
            f"Expected total count {n} to appear in summary message. Got:\n{content}"
        )

        # The message must be bounded — not one line per file.
        # If all N file paths were listed, each on its own line, we'd have >> N lines.
        # A bounded summary should have far fewer lines than N.
        line_count = content.count("\n") + 1
        assert line_count < n, (
            f"Message line count ({line_count}) should be less than file count ({n}). "
            f"Message is not summarized:\n{content}"
        )

        # Not every individual path should be present (only a sample at most)
        paths_in_message = sum(1 for f in files if f.name in content or str(f) in content)
        assert paths_in_message < n, (
            f"All {n} file paths appear in message — not summarized. "
            f"Expected only a sample. Got:\n{content}"
        )

    def test_small_changeset_names_each_path(self, tmp_path: Path) -> None:
        """When affected paths are at or below the threshold, each path is still named."""
        from sosa.graph.nodes.staleness import _SUMMARY_THRESHOLD

        n = min(_SUMMARY_THRESHOLD, 3)  # small, definitely at/below threshold
        files = []
        hashes = {}
        for i in range(n):
            f = tmp_path / f"small_file_{i}.txt"
            f.write_text(f"original {i}")
            hashes[str(f)] = hash_file(f)
            files.append(f)

        for f in files:
            f.write_text("modified")

        state = _make_state(hashes)
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected at least one SystemMessage"
        content = sys_msgs[0].content

        # Every individual path must be named in the detail listing
        for f in files:
            assert f.name in content or str(f) in content, (
                f"Expected path '{f.name}' to appear in message for small change set. "
                f"Got:\n{content}"
            )

    def test_large_changeset_summary_contains_changed_deleted_counts(
        self, tmp_path: Path
    ) -> None:
        """Summary message for large change sets includes changed and deleted counts."""
        from sosa.graph.nodes.staleness import _SUMMARY_THRESHOLD

        n_changed = _SUMMARY_THRESHOLD // 2 + 1
        n_deleted = _SUMMARY_THRESHOLD // 2 + 1
        # total = n_changed + n_deleted > threshold

        changed_files = []
        deleted_files = []
        hashes = {}

        for i in range(n_changed):
            f = tmp_path / f"chg_{i}.txt"
            f.write_text(f"v1_{i}")
            hashes[str(f)] = hash_file(f)
            changed_files.append(f)

        for i in range(n_deleted):
            f = tmp_path / f"del_{i}.txt"
            f.write_text(f"data_{i}")
            hashes[str(f)] = hash_file(f)
            deleted_files.append(f)

        # Apply changes
        for f in changed_files:
            f.write_text("v2")
        for f in deleted_files:
            f.unlink()

        state = _make_state(hashes)
        result = staleness(state)

        sys_msgs = _system_messages(result)
        assert sys_msgs, "Expected a SystemMessage"
        content = sys_msgs[0].content

        # Summary should mention how many changed and how many deleted
        assert str(n_changed) in content, (
            f"Expected changed count {n_changed} in summary. Got:\n{content}"
        )
        assert str(n_deleted) in content, (
            f"Expected deleted count {n_deleted} in summary. Got:\n{content}"
        )
