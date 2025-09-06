"""AST-based tool extractor package (POC).

Exposes a simple API:
    extract_tools(repo_path: str) -> tuple[list[dict], int, int]
which returns (tools, files_scanned, files_skipped).
"""

from .extractor import extract_tools  # noqa: F401

__all__ = ["extract_tools"]


