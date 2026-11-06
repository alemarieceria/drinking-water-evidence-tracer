# Evidence review skill implementation plan

Approved scope: a small, read-only review of PR behavior claims. Do not change
extraction behavior, call a live model, approve evidence, or merge a PR.
User requested direct execution without another brainstorming or approval round.

## Files and responsibilities

- `.agents/skills/evidence-review/SKILL.md`: review procedure and claim report.
- `AGENTS.md`: invoke the review before marking a PR ready.
- `.agents/skills/README.md`: distinguish the project skill from upstream skills.
- `docs/project-map.md`: identify the contributor tool, separate from app behavior.

## Task 1: Create and validate the skill

1. Use a fresh-context baseline review of committed `feat/page-extraction` versus
   its main base; retain the observed report outside the repository.
2. Write the minimum skill: pin the revision, compare claims with diff, tests,
   proposal and map; classify each claim with file references and missing evidence.
3. Add the AGENTS rule and update discovery documentation. No proposal feature or
   acceptance criterion changes: this is contributor tooling only.
4. Validate frontmatter with skill-creator's `quick_validate.py`.
5. Apply the skill in a fresh context to the same pinned feature snapshot. Check
   labels, citations, TestModel/live/human evidence boundaries and read-only scope.
   Keep the behavioral test report in the PR, not a new documentation subsystem.
6. Review the focused diff independently. Run `uv run ruff check`, `uv run mypy`,
   and `uv run pytest` in the main-based skill worktree; all must pass.

## Task 2: Publish for owner review

1. Commit with a Conventional Commit message; push only the new skill branch.
2. Look up the feature PR again and use its link if available, otherwise identify
   the reviewed branch and full commit explicitly.
3. Open a PR targeting main using the repository template, with claim-review
   findings, actual local results and limits. Leave owner review unchecked.
4. Run `gh pr checks --watch` for the latest revision, report CI, and mark ready
   only after it passes. Do not merge or touch the original checkout's files.
