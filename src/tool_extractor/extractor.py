from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Set, Tuple, Dict, Any

from .filesystem import discover_python_files
from .models import ToolRecord


def _read_and_parse(path: Path) -> Tuple[Optional[str], Optional[ast.Module]]:
    """Read a file and return (source_text, parsed_ast_module).

    Returns (None, None) on I/O, decoding, or syntax errors so callers can
    count the file as skipped without raising.
    """
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
    """Return top-level function and async function definitions from a module."""
    return [
        n
        for n in module.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _is_public(name: str, literal_all: Set[str]) -> bool:
    """Heuristic publicness: not leading underscore unless present in __all__."""
    return (not name.startswith("_")) or (name in literal_all)


def _get_annotation_text(source: str, annotation: Optional[ast.AST]) -> Optional[str]:
    """Render an annotation AST back to text.

    Preference order:
    1) Exact source segment (preserves formatting and forward references)
    2) ast.unparse fallback when available
    Returns None if no annotation exists or unparsing fails.
    """
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
    """Reconstruct a Python signature string from a FunctionDef/AsyncFunctionDef.

    Handles all parameter kinds (positional-only, positional-or-keyword, var-positional,
    keyword-only, var-keyword) and aligns defaults according to the AST's defaults
    layout. Inserts '/' for positional-only and '*' when needed for keyword-only
    parameters. Preserves annotation text using source segments when possible.
    """
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


def _normalize_module_name(mod: str) -> str:
    """Normalize module names for src-layout and future rules.

    Current rules:
    - Strip leading 'src.' if present.
    """
    if mod.startswith("src."):
        mod = mod[len("src.") :]
    return mod


def _module_name_for(file_path: Path, repo_root: Path) -> str:
    """Compute the dotted module name for a file under the repository root.

    - Produces src-layout aware names (e.g., strips trailing '.__init__').
    - Normalizes with _normalize_module_name for consistency across layouts.
    """
    rel = file_path.relative_to(repo_root).as_posix()
    mod = rel[:-3].replace("/", ".")  # strip .py
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    return _normalize_module_name(mod)


def _resolve_relative_module(current_module: str, module: Optional[str], level: int) -> str:
    """Resolve a relative import target to an absolute dotted path.

    Parameters
    - current_module: The dotted path of the module performing the import
      (e.g., 'pkg.subpkg.__init__' caller context already normalized upstream).
    - module: The 'from X import ...' target (can be None for 'from . import ...').
    - level: The number of leading dots indicating relative depth.

    The algorithm climbs 'level-1' parents from current_module, then appends the
    explicit 'module' if provided. For 'from . import subpkg as alias', module is
    None and we return the package prefix for alias handling at the call site.
    """
    # Resolve relative import target to absolute dotted path
    if level <= 0:
        return module or current_module
    parts = current_module.split(".")
    # If importing from a package __init__, current_module is the package path
    base = parts[: len(parts) - level + 1] if level > 0 else parts
    prefix = ".".join([p for p in base if p])
    if module:
        if prefix:
            return f"{prefix}.{module}"
        return module
    return prefix


def extract_tools(repo_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
    """Extract public top-level functions and their public API exposure.

    Two-pass strategy over the repository:
    1) Parse files to collect function definitions and package-level export hints:
       - Top-level functions that are public (not prefixed '_' unless in __all__)
       - Package re-exports (from X import Y as Z) and subpackage aliases
       - __all__ declarations per package
    2) Synthesize public API view by emitting records for re-exported names and
       aliased subpackages. Falls back to heuristics when explicit exports are
       absent, optionally guided by __all__.

    Returns (records, files_scanned, files_skipped).
    """
    repo_root = Path(repo_path)
    results: List[Dict[str, Any]] = []
    files_scanned = 0
    files_skipped = 0

    # Pass 1: collect function defs and package re-exports/aliases
    defs_by_full: Dict[str, ToolRecord] = {}
    exports_by_package: Dict[str, Dict[str, str]] = defaultdict(dict)  # pkg -> name -> origin full dotted
    aliases_by_package: Dict[str, Dict[str, str]] = defaultdict(dict)  # pkg -> alias -> subpkg
    all_by_package: Dict[str, Set[str]] = defaultdict(set)  # pkg -> names declared in __all__

    seen_ids: Set[str] = set()

    for file in discover_python_files(repo_root):
        files_scanned += 1
        source, module = _read_and_parse(file)
        if module is None or source is None:
            files_skipped += 1
            continue

        module_name = _module_name_for(file, repo_root)
        literal_all = _extract_literal_all(module)

        # Collect top-level functions (definitions)
        for fn in _extract_top_level_functions(module):
            if not _is_public(fn.name, literal_all):
                continue
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
            seen_ids.add(record.id)
            defs_by_full[f"{module_name}.{fn.name}"] = record

        # If this is a package __init__, collect __all__, re-exports and aliases
        if file.name == "__init__.py":
            if literal_all:
                all_by_package[module_name] |= literal_all
            for node in module.body:
                if isinstance(node, ast.ImportFrom):
                    abs_mod = _resolve_relative_module(module_name, node.module, node.level or 0)
                    if node.module is None and (node.level or 0) > 0:
                        # from . import subpkg as alias
                        for n in node.names:
                            alias = n.asname or n.name
                            aliases_by_package[module_name][alias] = n.name
                    else:
                        # from X import a as b, including star
                        for n in node.names:
                            if n.name == "*":
                                # Defer star handling (optional future work)
                                continue
                            exported_name = n.asname or n.name
                            origin = f"{abs_mod}.{n.name}"
                            exports_by_package[module_name][exported_name] = origin
                # Direct 'import' rarely used for local re-exports; ignore for now

    # Helper: build public export mapping for a package with fallbacks
    def _public_exports_for_package(pkg: str) -> Dict[str, str]:
        """Return mapping export_name -> origin.full.dotted for a package.

        Preference order:
        - Explicit 'from X import name as alias' collected for the package
        - If none, infer from available definitions within the package tree,
          optionally restricting to names present in __all__
        - As a last resort, consider the top-level package scope

        Where multiple candidates exist, a simple score prefers modules whose
        leaf name best matches the function name (e.g., '....<name>' > '...._<name>').
        """
        mapping = dict(exports_by_package.get(pkg, {}))
        if mapping:
            return mapping
        preferred_names = all_by_package.get(pkg, set())
        candidates = [full for full in defs_by_full.keys() if full.startswith(f"{pkg}.")]
        if not candidates:
            # fallback to top-level package scope
            top = pkg.split(".")[0]
            candidates = [full for full in defs_by_full.keys() if full.startswith(f"{top}.")]
        name_to_best: Dict[str, str] = {}
        def score(full: str, name: str) -> int:
            mod = full.rsplit(".", 1)[0]
            leaf = mod.split(".")[-1]
            if leaf == name:
                return 3
            if leaf == f"_{name}":
                return 2
            return 1
        for full in candidates:
            name = full.split(".")[-1]
            if preferred_names and name not in preferred_names:
                continue
            prev = name_to_best.get(name)
            if prev is None or score(full, name) > score(prev, name):
                name_to_best[name] = full
        return name_to_best

    # Pass 2: emit public API tool records based on re-exports and aliases
    def _emit_public(public_module: str, export_name: str, origin: str) -> None:
        """Emit a ToolRecord for a public API name if its origin is known.

        Avoid duplicates by tracking seen ids. Carries over signature and
        first-line doc from the origin definition.
        """
        src = defs_by_full.get(origin)
        if not src:
            return
        rec_id = f"{public_module}:{export_name}"
        if rec_id in seen_ids:
            return
        results.append(ToolRecord(
            id=rec_id,
            module=public_module,
            name=export_name,
            signature=src.signature,
            doc_first_line=src.doc_first_line,
            file=src.file,
            lineno=src.lineno,
        ).to_dict())
        seen_ids.add(rec_id)

    # Direct exports (explicit or inferred via __all__/fallback)
    direct_pkgs = set(exports_by_package.keys()) | set(all_by_package.keys())
    for pkg in direct_pkgs:
        mapping = _public_exports_for_package(pkg)
        for export_name, origin in mapping.items():
            _emit_public(pkg, export_name, origin)

    # Aliased subpackages on parent package (e.g., scanpy: pp -> preprocessing)
    for parent_pkg, alias_map in aliases_by_package.items():
        for alias, subpkg in alias_map.items():
            child_pkg = f"{parent_pkg}.{subpkg}"
            child_exports = _public_exports_for_package(child_pkg)
            for export_name, origin in child_exports.items():
                public_module = f"{parent_pkg}.{alias}"
                _emit_public(public_module, export_name, origin)

    return results, files_scanned, files_skipped


