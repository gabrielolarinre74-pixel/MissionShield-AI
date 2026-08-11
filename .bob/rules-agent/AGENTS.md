# Project Coding Rules (Non-Obvious Only)

- The only source file is [`test_watsonx.py`](../../test_watsonx.py) — there are no modules, packages, or subdirectories to import from.
- Use `.venv\Scripts\python.exe` to run the script; the global Python may not have the required packages.
- New required env vars must be added to the `required_values` dict (lines 19–24 of `test_watsonx.py`) — there is no central config class or settings module.
- `ModelInference.chat()` returns an OpenAI-compatible dict; extract content with `response["choices"][0]["message"]["content"]`.
- No linter or formatter is configured — follow the existing style (4-space indent, blank lines between logical sections, inline comments above each block).
