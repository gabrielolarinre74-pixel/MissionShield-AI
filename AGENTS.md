# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

**MissionShield AI** — a Python 3.14 script that connects to IBM watsonx.ai using the `ibm_watsonx_ai` SDK and sends chat messages to a Granite foundation model.

## Stack

- Python 3.14 (venv at `.venv/`)
- `ibm_watsonx_ai==1.6.1` — IBM watsonx SDK (`ModelInference`, `Credentials`)
- `python-dotenv==1.2.2` — loads secrets from `.env`
- No test framework, no linter, no build system

## Running the script

```powershell
.venv\Scripts\python.exe test_watsonx.py
```

## Required `.env` file (gitignored — never committed)

The script hard-fails with `ValueError` if any of these are missing:

```
WATSONX_APIKEY=
WATSONX_URL=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=
```

## Key patterns

- All four env vars are validated at startup before any SDK call; add new required vars to the `required_values` dict in [`test_watsonx.py`](test_watsonx.py).
- Model responses are accessed via `response["choices"][0]["message"]["content"]` — the standard OpenAI-compatible chat schema returned by `ModelInference.chat()`.
- The venv is inside the repo but `.venv/` is gitignored; install deps with `.venv\Scripts\pip install ibm_watsonx_ai python-dotenv`.
