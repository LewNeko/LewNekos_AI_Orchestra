"""Subprocess-backed agent tools."""

import subprocess
import sys
from collections.abc import Sequence

from .constants import MAX_LINT_CHARS, MAX_RUN_CHARS


def run_python(path: str) -> str:
    """Run a Python script using the same interpreter as the Orchestrator."""
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
        return (result.stdout + result.stderr)[-MAX_RUN_CHARS:] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: script timed out after 120 seconds."
    except Exception as error:  # noqa: BLE001 - a tool boundary returns failures to the model
        return f"Error: {error}"


def _truncate(text: str) -> str:
    if len(text) > MAX_LINT_CHARS:
        return text[:MAX_LINT_CHARS] + "\n...[TRUNCATED] ..."
    return text


def _run_linter(linter_name: str, command: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=300,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except FileNotFoundError:
        stdout = ""
        stderr = "Tool not installed"
        exit_code = -1
    except Exception as error:  # noqa: BLE001 - a tool boundary returns failures to the model
        stdout = ""
        stderr = str(error)
        exit_code = -1

    return (
        f"=== {linter_name.upper()} ===\n"
        f"Exit Code: {exit_code}\n\n"
        f"STDOUT:\n{_truncate(stdout)}\n\n"
        f"STDERR:\n{_truncate(stderr)}\n\n"
        f"{'=' * 20}\n"
    )


def run_linter_check(path: str) -> str:
    """Run Ruff and Pylint and return their bounded stdout/stderr reports."""
    return _run_linter("ruff", ["ruff", "check", path]) + _run_linter(
        "pylint", ["pylint", path]
    )
