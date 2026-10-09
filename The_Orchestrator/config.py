"""
config.py
---------
Tunable limits for the agent loop. Kept separate so they can be changed
(or later loaded from env vars / a config file) without touching logic.
"""

# Max model calls allowed for ONE user request (one "turn").
MAX_STEPS = 20

# How many times the exact same tool call (same name + same args) may be
# executed within one turn. 1 means "run it once, block any repeat".
MAX_REPEATED_TOOL_CALLS = 1

# How many characters of a tool result to echo to the console.
RESULT_PREVIEW_CHARS = 200
