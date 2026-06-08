"""Build the MEMORY.md index from per-fact files in soul_memory_path/memory/.

Each memory file is a markdown file with YAML frontmatter containing at least
``description`` and ``type`` fields, followed by an optional body.

The index is written to soul_memory_path/MEMORY.md unconditionally every turn
(hash-gating is a later slice).  Returns the index content as a string, or None
when no memory files exist.

Raises :exc:`MalformedMemoryFileError` (naming the offending file) when any
memory file has missing or incomplete frontmatter.  The caller is responsible
for catching this and surfacing it back to the agent.
"""

from pathlib import Path

# Suggested types appear in this order; any other types follow (alphabetically).
_SUGGESTED_TYPES = ("user", "feedback", "project", "reference")

_REQUIRED_FIELDS = ("description", "type")


class MalformedMemoryFileError(ValueError):
    """Raised when a memory file has missing or incomplete YAML frontmatter.

    The error message always names the offending file so the agent can locate
    and fix it.
    """


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter from *text*.

    Expects the file to start with ``---\\n``, followed by ``key: value`` lines,
    closed by another ``---`` line.  Only the frontmatter block is parsed.
    Returns an empty dict when the opening ``---`` is absent (no frontmatter).
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


def _validate_frontmatter(fields: dict[str, str], path: Path) -> None:
    """Raise :exc:`MalformedMemoryFileError` if *fields* is missing required keys.

    Checks for the presence of a ``---`` block (non-empty *fields*) and each of
    the required field names.  Names *path* in the error message.
    """
    if not fields:
        raise MalformedMemoryFileError(
            f"Memory file '{path}' has no frontmatter (expected a '---' block "
            f"with 'description' and 'type' fields)."
        )
    missing = [f for f in _REQUIRED_FIELDS if not fields.get(f)]
    if missing:
        raise MalformedMemoryFileError(
            f"Memory file '{path}' is missing required frontmatter "
            f"field(s): {', '.join(missing)}."
        )


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

    # Group files by type; raise loudly on malformed frontmatter
    groups: dict[str, list[tuple[str, str]]] = {}  # type → [(stem, description)]
    for path in md_files:
        fm = _parse_frontmatter(path.read_text())
        _validate_frontmatter(fm, path)
        description = fm["description"]
        type_ = fm["type"]
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
