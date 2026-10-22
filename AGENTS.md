
# Instructions for coding agents

Drinking Water Evidence Tracer is a research tool that helps environmental researchers trace drinking water test results for Zone I1 (Red Hill Housing) following the November 2021 jet fuel release. It connects the Navy’s Stage 4 laboratory, validation, and review reports to show what was tested, what was detected, and where each result came from. Researchers can identify missing information or differences in the Navy’s summary, verify results against source pages, and export reviewed evidence for further research.

## Layout
- app/main.py: routes and the page. No business rules.
- app/agent.py: the Pydantic AI agent and output model.
- app/rules.py: rules in plain Python. No FastAPI,
  no LLM client.

## Commands
```bash
uv run fastapi dev app/main.py   # run the app
uv run ruff check                # lint
uv run mypy                      # check types
uv run pytest                    # run the tests
```

## Rules
- Tests never call a real model. Use TestModel with
  override_allow_model_requests(False).
- Read LLM_API_TOKEN and LLM_API_GATEWAY from the
  environment. Never write a key outside .env.
- Run ruff, mypy, and pytest after every change and
  include their output. Never report done while one
  fails.
- Never weaken a check: no raised max-complexity, no
  # noqa or # type: ignore, no skipped tests.
