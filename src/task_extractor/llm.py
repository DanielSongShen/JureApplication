from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .config.settings import settings
from .models import NotebookUnit, TaskSpec, ToolRef

logger = logging.getLogger(__name__)


class TaskSpecOut(BaseModel):
	id: str = Field(..., description="Unique task id")
	title: str
	description: str
	code_snippet: str
	evaluation_type: str
	expected_outcome: Optional[str] = None


def _build_prompt() -> ChatPromptTemplate:
	return ChatPromptTemplate.from_messages([
		("system", "You convert a tutorial unit (prose + code) into a concise, runnable task spec."),
		("system", "Return only the structured output; be minimal, keep imports and core calls."),
		("human", (
			"Prose:\n{prose}\n\n"
			"Code:\n```python\n{code}\n```\n\n"
			"Notebook: {nb_path}\n"
			"Provide: title, description, minimal runnable snippet, evaluation type, expected outcome (optional)."
		)),
	])


def structure_task_from_unit(unit: NotebookUnit, snippet: str) -> TaskSpec:
	# Build ID here and pass to model
	task_id = f"{Path(unit.source_path).stem}_{unit.cell_index}"

	logger.info(f"Structuring task from unit: {task_id}")
	logger.debug(f"Input unit source: {unit.source_path}, cell: {unit.cell_index}")
	logger.debug(f"Prose length: {len(unit.prose_text)} chars")
	logger.debug(f"Code length: {len(unit.code_text)} chars")

	prompt = _build_prompt()
	llm = ChatOpenAI(
		api_key=settings.LLM_API_KEY or None,
		model=settings.LLM_MODEL,
		temperature=settings.LLM_TEMPERATURE,
		base_url=settings.LLM_API_URL,
	)

	logger.info(f"Using LLM model: {settings.LLM_MODEL} at {settings.LLM_API_URL}")

	chain = prompt | llm.with_structured_output(TaskSpecOut)

	logger.debug("Invoking LLM chain with structured output")
	result: TaskSpecOut = chain.invoke({
		"prose": unit.prose_text,
		"code": unit.code_text,
		"nb_path": unit.source_path,
	})

	logger.info(f"LLM call completed for task: {task_id}")
	logger.debug(f"Generated title: {result.title}")
	logger.debug(f"Evaluation type: {result.evaluation_type}")

	# Merge with known fields
	task_spec = TaskSpec(
		id=result.id or task_id,
		source_path=unit.source_path,
		cell_index=unit.cell_index,
		title=result.title,
		description=result.description,
		code_snippet=result.code_snippet or snippet,
		referenced_tools=unit.referenced_tools,
		evaluation_type=result.evaluation_type,  # type: ignore[arg-type]
		expected_outcome=result.expected_outcome,
	)

	logger.info(f"Task spec created: {task_spec.id}")
	return task_spec
