
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

## Git workflow

- Start each new change from the latest main on a descriptive branch.
  Continue work on its existing branch when the change is already in progress.
  Preserve unrelated uncommitted work. Never commit or push directly to main.
- Keep each branch and pull request focused on one purpose.
- Use Conventional Commit messages.
- For test-driven work, keep the failing test commit and its fix on the same
  branch. All checks must pass before the pull request is ready for review.
- Run `uv run ruff check`, `uv run mypy`, and `uv run pytest` after changes,
  and report their actual results.
- Push the branch and open a pull request targeting main. Use the repository's
  pull request template with Summary and Test plan sections. Explain what
  changed, why, and the related proposal requirement when applicable.
- Check a test-plan item only after running it successfully. Distinguish local
  results from GitHub Actions results. Leave human review items unchecked.
- Verify that GitHub Actions passes for the latest pull request revision.
- Leave the pull request for the project owner's review of the diff and intended
  behavior. External approval is not required for this solo project.
  Do not merge unless explicitly instructed.
- Use squash and merge after checks and human review are complete.

GitHub's active main-branch rules require a pull request, a passing `tests` check
from GitHub Actions against the latest main, and squash merging, with no bypass
exceptions. The owner records their own review in the pull request checklist.
