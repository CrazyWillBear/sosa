"""Content-hashing utilities for Sosa tools.

Provides a reusable helper to fingerprint file contents.
Used by read_file to record per-session path→hash state, and
available to later phases (e.g. staleness detection in #5).
"""

import hashlib
from pathlib import Path


def hash_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of the file at *path*.

    Reads the file in binary mode so the hash is encoding-agnostic.

    Raises:
        FileNotFoundError: if *path* does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return digest
