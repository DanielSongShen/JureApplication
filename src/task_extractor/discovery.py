from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


EXCLUDES = [".ipynb_checkpoints"]


def _is_excluded(path: Path) -> bool:
	return any(part in EXCLUDES for part in path.parts)


def discover_notebooks(roots: Iterable[Path], pattern: str = "**/*.ipynb") -> List[Path]:
	notebooks: list[Path] = []
	for root in roots:
		if not root.exists():
			continue
		for p in root.rglob(pattern):
			if _is_excluded(p):
				continue
			if p.is_file() and p.suffix == ".ipynb":
				notebooks.append(p.resolve())
	notebooks.sort()
	return notebooks
