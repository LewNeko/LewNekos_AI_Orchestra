"""
Enables:  python -m orchestrator [backend_name]
"""

import sys

from .session import interactive_chat


def main() -> None:
    backend_name = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    print(f"Running Interactive Chat with backend: {backend_name}\n")
    interactive_chat(backend_name=backend_name)


if __name__ == "__main__":
    main()
