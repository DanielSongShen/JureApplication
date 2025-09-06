from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class ToolRecord:
    id: str
    module: str
    name: str
    signature: str
    doc_first_line: str
    file: str
    lineno: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


