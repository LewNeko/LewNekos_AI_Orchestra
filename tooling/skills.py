"""Skill discovery tool."""

from .constants import SKILLS_DIR


def skill_index() -> str:
    """List each local skill and the frontmatter that describes it."""
    if not SKILLS_DIR.is_dir():
        return f"Error: skills folder not found at {SKILLS_DIR}"

    lines = []
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_file.read_text(errors="replace")
        parts = text.split("---", 2)
        summary = (
            parts[1].strip()
            if text.startswith("---") and len(parts) == 3
            else text[:200].strip()
        )
        lines.append(f"- {skill_file}: {summary}")
    return "\n".join(lines) if lines else "(no skills found)"
