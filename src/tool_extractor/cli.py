from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from .extractor import extract_tools


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AST-based tool extractor (POC)")
    parser.add_argument("--repo", required=True, help="Path to the target repository root")
    parser.add_argument(
        "--out",
        default=str(Path("artifacts") / "tools.json"),
        help="Path to output JSON (default: artifacts/tools.json)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo)
    if not repo_root.is_dir():
        print(f"Error: --repo '{repo_root}' is not a directory or not accessible.")
        return 2

    tools, files_scanned, files_skipped = extract_tools(str(repo_root))

    # Deterministic ordering
    tools_sorted: List[Dict[str, Any]] = sorted(tools, key=lambda r: (r["module"], r["name"]))

    out_path = Path(args.out)
    out_dir = out_path.parent
    _ensure_dir(out_dir)

    # Write tools.json
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(tools_sorted, f, ensure_ascii=False, indent=2)

    # Write summary next to the JSON output
    summary_path = out_dir / "tools_summary.txt"
    total_tools = len(tools_sorted)
    summary_lines = [
        f"Scanned files: {files_scanned}",
        f"Files skipped: {files_skipped}",
        f"Tools found: {total_tools}",
        f"Output: {out_path}",
    ]
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print(f"Scanned {files_scanned} files, found {total_tools} tools, skipped {files_skipped} files")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


