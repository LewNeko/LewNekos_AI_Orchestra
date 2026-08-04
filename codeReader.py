import requests, json, re
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:14b"

def load_agent(path):
    """Parse an agent .md file: YAML frontmatter + system prompt body."""
    text = Path(path).read_text()
    if text.startswith("---"):
        _, frontmatter, body = text.split("---", 2)
        meta = {}
        for line in frontmatter.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta, body.strip()
    return {}, text.strip()

def run_agent(system_prompt, user_input):
    """Fresh, isolated context per call — no shared history between agents."""
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
    })
    return resp.json()["message"]["content"]

def review_diff(diff_text):
    agents_dir = Path("agents")
    findings = {}

    # Step 1: run each specialist agent in its own isolated context
    for agent_file in agents_dir.glob("*.md"):
        meta, system_prompt = load_agent(agent_file)
        name = meta.get("name", agent_file.stem)
        print(f"Running {name}...")
        findings[name] = run_agent(system_prompt, f"Review this diff:\n\n{diff_text}")

    # Step 2: validator pass — separate context, only sees the outputs, not the diff
    validator_prompt = """You are a validation agent. You will be given the outputs
of several specialist code reviewers. Check whether each reviewer actually
addressed their scope, or gave a vague/incomplete answer. List any gaps."""
    combined = "\n\n".join(f"=== {k} ===\n{v}" for k, v in findings.items())
    validation = run_agent(validator_prompt, combined)

    return findings, validation

if __name__ == "__main__":
    diff = Path("sample.diff").read_text()
    findings, validation = review_diff(diff)
    for name, output in findings.items():
        print(f"\n## {name}\n{output}")
    print(f"\n## Validation\n{validation}")