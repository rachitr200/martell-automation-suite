# Martell automation suite: working agreements

Eight small projects, one per area of the AI Automation Developer role. Read `README.md` for the map.

## Run things
- `python run_tests.py` runs every dependency-free test (the verified path). `python run_tests.py 05` runs one project.
- `01-lifecycle-engine` is a FastAPI service: `cd 01-lifecycle-engine && uv sync && uv run pytest`.
- Each project is a package under `NN-name/src/<package>`; run a module with `PYTHONPATH=NN-name/src python -m <package>.cli`.

## Rules that matter here
1. **Deterministic code owns money and access.** Never put an LLM in the payment, entitlement, or access-revocation path. LLMs classify, summarise, and draft; humans or code decide.
2. **Side effects must be idempotent.** Any handler can run twice (retry after a crash). Granting access that already exists, or revoking access already gone, is success.
3. **Fail loudly, never silently.** A dropped event, a missing batch result, or an unparseable model reply becomes a visible status (`failed`, `dead`, `error`, `unparseable`), never an empty value.
4. **Read-only first.** Tools that touch HubSpot or members recommend and export; a person applies the change. New write paths need a dry-run mode.
5. **No secrets in code or tests.** Tokens come from environment variables (see `.env.example`). Never paste real customer data into a prompt or a fixture.
6. **Every change gets a test that would have caught the bug.** Prefer plain `assert` tests so `run_tests.py` can run them.

## When a colleague asks "why didn't X happen?"
Use `/trace-customer`. Teach the method, then point to the command, so the question does not come back.
