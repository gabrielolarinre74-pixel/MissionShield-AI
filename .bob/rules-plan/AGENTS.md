# Project Architecture Rules (Non-Obvious Only)

- The project is currently a single flat script — no package structure, no modules, no CLI entrypoint defined in `pyproject.toml` or `setup.py`.
- Authentication is stateless per-run: `Credentials` + `ModelInference` are instantiated fresh each execution; there is no session caching.
- `.gitignore` anticipates a Next.js frontend (`node_modules/`, `.next/`) that does not yet exist — plan accordingly when adding a web layer.
- The IBM SDK (`ibm_watsonx_ai`) wraps both REST and WebSocket transports internally; `ModelInference.chat()` is the synchronous REST path.
- Python 3.14 is required (venv was created with it); avoid features or packages incompatible with 3.14.
