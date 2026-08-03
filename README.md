
A Beginners journey into making a real ai orchestration.
Minimal agent loop with a swappable model backend: run it against a
local model (Ollama) on your own hardware, or point it at Claude's
API with one flag change. No other code changes needed either way.

Built for: 16GB RAM, RTX 3050 Laptop (4GB VRAM).

```
tools.py         <- what the agent is allowed to DO (list_directory, read_file)
backends.py       <- HOW to talk to a model (Ollama or Claude), one interface
orchestrator.py   <- the agent loop: send -> maybe call a tool -> repeat
```

## 1. Install Ollama (one-time)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

(Windows/Mac: download the installer from https://ollama.com/download instead.)

## 2. Pull a model sized for your GPU

```bash
ollama pull qwen3:4b
```

Confirm it's being served:

```bash
ollama list
curl http://localhost:11434/v1/models
```

## 3. Set up the Python project

```bash
cd local-orchestrator
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Run it against your local model

```bash
python orchestrator.py ollama "List the files in the current directory, then read README.md and summarize it in one sentence."
```

What happens:
1. `orchestrator.py` sends your task + the tool list to `qwen3:4b` via Ollama.
2. The model decides it needs `list_directory`, the orchestrator runs it locally.
3. Result gets fed back to the model.
4. Model calls `read_file`, orchestrator runs it, feeds the result back.
5. Model gives a final text answer -- printed to your terminal.

Everything above runs entirely on your machine. No API calls, no data leaving your laptop.

## 5. Swap to Claude when you need stronger reasoning

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # get one at console.anthropic.com
python orchestrator.py claude "Same task, but harder -- multi-step reasoning here."
```

Same `orchestrator.py`, same `tools.py`, same task format. Only the
`backend_name` argument changed. This is the whole point of the
architecture: your agent logic never knows or cares which model answered.

## 6. Add your own tools

In `tools.py`:
1. Add a schema entry to `TOOL_SCHEMA` (name, description, parameters).
2. Write the matching Python function.
3. Register it in `TOOL_FUNCTIONS`.

The orchestrator picks it up automatically -- no changes needed there.

## Notes for your hardware specifically

- `qwen3:4b` is small enough to run mostly on your 4GB VRAM. If you
  want to try something bigger, `gemma2:9b` will split across GPU
  and system RAM -- slower, but still workable on 16GB total RAM.
- Check `ollama ps` if generation feels CPU-slow -- on laptops with
  both an Nvidia GPU and integrated AMD graphics, Ollama can
  occasionally pick the wrong device.
- `MAX_STEPS = 6` in `orchestrator.py` is a safety cap so a confused
  small model can't loop forever calling tools. Raise it once you
  trust the loop.

