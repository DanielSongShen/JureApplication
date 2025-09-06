from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable


EXCLUDED_DIR_NAMES = {
    "tests",
    "test",
    "docs",
    "examples",
    ".venv",
    "build",
    "dist",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}


def is_excluded_path(path: Path, repo_root: Path) -> bool:
    """Return True if any component of path (relative to repo_root) is excluded.

    The check is performed on each directory component. If any component matches an
    excluded name, the path is considered excluded.
    """
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        # If path is not under repo_root, be conservative and exclude it
        return True

    for part in relative.parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
        if part.startswith(".") and part not in {".", ".."}:
            # Skip other hidden directories/files by convention
            return True
    return False


def discover_python_files(repo_root: Path) -> Generator[Path, None, None]:
    """Yield Python source files under repo_root respecting exclusion rules.

    Files are yielded in sorted order for determinism.
    """
    candidates: Iterable[Path] = sorted(repo_root.rglob("*.py"))
    for path in candidates:
        if is_excluded_path(path, repo_root):
            continue
        if not path.is_file():
            continue
        yield path


