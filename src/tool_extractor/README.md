## tool_extractor

AST-based Python tool discovery that scans a repository to surface public, top-level functions and their public API exposure (including re-exports and aliased subpackages). Produces a machine-readable list of tools with signatures and first-line docstrings.

### What it does

- Parses Python files under a repository root and discovers top-level functions that are considered public.
- Detects public APIs exposed via package `__init__.py` files:
  - Explicit re-exports: `from package.submod import func as alias`
  - Subpackage aliases: `from . import preprocessing as pp`
  - Optional hints via `__all__ = ["name", ...]`
- Reconstructs function signatures from the AST, preserving annotations.
- Emits structured records for both direct definitions and re-exported names.

### Publicness rules

- A function is public if:
  - Its name does not start with `_`, or
  - It is explicitly listed in `__all__` of its module/package.

### Output format

Each discovered tool is emitted as a JSON object with the following schema (see `models.py`):

```
{
  "id": "package.module:func_name",         // unique id per public API name
  "module": "package.module",               // module exposing the public name
  "name": "func_name",                      // exposed public name
  "signature": "def func_name(x: int) -> str", // reconstructed signature
  "doc_first_line": "Short description...", // first line of the function docstring
  "file": "relative/path/to/file.py",      // file where the function is defined
  "lineno": 42                               // definition line number (1-based)
}
```

Notes:
- Re-exported names reuse the `signature`, `doc_first_line`, `file`, and `lineno` from the original definition.
- The `module` in a re-export record is the public-facing module (e.g., `scanpy.pp`).

### Heuristics for exports

When a package `__init__.py` lacks explicit re-exports, the extractor infers public exports by scanning definitions under the package path. If `__all__` is present, it restricts candidates to those names. When multiple candidates exist, a simple score prefers modules whose leaf name best matches the function name (e.g., `.../<name>.py` outranks `.../_<name>.py`).

Star imports (`from X import *`) are intentionally ignored.

### Directory scanning rules

Excluded directories: `tests`, `test`, `docs`, `examples`, `.venv`, `build`, `dist`, `.git`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, and any hidden directories. See `filesystem.py`.

### API

```
from tool_extractor import extract_tools

tools, files_scanned, files_skipped = extract_tools(repo_path)

# tools is a list[dict] as per schema above
```

### CLI

```
python -m tool_extractor --repo /path/to/repo --out artifacts/tools.json
```

Outputs:
- `artifacts/tools.json`: Sorted list of tool records.
- `artifacts/tools_summary.txt`: A short summary with counts and output path.

Exit code:
- `0` on success; `2` if `--repo` is not a directory.

### Implementation overview

Two-pass approach in `extractor.py`:

1) Collection pass
   - Read and parse each Python file into an AST (`_read_and_parse`).
   - Compute a dotted module name for each file (src-layout aware).
   - Collect top-level public function definitions and emit direct records.
   - For package `__init__.py`, collect:
     - Literal `__all__` strings
     - Explicit re-exports (`from X import a as b`)
     - Subpackage aliases (`from . import subpkg as alias`)

2) Synthesis pass
   - Build a mapping of public exports per package, preferring explicit re-exports; otherwise infer using `__all__` and simple heuristics.
   - Emit additional records for public names on packages and aliased subpackages by pointing back to the original definition.

Signature rendering
- `_render_signature` reconstructs function signatures including positional-only (`/`) and keyword-only (`*`) separators, varargs, kwargs, and annotations.
- Annotation text prefers exact source substrings to preserve formatting, falling back to `ast.unparse` when available.

Module name normalization
- Uses file paths relative to the repo root and replaces `/` with `.`.
- Strips trailing `.__init__` for packages and leading `src.` (to normalize src-layout projects).

Relative import resolution
- `_resolve_relative_module` expands relative imports to absolute dotted paths using the caller module and the import level.

### Limitations

- Does not evaluate dynamic code or execute imports; relies purely on the AST.
- Ignores `from X import *` re-exports.
- Only literal string lists/tuples/sets in `__all__` are supported.
- Focuses on top-level functions; classes/methods are not treated as tools.

### Developing

- Core files:
  - `extractor.py`: AST parsing, collection, and synthesis logic
  - `filesystem.py`: Repository traversal with exclusion rules
  - `cli.py`: CLI entry point for batch extraction
  - `models.py`: `ToolRecord` dataclass and JSON conversion

Run locally via CLI or import the API, as shown above.


