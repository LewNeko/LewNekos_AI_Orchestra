"""Shared paths and output limits for local agent tools."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPOSITORY_ROOT / "skills"

MAX_READ_CHARS = 12_000
MAX_RUN_CHARS = 6_000
MAX_LINT_CHARS = 12_000
