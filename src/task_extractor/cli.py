from __future__ import annotations

from pathlib import Path
import typing as t

import typer

from .config.settings import settings

app = typer.Typer(add_completion=True, help="Task extractor CLI")


@app.command()
def discover(
	tutorial_dir: t.Optional[Path] = typer.Option(None, exists=True, file_okay=False, resolve_path=True, help="Optional tutorial directory to search"),
	glob: str = typer.Option("**/*.ipynb", help="Glob pattern for notebooks"),
) -> None:
	from .discovery import discover_notebooks

	roots: list[Path]
	if tutorial_dir is not None:
		roots = [tutorial_dir]
	else:
		defaults = settings.DEFAULT_SOURCE_DIRS
		roots = [Path(p) for p in defaults]

	notebooks = discover_notebooks(roots=roots, pattern=glob)
	for nb in notebooks:
		typer.echo(str(nb))


@app.command()
def extract(
	tools_json: Path = typer.Option(Path("artifacts/tools.json"), exists=False, dir_okay=False, resolve_path=True, help="Path to tools.json"),
	output: Path = typer.Option(Path("artifacts/tasks.jsonl"), dir_okay=False, resolve_path=True, help="Output tasks.jsonl"),
	report: bool = typer.Option(False, help="Write units_report.md"),
	max_units: t.Optional[int] = typer.Option(None, help="Optional cap on processed units"),
	tutorial_dir: t.Optional[Path] = typer.Option(None, exists=True, file_okay=False, resolve_path=True, help="Optional tutorial directory to search"),
	llm_provider: t.Optional[str] = typer.Option(None, help="Override LLM provider name"),
	model: t.Optional[str] = typer.Option(None, help="Override LLM model name"),
	dry_run: bool = typer.Option(False, help="Run without LLM calls (structure minimal fields)"),
) -> None:
	from .discovery import discover_notebooks
	from .notebook import segment_notebook
	from .linker import link_tools_for_unit
	from .snippet import assemble_minimal_snippet
	from .io import TasksWriter, UnitsReportWriter
	from .models import TaskSpec
	from .llm import structure_task_from_unit

	if llm_provider:
		settings.LLM_PROVIDER = llm_provider
	if model:
		settings.LLM_MODEL = model

	roots: list[Path]
	if tutorial_dir is not None:
		roots = [tutorial_dir]
	else:
		defaults = settings.DEFAULT_SOURCE_DIRS
		roots = [Path(p) for p in defaults]

	notebooks = discover_notebooks(roots=roots, pattern="**/*.ipynb")

	output.parent.mkdir(parents=True, exist_ok=True)
	tasks_writer = TasksWriter(output)
	report_writer = UnitsReportWriter(output.with_name("units_report.md")) if report else None

	processed = 0
	for nb_path in notebooks:
		for unit in segment_notebook(nb_path):
			unit.referenced_tools = link_tools_for_unit(unit, tools_json)
			snippet = assemble_minimal_snippet(unit)
			if dry_run:
				task = TaskSpec.from_unit(unit=unit, code_snippet=snippet)
			else:
				task = structure_task_from_unit(unit=unit, snippet=snippet)
			tasks_writer.write(task)
			if report_writer:
				report_writer.write_unit(unit, task)
			processed += 1
			if max_units is not None and processed >= max_units:
				break
		if max_units is not None and processed >= max_units:
			break

	tasks_writer.close()
	if report_writer:
		report_writer.close()
