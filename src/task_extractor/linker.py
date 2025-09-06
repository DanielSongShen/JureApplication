from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

from .models import NotebookUnit, ToolRef


def _build_import_map(code: str) -> Dict[str, str]:
	alias_to_dotted: Dict[str, str] = {}
	try:
		tree = ast.parse(code)
	except Exception:
		return alias_to_dotted
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for n in node.names:
				name = n.name
				asname = n.asname or name.split(".")[0]
				alias_to_dotted[asname] = name
		elif isinstance(node, ast.ImportFrom):
			module = node.module or ""
			for n in node.names:
				name = n.name
				asname = n.asname or name
				dotted = f"{module}.{name}" if module else name
				alias_to_dotted[asname] = dotted
	return alias_to_dotted


def _attr_to_dotted(node: ast.AST) -> str | None:
	# Convert nested Attribute(Name(...)) to dotted string
	parts: List[str] = []
	cur = node
	while isinstance(cur, ast.Attribute):
		parts.append(cur.attr)
		cur = cur.value
	if isinstance(cur, ast.Name):
		parts.append(cur.id)
		return ".".join(reversed(parts))
	return None


def _extract_call_dotted(code: str, import_map: Dict[str, str]) -> List[str]:
	dotted_calls: List[str] = []
	try:
		tree = ast.parse(code)
	except Exception:
		return dotted_calls
	for node in ast.walk(tree):
		if isinstance(node, ast.Call):
			func = node.func
			dotted: str | None = None
			if isinstance(func, ast.Name):
				name = func.id
				base = import_map.get(name)
				if base:
					dotted = base
				else:
					dotted = name
			elif isinstance(func, ast.Attribute):
				dotted = _attr_to_dotted(func)
				if dotted:
					root = dotted.split(".")[0]
					if root in import_map:
						mapped_root = import_map[root]
						rest = ".".join(dotted.split(".")[1:])
						dotted = f"{mapped_root}.{rest}" if rest else mapped_root
			if dotted:
				dotted_calls.append(dotted)
	return dotted_calls


def _load_tool_candidates(tools_json: Path) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
	# Returns (full_dotted_to_id, name_to_ids)
	full_map: Dict[str, str] = {}
	name_map: Dict[str, Set[str]] = {}
	if not tools_json.exists():
		return full_map, name_map
	data = json.loads(tools_json.read_text())
	if isinstance(data, dict):
		records = data.get("tools", [])
	else:
		records = data
	for rec in records:
		tool_id = rec.get("id") or rec.get("tool_id")
		module = rec.get("module") or rec.get("mod") or ""
		name = rec.get("name") or rec.get("func") or rec.get("symbol")
		if not tool_id or not name:
			continue
		full = f"{module}.{name}".strip(".")
		if full:
			full_map[full] = tool_id
		name_map.setdefault(name, set()).add(tool_id)
		# Also allow matching by id if referenced directly
		full_map[tool_id] = tool_id
	return full_map, name_map


def link_tools_for_unit(unit: NotebookUnit, tools_json: Path) -> List[ToolRef]:
	import_map = _build_import_map(unit.code_text)
	calls = _extract_call_dotted(unit.code_text, import_map)
	full_map, name_map = _load_tool_candidates(tools_json)

	seen: Set[str] = set()
	refs: List[ToolRef] = []
	for dotted in calls:
		if dotted in full_map and full_map[dotted] not in seen:
			refs.append(ToolRef(tool_id=full_map[dotted], match_type="exact"))
			seen.add(full_map[dotted])
			continue
		last = dotted.split(".")[-1]
		candidate_ids = name_map.get(last, set())
		for cid in candidate_ids:
			if cid in seen:
				continue
			refs.append(ToolRef(tool_id=cid, match_type="fuzzy"))
			seen.add(cid)
	return refs
