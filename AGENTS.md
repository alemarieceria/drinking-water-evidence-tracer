
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

## Maintainability and human understanding

- Before meaningful work, explain the purpose, a concrete example, and where
  the change fits in plain English. Use a small diagram when it helps. Report
  progress in terms of behavior, evidence, and remaining work.
- Give each module a clear responsibility and explicit inputs, outputs, and
  assumptions. Prefer small functions and clear names. Introduce abstractions,
  dependencies, and new files only for a concrete need; explain the trade-off.
- Keep rules separate from routes, model calls, and storage, following Layout.
  Tests should check behavior and important boundaries without real model calls.
- Preserve reproducibility with `uv.lock`, documented setup, and representative
  inputs with expected outputs. Explain configuration without exposing secrets.
  When model extraction is introduced, preserve source document versions,
  prompt/model versions, settings, outputs, and review decisions; reruns may vary.
- Keep [docs/project-map.md](docs/project-map.md) accurate when structure,
  processing, capabilities, or setup changes. Label implemented, placeholder,
  and planned behavior explicitly, including connections between components.
- Keep documentation focused: the proposal defines intent, code implements
  behavior, tests verify examples, and the project map explains the current
  system. Link to existing sources instead of repeating full specifications.
- Record significant lasting choices in the project map's decision record,
  including rationale, alternatives actually considered, consequences, and the
  relevant PR. Add entries for meaningful decisions, not every commit.
- PR summaries should include a plain-English explanation, an input/output
  example when applicable, and scope or remaining limitations. Visuals are
  optional and reusable; prefer editable diagrams for processing and structure,
  and illustrations for concepts. Include a text caption and text equivalents
  for visuals, and distinguish intended workflow from implemented behavior.
- Before marking a PR ready, verify that tests pass, assumptions and limitations
  are visible, and documentation matches the change. Leave the owner's review
  pending so they can ask questions and explain the behavior in their own words.

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
- Push the branch and open a pull request targeting main with `gh pr create`.
  Use the repository's pull request template with `## Summary` and
  `## Test plan` sections. Explain what changed and why, citing the relevant
  section of `docs/proposal.md`. For maintenance changes, explain why no
  proposal feature or acceptance criterion is affected.
- Check a test-plan item only after running it successfully. Distinguish local
  results from GitHub Actions results. Leave human review items unchecked.
- After pushing, run `gh pr checks --watch` and report the result for the latest
  pull request revision. Verify that GitHub Actions passes before marking the
  pull request ready for review.
- Leave the pull request for the project owner's review of the diff and intended
  behavior. External approval is not required for this solo project.
- Never merge a pull request. The project owner performs squash and merge
  after reviewing the diff and confirming that checks pass.

GitHub's active main-branch rules require a pull request, a passing `tests` check
from GitHub Actions against the latest main, and squash merging, with no bypass
exceptions. The owner records their own review in the pull request checklist.
