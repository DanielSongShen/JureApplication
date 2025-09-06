from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple, List, Dict
from pydantic import BaseModel, Field


class ToolRef(BaseModel):
	tool_id: str
	match_type: Literal["exact", "alias", "fuzzy"] = "exact"
	code_span: Optional[Tuple[int, int]] = None


class NotebookUnit(BaseModel):
	source_path: str
	unit_id: str
	cell_index: int
	prose_text: str
	code_text: str
	execution_count: Optional[int] = None
	referenced_tools: List[ToolRef] = Field(default_factory=list)


class MetricCriterion(BaseModel):
	name: str
	op: Literal[">=", "<=", "==", ">", "<"]
	value: float


class SuccessCriterion(BaseModel):
	metric: Optional[MetricCriterion] = None
	stdout_contains: Optional[str] = None
	file_saved: Optional[str] = None


class TaskSpec(BaseModel):
	id: str
	source_path: str
	cell_index: int
	title: str
	description: str
	code_snippet: str
	referenced_tools: List[ToolRef] = Field(default_factory=list)
	evaluation_type: str
	expected_outcome: Optional[str] = None
	success_criteria: Optional[List[SuccessCriterion]] = None

	@classmethod
	def from_unit(cls, unit: NotebookUnit, code_snippet: str) -> "TaskSpec":
		return cls(
			id=f"{Path(unit.source_path).stem}_{unit.cell_index}",
			source_path=unit.source_path,
			cell_index=unit.cell_index,
			title=f"Unit {unit.cell_index}",
			description=unit.prose_text.strip()[:200],
			code_snippet=code_snippet,
			referenced_tools=unit.referenced_tools,
			evaluation_type="text",
		)


class Notebook(BaseModel):
	source_path: str
	units: List[NotebookUnit] = Field(default_factory=list)
	import_map: Dict[str, str] = Field(default_factory=dict)
