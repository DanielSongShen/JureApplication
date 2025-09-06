from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

import nbformat

from .models import NotebookUnit


def _collect_markdown_span(md_cells: List[str]) -> str:
	return "\n\n".join(md_cells).strip()


def segment_notebook(nb_path: Path) -> Iterator[NotebookUnit]:
	nb = nbformat.read(str(nb_path), as_version=4)
	prior_markdown: List[str] = []
	for idx, cell in enumerate(nb.cells):
		cell_type = cell.get("cell_type")
		if cell_type == "markdown":
			text = cell.get("source", "") or ""
			prior_markdown.append(text)
			continue
		if cell_type == "code":
			code_text: str = cell.get("source", "") or ""
			if not code_text.strip():
				continue
			prose = _collect_markdown_span(prior_markdown)
			unit = NotebookUnit(
				source_path=str(nb_path),
				unit_id=f"{nb_path.stem}:cell_{idx}",
				cell_index=idx,
				prose_text=prose,
				code_text=code_text,
				execution_count=cell.get("execution_count"),
			)
			yield unit
			prior_markdown = []
			continue
		# Reset on other cell types
		prior_markdown = []
