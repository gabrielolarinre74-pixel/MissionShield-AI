# Project Documentation Context (Non-Obvious Only)

- Despite the name `test_watsonx.py`, this is not a test file — there is no test framework; it is the sole entry-point script for the project.
- The project name "MissionShield AI" appears only in the chat prompt inside the script; it is not referenced anywhere else in the repo.
- `.gitignore` includes `node_modules/` and `.next/` — suggesting a frontend may be planned but does not yet exist.
- All credentials and configuration live exclusively in a `.env` file that is gitignored and never committed.
