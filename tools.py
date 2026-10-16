"""
tools.py
--------
Define what the agent is allowed to DO. Start small -- one or two
safe, read-only tools -- and expand once the loop is solid.
"""

import os
import pathlib
import subprocess
import sys
#import List this was from something import List but i forgot the 'from something' part.

# Anchor the skills folder to this file, not the current working directory.
SKILLS_DIR = pathlib.Path(__file__).resolve().parent / "skills"

# Keep tool output bounded so it doesn't blow up context.
MAX_READ_CHARS = 12000
MAX_RUN_CHARS = 6000
MAX_LINT_CHARS = 12000
# OpenAI-style tool schema. Both backends understand this shape
# (ClaudeBackend converts it internally).
TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a given directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Run a Python script and return its stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to python script."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_index",
            "description": (
                "List the available skills: the path, name and description of every "
                "SKILL.md in the skills/ folder. Call this first to find the skill that "
                "matches the task, then use read_file on its path before writing code."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function":{
            "name": "write_file",
            "description": (
                "Write content to a file, creating any necessary parent directories. "
                "(You can use this to create a new folder as well as new files). "
                "Warning, If the file already exists, it will be overwritten."
            ),
            "properties": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to."},
                    "content": {"type": "string", "description": "Content to write to the file."}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_linter_check",
            "description": "Run Ruff and Pylint checks on a directory or file"
            "and return the findings",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file or directory to lint."}
                },
                "required": ["path"],
            },
        },
    },
]


def list_directory(path: str) -> str:
    try:
        entries = os.listdir(path)
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:  # return errors as text so the model can recover
        return f"Error: {e}"


def read_file(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read()
        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + "\n...(truncated)"
        return content
    except Exception as e:
        return f"Error: {e}"


def skill_index() -> str:
    if not SKILLS_DIR.is_dir():
        return f"Error: skills folder not found at {SKILLS_DIR}"
    lines = []
    for f in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = f.read_text(errors="replace")
        # Simple frontmatter parse: text between the first two '---' lines.
        parts = text.split("---", 2)
        head = parts[1].strip() if text.startswith("---") and len(parts) == 3 else text[:200].strip()
        lines.append(f"- {f}: {head}")
    return "\n".join(lines) if lines else "(no skills found)"


def run_python(path: str) -> str:
    """Run a Python script and return its stdout and stderr."""
    try:
        r = subprocess.run(
            [sys.executable, path], capture_output=True, text=True, timeout=120
        )
        return (r.stdout + r.stderr)[-MAX_RUN_CHARS:] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: script timed out after 120 seconds."
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """
    Write content to a file, creating any necessary parent directories.
    If the file already exists then it will be overwritten.
    """
    try:
        path_obj = pathlib.Path(path).resolve()
        # Create parent directories if they don't exist
        path_obj.parent.mkdir(parents=True, exist_ok=True) #what are these from?

        #Write the file content
        path_obj.write_text(content, encoding="utf-8")

        size = path_obj.stat().st_size #What does this specifically do?
        return (
            f"Successfully wrote to {path}\n"
            f"Absolute path: {path_obj}\n"
            f"File size: {size} bytes"
        )
    except Exception as e:
        return (
            f"Error writing file: {e} by the way\n" 
            f"I should make more err types to find out the specific problem later"
        )

def run_linter_check(path: str) -> str:
    """
    Run Ruff and Pylint checks on a directory or file and return findings.
    Captures stdout, stderr, and exit codes for both.
    """
    output = []

    def get_linter_results(linter_name: str, cmd_args: List[str]) -> str:
        try:
            res = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=300 #5 minutes
            )
            stdout = res.stdout
            stderr = res.stderr
            exit_code = res.returncode
        except FileNotFoundError: #why are setting the variables to be this? why tool not installed?
            stdout = "Tool not installed"
            stderr = "Tool not installed"    
            exit_code = -1
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = -1

        #I should make a method for the 
        # model to request the truncated information 
        # anyway instead of just throwing it away in case it's 
        # actually necessary for the model to see the entire thing.
        def truncate(text: str) -> str:
            if len(text) > MAX_LINT_CHARS:
                return text[:MAX_LINT_CHARS] + "\n...[TRUNCATED] ... "
            return text    

        return (
            f"=== {linter_name.upper()} === \n"
            f"Exit Code: {exit_code}\n\n"
            f"STDOUT:\n{truncate(stdout)}\n\n"
            f"STDERR:\n{truncate(stderr)}\n\n"
            f"{'=' * 20}\n" #what does this last part mean?
        )

    # Ruff typically takes "check" as a subcommand
    ruff_results = get_linter_results("ruff", ["ruff", "check", path]) #recursive i think

    # Pylint takes the path directly
    pylint_results = get_linter_results("pylint", ["pylint", path])

    return ruff_results + pylint_results

def edit_context(messages: list) -> str:
    """
    Replaces the current conversation history with the provided list of messages.
    Use this to summarize long histories, remove irrelevant information,
    or keep only the most important facts to save context space.
    """
    #the actual code goes here but i don't have the time rn, just know
    #in a real CLM implement, this would overwrite the state object
    # for now cause i'm dumb ass fuck i'ma just put a message for the return
    return "Nothing happened LOL"

TOOL_FUNCTIONS = {
    "list_directory": list_directory,
    "read_file": read_file,
    "skill_index": skill_index,
    "run_python": run_python,
    "run_linter_check": run_linter_check,
    "write_file": write_file
}