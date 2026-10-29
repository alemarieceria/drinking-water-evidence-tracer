# One-page laboratory result extraction

**Status: proposed design; no extraction functionality is implemented by this document.**

## Intent and agreed scope

Connect a browser page to a real model so a researcher can inspect structured
result rows beside the text they supplied. This is the first extraction experiment
from [proposal section 10](../../proposal.md#10-llm-role), contributing to the
accuracy investigation in [section 19](../../proposal.md#19-next-investigation).

The owner selected candidate A and extraction of **every environmental analyte
result row on the supplied page**, including rows for multiple samples. Inputs are
pasted text, document metadata, a page number, and qualifier definitions. No RAG,
database, PDF upload, or full interface redesign is included. The arrangement in
the mockup is provisional and can change without changing the extraction contract.

Engineering choices below are the author's proposals for design approval, not
additional preferences attributed to the owner.

## Approaches considered

| Approach | Benefit | Trade-off and disposition |
| --- | --- | --- |
| A. Extract one supplied results page | Establishes the page-to-model connection and reveals extraction errors with little integration work. | No independent result cross-check; chosen by the owner. |
| B. Extract a results page and its Detection Summary | Exercises the existing numeric comparison rule with a meaningful safeguard. | Also needs identity and unit checks and two-page handling; deferred. |
| C. Extract validation/review findings | Turns narrative into samples, qualifiers, and reasons. | Does not exercise laboratory result extraction or automatically link findings to results; deferred. |

## Current system and limits

`app/main.py` serves a page and `/trace`, which returns the same fixed example.
`app/agent.py` defines field models but initializes no agent. `app/rules.py` compares
already-matched decimals; the route does not call it. The current models assume
information such as location and collection date that a single results page may
not supply. The extraction response must not invent these fields to fit that model.

This slice does not satisfy the proposal's three end-to-end acceptance criteria.
There is no summary comparison, finding-to-result matching, screening-level check,
inventory update, confirmation, correction, saved evidence set, or evidence export.
No health or regulatory conclusions are produced. Five-format accuracy remains
an investigation, not a claim established by these two examples.

## Proposed interaction

1. Open a separately labeled **Page extraction experiment** at `GET /extract`.
   The existing `/` and `/trace` remain explicitly labeled demonstrations.
2. Enter a source identifier, document title, and a one-based PDF page number;
   optionally add printed-page label, batch, laboratory, report level, revision,
   and a source-version description. Unknown optional metadata stays blank.
3. Paste one complete, text-readable results page, including its headings. Supply
   qualifier definitions as code/description pairs, or explicitly leave them empty.
   Missing definitions are disclosed; the model must not invent their meaning.
4. Select **Extract page**. Show progress, disable duplicate submission in this
   page, and keep the submitted input available. Browser text explains that the
   supplied content goes to the configured model gateway and a local run record.
5. Show the returned rows beside a read-only snapshot of the submitted text.
   Each row includes sample IDs and citation, so two samples' results do not look
   interchangeable. Show **Unconfirmed**, missing fields, and ambiguity notes.
6. Show a row count labeled **rows returned**, not a guarantee of completeness.
   The researcher can inspect and rerun with revised input; each submission gets
   a new run ID. There are no confirm/correct/flag or evidence-export controls.

Clear the previous displayed output when a new submission begins, or retain it
only in an explicitly labeled previous-run area. An error must not make old output
look like the response to edited input. Retrying is always a deliberate submission.
Use labeled controls, keyboard access, visible focus, announced status messages,
readable narrow-width layouts, and the project contrast conventions. Check actual
keyboard, zoom, and screen-reader behavior before making accessibility claims.

## Extraction and response contract

`POST /extract` accepts page context rather than a sample/analyte search. Use a
dedicated extraction request/response; do not change the existing trace contract.
Return a server-generated run ID, processing outcome, page classification, a list
of draft rows, and page-level issues. Include the submitted source context and
text snapshot, so output always refers to the input actually processed.

The model classifies the input as `sample_results`, `other`, or `unclear` and
extracts environmental analyte rows only. Detection summaries, QC sample results,
surrogate percent recoveries, narratives, headings, and footers are not additional
environmental results. Preserve page order and repeated analytes belonging to
different samples; do not deduplicate or infer unseen rows from adjacent pages.

Classification boundary: a page with identifiable environmental-results blocks
and clearly separate QC, surrogate, or narrative sections is `sample_results`;
exclude the other sections. An uncertain field within an identifiable results
block stays a nullable, flagged row. Use whole-page `unclear` only when the page
type or section boundaries cannot be established well enough to distinguish
environmental results from excluded material. In that case, preserve tentative
model output in the run record but return no successful result list. These are
the author's proposed defaults, including pages with multiple sample blocks.

For each row, extract these source observations:

- Field sample ID, lab sample ID, analyte name, and method.
- Exact result-cell text; any separate qualifier-cell text; numeric value token
  if visibly present; units as written; reporting limit and detection limit as
  written, including the source labels such as RL/MRL and MDL.
- Dilution and analysis date when present, and a short verbatim row excerpt.
- `unclear` and specific field-level issues where values or context are missing,
  illegible in the supplied text, or ambiguous. Nullable fields remain nullable.

Treat numeric observations as decimal strings, not binary floating-point values.
Missing values are null rather than zero, guessed identifiers, or empty successes.
An absent MDL on one row must not be copied from its neighbors. Preserve original
precision in raw fields even when a parsed `Decimal` has the same numeric value.
An absent qualifier stays null; it must not be inferred merely because a value is
below the reporting limit. Qualifier definitions provide context, not extra rows.

The server attaches citation metadata and page number from the submitted context;
the model cannot replace them. The citation is **user supplied**, not verified
against an uploaded PDF. A pasted-text digest identifies this input version; it
does not establish the source PDF's identity or original page layout.

Plain Python applies the proposal's nondetect predicate (`<`, `ND`, or U qualifier)
after extraction. A nondetect has a null measured concentration: `<0.020` does not
mean a detected value of `0.020`. Its reported threshold text and explicit MDL/RL
remain available separately. If no MDL is supplied, the detection limit stays null;
do not substitute the reporting limit. This is limited interpretation of observed
fields, not unit conversion, analyte matching, cross-checking, or final flagging.

The server sets every row's review status to `unconfirmed`; model output cannot
confirm it. A schema-valid output is still a model extraction, not verified
evidence. Preserve ambiguity and do not use model confidence as a review decision.

## Model execution and boundaries

Build on the locked FastAPI/Pydantic AI stack, with no additional frontend framework.
Use a structured-output agent without application tools, retrieval, browsing,
filesystem access, or conversation history between runs. Treat page text and
qualifier descriptions as untrusted source content, never as executable instructions.

Read `LLM_API_TOKEN` and `LLM_API_GATEWAY` on the server. Proposed additional config:
`LLM_MODEL` explicitly names the gateway model; no particular model, price, or
gateway capability has been agreed. Require it before a live extraction, without
requiring credentials at import or when loading demonstration pages or tests.
Verify structured-output compatibility against the installed package and actual
gateway before selecting provider-specific options; never silently fall back to
an unrelated endpoint or model.

Proposed initial operating limits: 64 KiB UTF-8 request body, 40,000 characters of
page text, 200 returned rows, 16,384 output tokens per model request, and a 90-second
overall run deadline. Metadata and qualifier definitions count toward the body
limit. Reject oversize input before a model call; do not truncate a page silently.
Allow at most one output-repair retry, two model requests total, and no automatic
transport retries. A provider output cap is distinct from usage accounting;
post-response accounting is not a prepaid spending cap. Record the actual limits.

The workbench targets one local user, with at most one extraction in progress;
reject an overlapping request rather than queue it. This is not a public, multiuser
deployment design. A browser disconnect may leave a bounded server run completing;
never resubmit automatically or claim the provider request was canceled.

## Local run records, not an evidence database

Use append-only run directories under ignored `data/extraction-runs/<run-id>/`.
Generate IDs on the server and never construct paths from source names. Preserve
the accepted input before making a model request; if that write fails, do not call
the model. Finish each record atomically as success, unsupported, unclear, or
failed. Leave interrupted attempts recognizable after a crash rather than silently
reusing an old output. Use a new directory for every attempt.

Preserve submitted text and its SHA-256, metadata and qualifier definitions, exact
versioned prompt, schema version, application revision when available, model name
and returned version/ID when exposed, nonsecret settings and limits, timestamps,
model response messages available through the SDK, parsed output, issues, usage
when available, and sanitized failure category. No review decisions exist in this
slice. Never serialize API keys, authorization headers, environment dumps, client
objects, or unsanitized provider exceptions into files, logs, or browser responses.

Run files survive restart for developer inspection but are not ingested as
confirmed results. There is no history/reopen UI, retention scheduler, or download
of evidence. Records remain until deliberately removed by the local owner. Browser
reloading does not restore the previous result. Document the run location and this
limit in setup instructions; no database is needed.

## Outcomes and failures

| Condition | Expected behavior |
| --- | --- |
| Valid sample-results extraction | Display returned rows and issues as unconfirmed; persist run. |
| Supported page with zero returned rows | Show an explicit empty result needing inspection, not “no detections.” |
| Other page type | Show unsupported page type with no environmental rows; persist outcome. |
| Unclear page type or uncertain section boundaries | Show why it needs inspection; preserve tentative output only in the run record, not as a successful result list. |
| Missing/invalid input or excessive size | Explain the field/size problem; no model call. |
| Missing model config | Explain configuration is unavailable; no credentials or dummy success returned. |
| Provider, timeout, retry, schema, or output-limit failure | Show a bounded, sanitized error and run ID when available; no partial rows as success. |
| Run-record finalization fails | Do not report a fully saved success; show a persistence failure and retain the recoverable input record. |

Validation cannot prove that all rows were found or that a sample ID was attached
correctly. Comparing source text and hand-checked fixtures is required. Do not
automatically feed unconfirmed rows into the demonstration's inventory or exports.

## Components and responsibilities

| Component | Proposed responsibility and boundary |
| --- | --- |
| `app/main.py` | HTTP validation, page/response delivery, and HTTP error mapping. |
| `app/agent.py` | Extraction input/output models, prompt, and lazily configured model call; no storage decisions. |
| `app/rules.py` | Pure-Python nondetect/value interpretation; existing numeric cross-check remains separate and unused by this slice. |
| `app/extraction.py` (new) | Coordinates input snapshot, one bounded agent run, interpretation, and run completion. Needed to keep that orchestration out of routes. |
| `app/run_records.py` (new) | Writes run files and exposes clear storage failures, without model calls or evidence rules. |

Keep browser styles and scripts in application code. The builder may split page
content into a focused module if two pages make the route module difficult to
understand; update AGENTS.md and the project map if responsibilities move. Further
module splits require an actual responsibility conflict, not anticipated scale.

## Representative inputs and verification

The owner supplied the reports directory in a neighboring checkout. Do not depend
on its absolute path in tests or CI, and do not read its `v1/` directory. During
implementation, prepare versioned page-text fixtures, source manifests, and
hand-checked expected rows under `tests/fixtures/extraction/`. Record how text was
obtained and the tool/version/settings. Keep the original PDFs unchanged; do not
copy entire reports into the repository merely to test the pasted-text boundary.

| Fixture | Expected behavior and purpose |
| --- | --- |
| `pub_00002948.pdf`, PDF/printed p. 6; definitions p. 3 | 21 environmental rows: seven each for `220115-I1-AT01`, `220115-I1-FT04`, and `220115-I1-FT03`. Preserve less-than values and changing limits; exclude nine surrogate recovery rows. |
| `2022-01-24-flushing-zone-i1-lab-reports-stage-2-data-release.pdf`, PDF p. 7; definitions p. 16 | 35 environmental rows for field sample `20220104-A1-ZT03`, lab sample `2A05051-02`: bromodichloromethane `0.29` with separate `J`, bromoform `0.86`, dibromochloromethane `0.74`, and 32 ND/U rows. Preserve a missing MDL for `1,3-Dichloropropene, Total`. |

Source file SHA-256 values:

- `pub_00002948.pdf`: `0fbfa2d7ce9d5c494e1b303e83c8561849eb3b5b8a976111bb0bd1125b85fb95`
- Stage 2 combined PDF: `571653ce6b4a13c2f314f81d50bbc314d663786f126d6942ec36175dd3bbdc01`

The first is a Zone I1 development example from batch 810-12365-1, outside the
proposal's named version-one set. The second is a **development-only Stage 2,
non-I1 example**. Neither changes the application evidence scope or adds a batch
to the version-one corpus. Preserve the source filenames exactly; do not silently
translate their identifiers to the proposal's shorter publication naming style.

Offline tests use `TestModel` with `override_allow_model_requests(False)`. Use a
controlled offline model only when needed to simulate malformed responses and
retries; never permit real provider requests in tests. Exercise request-to-response
handling, sample boundaries, nulls, separate qualifiers, nondetect interpretation,
unsupported/empty pages, sanitization, limits, and storage failures. Check model
inputs contain the supplied context, rather than merely replaying canned output.

Offline wiring tests do not establish model accuracy. A separately invoked manual
experiment, outside pytest and CI, can compare real model outputs against the
hand-checked rows after the owner chooses an accessible model. Record field-level
accuracy, missed/extra rows, sample assignment errors, run settings, and failures.
Report the results without a fabricated accuracy threshold or five-format claim.

## Completion and choices left to implementation

Completion requires the workbench's happy path and failure states to function,
local run provenance to be inspectable, offline behavior tests and the three project
checks to pass, and documentation to distinguish implemented, placeholder, and
planned behavior. Run an explicit live smoke experiment only when the model is
configured; if it is not, report that limitation rather than claiming a live pass.

The builder may choose small function names, page layout refinements, error
wording, and serialization mechanics within this contract. The exact model name
and gateway-specific capabilities remain deployment configuration, not assumed
design facts. Changing limits, model settings, or prompt/schema versions must be
visible in run records. A later interface redesign can replace the presentation
while retaining this extraction boundary.

Reference documentation checked while drafting: Pydantic AI
[structured outputs](https://github.com/pydantic/pydantic-ai/blob/main/docs/output.md),
[offline testing](https://github.com/pydantic/pydantic-ai/blob/main/docs/testing.md),
and [provider configuration](https://github.com/pydantic/pydantic-ai/blob/main/docs/models/openai.md).
The implementation must verify syntax against `uv.lock`; these references do not
justify changing the locked versions as part of the design-only change.
