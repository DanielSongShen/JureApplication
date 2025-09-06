from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict, Any

from .filesystem import discover_python_files
from .models import ToolRecord


def _read_and_parse(path: Path) -> Tuple[Optional[str], Optional[ast.Module]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, None
    try:
        module = ast.parse(text, filename=str(path))
    except SyntaxError:
        return None, None
    return text, module


def _collect_string_constants(node: ast.AST) -> Set[str]:
    """Collect string constants from a literal container (list/tuple/set).

    Non-string or nested non-literal values are ignored.
    """
    items: List[ast.AST] = []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        items = list(node.elts)
    else:
        return set()

    names: Set[str] = set()
    for elt in items:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            names.add(elt.value)
    return names


def _extract_literal_all(module: ast.Module) -> Set[str]:
    names: Set[str] = set()
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    names |= _collect_string_constants(node.value)
    return names


def _extract_top_level_functions(module: ast.Module) -> List[ast.AST]:
    return [
        n
        for n in module.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _is_public(name: str, literal_all: Set[str]) -> bool:
    return (not name.startswith("_")) or (name in literal_all)


def _get_annotation_text(source: str, annotation: Optional[ast.AST]) -> Optional[str]:
    if annotation is None:
        return None
    # Prefer exact source segment
    try:
        seg = ast.get_source_segment(source, annotation)
        if seg:
            return seg.strip()
    except Exception:
        pass
    # Fallback to unparse if available
    try:
        return ast.unparse(annotation)
    except Exception:
        return None


def _format_param(name: str, ann: Optional[str], default: bool) -> str:
    if ann:
        base = f"{name}: {ann}"
    else:
        base = name
    if default:
        base += "=..."
    return base


def _render_signature(fn: ast.AST, source: str) -> str:
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    args = fn.args

    parts: List[str] = []

    # Build combined positional (posonly + args) for default alignment
    positional_params = list(args.posonlyargs) + list(args.args)
    num_positional = len(positional_params)
    num_positional_defaults = len(args.defaults)
    first_default_index = num_positional - num_positional_defaults if num_positional_defaults else num_positional

    # Positional-only
    for index, param in enumerate(args.posonlyargs):
        ann = _get_annotation_text(source, param.annotation)
        has_default = index >= first_default_index
        parts.append(_format_param(param.arg, ann, has_default))
    if args.posonlyargs:
        parts.append("/")

    # Positional-or-keyword
    for idx, param in enumerate(args.args):
        absolute_index = len(args.posonlyargs) + idx
        ann = _get_annotation_text(source, param.annotation)
        has_default = absolute_index >= first_default_index
        parts.append(_format_param(param.arg, ann, has_default))

    # Var positional
    if args.vararg:
        ann = _get_annotation_text(source, args.vararg.annotation)
        name = f"*{args.vararg.arg}"
        parts.append(_format_param(name, ann, default=False))

    # Keyword-only
    if args.kwonlyargs and not args.vararg:
        parts.append("*")
    for i, param in enumerate(args.kwonlyargs):
        ann = _get_annotation_text(source, param.annotation)
        default_node = args.kw_defaults[i]
        has_default = default_node is not None
        parts.append(_format_param(param.arg, ann, has_default))

    # Var keyword
    if args.kwarg:
        ann = _get_annotation_text(source, args.kwarg.annotation)
        name = f"**{args.kwarg.arg}"
        parts.append(_format_param(name, ann, default=False))

    params_rendered = ", ".join(parts)

    return_ann = _get_annotation_text(source, fn.returns)
    kind = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
    if return_ann:
        return f"{kind} {fn.name}({params_rendered}) -> {return_ann}"
    return f"{kind} {fn.name}({params_rendered})"


def _module_name_for(file_path: Path, repo_root: Path) -> str:
    rel = file_path.relative_to(repo_root).as_posix()
    mod = rel[:-3].replace("/", ".")  # strip .py
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    return mod


def extract_tools(repo_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
    repo_root = Path(repo_path)
    results: List[Dict[str, Any]] = []
    files_scanned = 0
    files_skipped = 0

    for file in discover_python_files(repo_root):
        files_scanned += 1
        source, module = _read_and_parse(file)
        if module is None or source is None:
            files_skipped += 1
            continue

        literal_all = _extract_literal_all(module)
        for fn in _extract_top_level_functions(module):
            if not _is_public(fn.name, literal_all):
                continue
            module_name = _module_name_for(file, repo_root)
            signature = _render_signature(fn, source)
            doc_first_raw = (ast.get_docstring(fn, clean=True) or "").strip().splitlines()
            doc_first_line = doc_first_raw[0] if doc_first_raw else ""
            record = ToolRecord(
                id=f"{module_name}:{fn.name}",
                module=module_name,
                name=fn.name,
                signature=signature,
                doc_first_line=doc_first_line,
                file=str(file.relative_to(repo_root).as_posix()),
                lineno=fn.lineno,
            )
            results.append(record.to_dict())

    return results, files_scanned, files_skipped


