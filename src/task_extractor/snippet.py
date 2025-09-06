from __future__ import annotations

from pathlib import Path

from .models import NotebookUnit


def assemble_minimal_snippet(unit: NotebookUnit) -> str:
	task_id = f"{Path(unit.source_path).stem}_{unit.cell_index}"
	prelude = (
		"import os\n"
		"from pathlib import Path as _Path\n"
		"import random\n"
		"random.seed(0)\n"
		f"ARTIFACT_DIR = _Path('./artifacts') / '{task_id}'\n"
		"ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)\n"
	)
	metric_hint = (
		"\n# If you compute a metric, emit one JSON line like:\n"
		"# print('METRIC_JSON: {"metric": "name", "value": 0.0}')\n"
	)
	return f"{prelude}\n{unit.code_text.strip()}\n{metric_hint}"
