# Project Documentation Context (Non-Obvious Only)

- `test_watsonx.py` at repo root is NOT a test file — it is the original IBM watsonx.ai connectivity proof. Keep it. Do not modify it.
- `backend/sanity_check.py` and `backend/endpoint_test.py` are developer utilities, not part of the test suite (`pytest` does not discover them).
- `docs/ibm-bob-development.md` is the competition evidence record for IBM Bob usage — update it after each phase.
- `missionshield-plan.md` is the live architecture document — update sub-task statuses as phases complete.
- The `.gitignore` already covers `node_modules/` and `.next/` — the Next.js frontend directory is not yet created but is anticipated.
- `backend/.env.example` lists all supported variable names with safe defaults — it is safe to commit.
- NOAA feed URLs are documented in `noaa_swpc.py` header comments — they are non-obvious and should not be guessed.
- The GOES proton feed used is `integral-protons-6-hour.json` (primary satellite). It contains 8 energy channels per timestamp.
- `>=10 MeV` is the standard space-weather S-class alert threshold channel — it is the channel most relevant for risk scoring.
