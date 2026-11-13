"""Settings read from the environment (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    db_url: str
    data_seed: int
    subjects_per_study: int
    genai_provider: str
    genai_fallback: bool
    claude_model: str
    reports_dir: Path


def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        db_url=os.getenv("DB_URL", "postgresql+psycopg://qa:qa@localhost:55432/clinical"),
        data_seed=int(os.getenv("DATA_SEED", "42")),
        subjects_per_study=int(os.getenv("SUBJECTS_PER_STUDY", "40")),
        genai_provider=os.getenv("GENAI_PROVIDER", "template").lower(),
        genai_fallback=os.getenv("GENAI_FALLBACK", "on").lower() not in ("off", "false", "0", "no"),
        claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        reports_dir=Path(os.getenv("REPORTS_DIR", str(ROOT / "reports"))),
    )
