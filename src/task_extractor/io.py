from __future__ import annotations

from pathlib import Path
from typing import TextIO

from .models import TaskSpec, NotebookUnit


class TasksWriter:
	def __init__(self, path: Path) -> None:
		self.path = path
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._fh: TextIO = self.path.open("w", encoding="utf-8")

	def write(self, task: TaskSpec) -> None:
		self._fh.write(task.model_dump_json())
		self._fh.write("\n")
		self._fh.flush()

	def close(self) -> None:
		self._fh.close()


class UnitsReportWriter:
	def __init__(self, path: Path) -> None:
		self.path = path
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._fh: TextIO = self.path.open("w", encoding="utf-8")
		self._fh.write("# Units Report\n\n")

	def write_unit(self, unit: NotebookUnit, task: TaskSpec) -> None:
		self._fh.write(f"## {Path(unit.source_path).name} – cell {unit.cell_index}\n\n")
		self._fh.write(f"Title: {task.title}\n\n")
		self._fh.write("Prose:\n\n")
		self._fh.write("```\n")
		self._fh.write(unit.prose_text.strip() + "\n")
		self._fh.write("```\n\n")
		self._fh.write("Snippet Preview:\n\n")
		self._fh.write("```python\n")
		preview = (task.code_snippet or "").strip().splitlines()
		self._fh.write("\n".join(preview[:20]) + ("\n...\n" if len(preview) > 20 else "\n"))
		self._fh.write("```\n\n")

	def close(self) -> None:
		self._fh.close()
