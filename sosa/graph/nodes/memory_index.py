"""Build the MEMORY.md index from per-fact files in soul_memory_path/memory/.

Each memory file is a markdown file with YAML frontmatter containing at least
``description`` and ``type`` fields, followed by an optional body.

The index is written to soul_memory_path/MEMORY.md unconditionally every turn
(hash-gating is a later slice).  Returns the index content as a string, or None
when no memory files exist.
"""

from pathlib import Path

# Suggested types appear in this order; any other types follow (alphabetically).
_SUGGESTED_TYPES = ("user", "feedback", "project", "reference")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter from *text*.

    Expects the file to start with ``---\\n``, followed by ``key: value`` lines,
    closed by another ``---`` line.  Only the frontmatter block is parsed.
    Assumes well-formed input (no error handling in this slice).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def build_memory_index(soul_memory_path: Path) -> str | None:
    """Scan *soul_memory_path*/memory/ and build a MEMORY.md index.

    Returns the index content (and writes it to MEMORY.md) when at least one
    ``.md`` file is found in the memory directory.  Returns None without writing
    any file when the directory is absent or empty.
    """
    memory_dir = soul_memory_path / "memory"
    if not memory_dir.exists():
        return None

    md_files = sorted(memory_dir.glob("*.md"))
    if not md_files:
        return None

    # Group files by type
    groups: dict[str, list[tuple[str, str]]] = {}  # type → [(stem, description)]
    for path in md_files:
        fm = _parse_frontmatter(path.read_text())
        description = fm.get("description", "")
        type_ = fm.get("type", "")
        groups.setdefault(type_, []).append((path.stem, description))

    # Determine section order: suggested types first (in order), then the rest
    suggested = [t for t in _SUGGESTED_TYPES if t in groups]
    others = sorted(t for t in groups if t not in _SUGGESTED_TYPES)
    ordered_types = suggested + others

    # Build index text
    lines = ["# Memory", ""]
    for type_ in ordered_types:
        lines.append(f"## {type_}")
        for stem, description in groups[type_]:
            lines.append(f"- [{stem}](memory/{stem}.md) — {description}")
        lines.append("")

    # Remove trailing blank line to avoid double-newline at EOF
    while lines and lines[-1] == "":
        lines.pop()

    content = "\n".join(lines) + "\n"

    (soul_memory_path / "MEMORY.md").write_text(content)
    return content
