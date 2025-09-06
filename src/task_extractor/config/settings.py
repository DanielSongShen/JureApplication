from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _load_env() -> None:
	# Try CWD first
	load_dotenv(dotenv_path=Path.cwd() / ".env")
	# Walk up from this file looking for .env as fallback
	current = Path(__file__).resolve()
	for parent in [current.parent, *current.parents]:
		candidate = parent / ".env"
		if candidate.exists():
			load_dotenv(dotenv_path=candidate, override=False)
			break


_load_env()


@dataclass
class Settings:
	LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
	LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
	LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
	LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-5-mini")
	LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "1"))
	LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "3000"))
	LLM_TIMEOUT_S: int = int(os.getenv("LLM_TIMEOUT_S", "60"))

	DEFAULT_SOURCE_DIRS: List[str] = field(default_factory=lambda: [
		"notebooks",
		"tutorials",
		"examples",
		"docs",
		".",
	])

	OUTPUT_DIR: str = os.getenv("TASKS_OUTPUT_DIR", "artifacts")
	REPORT_ENABLED: bool = os.getenv("TASKS_REPORT_ENABLED", "0") in {"1", "true", "True"}

	def apply_vendor_env(self) -> None:
		# For OpenAI, map generic key to OPENAI_API_KEY if not set
		if self.LLM_PROVIDER.lower() == "openai" and self.LLM_API_KEY and not os.getenv("OPENAI_API_KEY"):
			os.environ["OPENAI_API_KEY"] = self.LLM_API_KEY


settings = Settings()
settings.apply_vendor_env()
