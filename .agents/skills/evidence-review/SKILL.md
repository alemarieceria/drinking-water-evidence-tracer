---
name: evidence-review
description: Use when reviewing a Drinking Water Evidence Tracer PR's behavior claims or checking whether its summary is supported before marking it ready for owner review.
---

# Evidence review

Review claims against evidence, read-only. This is a contributor review, not
confirmation of extracted results or approval to merge.

## Gather evidence

1. Identify the PR URL, target branch, base and head SHAs. Read its summary and
   test plan, then inspect the diff and relevant surrounding code at that head.
   For a branch without a PR, record the branch and pinned SHAs; use the PR link
   when available. Report uncommitted work separately; do not count it as PR evidence.
2. Read relevant tests and fixtures, `docs/proposal.md`, and
   `docs/project-map.md` at the same revision. The proposal defines intent; the
   map describes current behavior. A design or plan is not implementation evidence.
3. Extract each behavior claim from the summary and test plan. Split compound
   claims when their support differs. Trace the input through the changed code
   to the observable output, including relevant failure paths and limits.

Do not edit files, fix findings, switch the reviewed checkout's branch, invoke a
live model, change review metadata, post comments, approve, or merge. Read existing
check results by default. If offline checks are authorized, run them in an isolated
checkout; distinguish their exact revision and results from inspected assertions.

## Judge each claim

| Verdict | Meaning |
| --- | --- |
| supported | Implementation and relevant evidence support the claim as worded. State the tested scope. |
| partly supported | A narrower behavior is evidenced; identify the unsupported part or boundary. |
| unsupported | Evidence is absent or contradicts the claim. Distinguish missing evidence from demonstrated failure. |

Keep these evidence boundaries explicit:

- **Offline:** `TestModel` with `override_allow_model_requests(False)` checks
  protocol, validation and handling of supplied output. Rows supplied from an
  expected CSV do not show that a live model extracted them correctly. Tests read
  but not run establish coverage intent, not a passing result. CI proves only the
  checks and revision it actually ran.
- **Live accuracy:** requires recorded real-model outputs, source/prompt/model
  versions and settings, and comparison against source-checked reference rows.
  State the pages, fields and formats measured; do not generalize beyond them.
- **Human review:** inspect recorded reviewer evidence. Draft expected rows,
  an agent's verdict, and a provenance link do not establish source-PDF review or
  confirmed results. Local run storage does not establish reviewed-evidence export.

## Report

Start with the PR link (or branch), base/head SHAs, and reviewed scope. Use a table:

| Claim | Verdict | Evidence and limits | Missing evidence or correction |
| --- | --- | --- | --- |
| Offline fixture checks prove live accuracy. | unsupported | `tests/<file>.py:<line>` supplies expected rows to TestModel. | Recorded live outputs scored against source-checked references. |

Give every claim concrete file-and-line references at the reviewed head, including
relevant test assertions and proposal/map sections. Link revision-specific files
when a remote is available. Report documentation contradictions explicitly.
Finish with checks actually run (command, revision, result), checks only inspected,
and remaining live-accuracy or human-review gaps. Leave owner review pending;
supported claims do not mean the whole PR is ready or the evidence is confirmed.
