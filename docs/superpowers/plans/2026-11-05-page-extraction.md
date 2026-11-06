# One-page extraction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The owner chooses the execution method after reviewing this plan.

**Goal:** Read one archived results page and its definitions, extract draft environmental results, and show them beside the text with an inspectable local run record.

**Architecture:** Keep archive lookup, PDF reading, model calls, evidence rules, run-file storage, and HTTP presentation separate. Introduce one orchestration module to connect them; the existing demonstration remains labeled and available. Tests inject temporary archives and TestModel; only an explicitly invoked experiment uses the live model.

**Tech stack:** Python 3.14, existing FastAPI/Pydantic AI dependencies, pdfplumber 0.11.10 with pdfminer.six 20260107. Preserve the existing lockfile versions when adding the PDF dependency.

**Spec:** Read [the extraction design](../specs/2026-10-29-page-extraction-design.md), [proposal sections 10 and 19](../../proposal.md#10-llm-role), and [AGENTS.md](../../../AGENTS.md) before executing.

## Global constraints

- All results stay unconfirmed. A row count or valid model response does not establish correctness or completeness.
- Preserve result text, qualifiers, units, and decimal precision. Missing fields stay missing. Never turn a nondetect into a measured value.
- Extract environmental analyte results, not QC measurements, surrogate recoveries, or headings. Uncertain boundaries produce an unclear page with no displayed result rows.
- Keep rows attached to their sample, document, and PDF page, in source order. No search, filter, or sort controls.
- No PDF upload/viewer, RAG, database, cross-checking, inventory updates, review decisions, export, or full UI redesign.
- Tests never call a real model: use TestModel with `override_allow_model_requests(False)`; tests need neither the Shared Drive nor a neighboring checkout.
- Read credentials from `LLM_API_TOKEN` and `LLM_API_GATEWAY`; never expose them in the page, errors, logs, fixtures, or run files. Do not inspect or change the owner's `.env`.
- Before implementation, start a feature branch from latest main. Keep each failing-test commit and its fix on that branch. After each implementation task, run `uv run ruff check`, `uv run mypy`, and `uv run pytest`; report actual output and never weaken a check.

## Proposed operational limits

These are planning choices for owner review, not existing application settings.
Use at most **60,000 combined extracted characters** from the two pages and
**12,000 output tokens** per model request. Allow **one output-validation retry**,
at most **two model requests** per attempt, **zero SDK transport retries**,
a **30-second SDK network timeout**, and a **60-second total model-run deadline**.
No automatic retry follows a network error or the user submitting again.

Require `LLM_MODEL` with no default or fallback model. Use the configured gateway's
OpenAI-compatible Chat Completions endpoint and tool-based structured output;
compatibility must be checked in the live experiment. Keep temperature unset to
avoid assuming model support; record all settings actually supplied. Gateway URLs
must be HTTP(S), without embedded credentials, query parameters, or fragments.
The gateway may not disclose a fixed model revision; record its returned model
identifier when available and do not promise identical model outputs on rerun.

## File map and interfaces

All names below are proposed files until their task is implemented.

| File | One responsibility |
| --- | --- |
| `app/models.py` | Shared request, response, extraction, and run-record data contracts. Move existing schemas here unchanged so `agent.py` can focus on model extraction. |
| `app/pages.py` | Read the two requested PDF pages using the fixed library; no FastAPI or model client. |
| `app/agent.py` | Prompt, bounded Pydantic AI calls, configuration, and captured model messages. |
| `app/rules.py` | Existing numeric comparison plus plain-Python result interpretation and source-reference checks. |
| `app/runs.py` | Atomic local JSON run-file writes and reads; no FastAPI or model calls. |
| `app/extraction.py` | Orchestrate lookup, reading, extraction, rules, and persistence; no FastAPI. |
| `app/main.py` | Existing demo plus extraction routes and dependency wiring. |
| `app/extraction_page.html`, `app/static/extraction.js` | Extraction form, progress, source text, result table, and row details. |
| `app/evaluation.py`, `scripts/evaluate_extraction.py` | Pure field-level scoring, and a separate explicit live-experiment entry point, respectively. |

Update AGENTS.md Layout when these responsibilities actually move, in the same
implementation task. Update the project map as capabilities become implemented;
do not label planned files as working now.

- `ExtractionRequest`: `doc_id` matching `DOC-` plus four digits; strict positive integer `results_page` and `definitions_page`. These are PDF page numbers, never filesystem paths or URLs.
- `PagePair` in `pages.py`: original texts and page numbers, `doc_id`, source URL/title, verified PDF SHA-256, pdfplumber/pdfminer versions, and exact extraction options. Allow both requested numbers to name the same page.
- `ExtractedRow`: nonempty/non-whitespace `sample_id`, `analyte`, `result_as_written`, and `source_excerpt`; required `source_line` (1-based results-text line); nullable strings `lab_sample_id`, `method`, `qualifier`, `reporting_limit`, `mdl`, `units`, `dilution`, `analysis_date`. Reject blank required strings without trimming or changing stored result/excerpt text. Strings preserve original decimal spelling. Do not invent absent metadata.
- `PageExtraction`: `status: Literal["extracted", "unclear"]`, `reason: str | None`, `rows: list[ExtractedRow]`. Extracted requires at least one row and no reason; unclear requires a reason and no rows.
- `DraftRow`: ExtractedRow plus server-owned `doc_id`, `page_number`, `row_number`, `value: Decimal | None`, `is_nondetect: bool`, and `review_status: Literal["unconfirmed"]`. The model never assigns provenance or review status.
- `AgentAttempt`: optional validated PageExtraction, captured JSON-safe model messages (including invalid output if received), requested/returned model names, usage, and optional safe error code. Never include raw transport exception strings or headers.
- `ExtractionResponse`: original request, optional `run_id`, `status: Literal["success", "unclear", "error"]`, safe `message`/`error_code`, optional current PagePair text/provenance excluding local paths, rows, and `total_rows == len(rows)`. Unclear/error responses always have zero rows.
- `RunRecord`: schema version, `run_id: UUID`, UTC start/end times, request, status (`running` or a response status), available page provenance/text, full prompt plus version/hash, public model configuration and dependency versions, AgentAttempt, interpreted rows, and safe error details. Unknown/unread document fields remain null rather than fabricated.

## Review focus

1. A PDF changes during reading: reject it and do not call the model (Task 1).
2. A blank MDL or a margin tab becomes a number: preserve the raw text and check field handling without inferring missing values (Tasks 1-3).
3. A provider fails after returning malformed output, or run storage fails: retain available evidence and show no successful/partial table (Tasks 3-4).
4. A failed or overlapping submission leaves old rows looking current: clear results and prevent stale responses from replacing the active attempt (Task 5).
5. A fixture was never reviewed or changes after review: refuse live scoring before making a model request (Task 6).

## Task 1: Reproducible page text and draft fixtures

**Files:** create `app/pages.py`, `tests/test_pages.py`, `tests/fixtures/extraction/.gitattributes`, and `tests/fixtures/extraction/{DOC-0033-p6,DOC-0003-p7}/`; modify `pyproject.toml`, `uv.lock`, AGENTS.md Layout, and the project map.

**Interfaces:** consume `ArchivedDocument` and `file_sha256(Path) -> str` from archive.py. Produce `read_pages(document: ArchivedDocument, results_page: int, definitions_page: int) -> PagePair` and `PageReadError` with a safe code/message.

- [ ] **1. Write failing tests** named `test_reads_both_pages`, `test_accepts_same_page_twice`, `test_rejects_out_of_range_or_unreadable_pdf`, and `test_rejects_changed_file_before_and_after_read`. Use a tiny valid PDF generated in a temporary directory by a test helper, not a committed binary or the archive. Assert a known line is read from each requested page; page zero/out-of-range fail; fingerprint mismatch prevents extraction; a simulated mid-read change fails.

```python
# The test's document fixture has "Results page" and "Definitions page" text.
pages = read_pages(document, 1, 2)
assert "Results page" in pages.results_text
assert "Definitions page" in pages.definitions_text
```
- [ ] **2. Run** `uv run pytest tests/test_pages.py -v`; confirm failure because the reader is absent, then commit the failing tests (`test: specify archived page reading`).
- [ ] **3. Implement** the reader with `pdfplumber.open`, unchanged page text from `extract_text(layout=True)`, and default `x_tolerance=3`, `y_tolerance=3`, `x_density=7.25`, `y_density=13`. Record these options. Check SHA-256 against the catalog before and after reading; never crop or strip trailing numbers. Reject empty text, encryption failures, malformed PDFs, or bad page numbers with safe messages. Add `pdfplumber==0.11.10` using uv; confirm locked pdfminer.six is 20260107.
- [ ] **4. Prepare draft fixtures** only from the verified archive PDFs. Each folder contains `page.txt`, `definitions.txt`, `source.json`, and `expected_rows.csv`. Use the design's page numbers and PR #13's fingerprints. source.json records source URL, PDF fingerprint/pages, reader versions/options, text hashes, and review metadata. CSV columns are `sample_id,lab_sample_id,analyte,method,result_as_written,qualifier,reporting_limit,mdl,units,dilution,analysis_date`; blank cells mean missing. Write UTF-8 without BOM and with LF line endings; preserve page-text spaces. Add fixture-local .gitattributes rules `*.txt text eol=lf`, `*.csv text eol=lf`, and `*.json text eol=lf`. Hash the stored file bytes, and test there are no CR bytes, so Windows checkout cannot silently change the review reference. No source PDFs or margin-free text variants are committed.
- [ ] **5. Verify fixture boundaries** with stored-text tests: DOC-0033 has three sample sections, 21 less-than results, nine surrogate rows, and margin tabs; DOC-0003 has 35 results, `0.29` with J, `0.86`, `0.74`, 32 ND/U results, and the blank total 1,3-dichloropropene MDL. Keep both expected CSVs labeled draft with null reviewer fields. A. Ceria reviews every expected value against the PDFs; only she authorizes changing review status to reviewed, recording reviewer/time, the expected CSV's SHA-256, and a hash covering the source ID/PDF fingerprint/pages, reader versions/options, both text hashes, and CSV hash. Other tasks can proceed while this review is pending, but no live score may use draft files.
- [ ] **6. Run all three project checks**, confirm no unrelated dependency upgrades, update implemented/planned labels, and commit (`feat: read reproducible archived page text`).

## Task 2: Data contracts and plain-Python interpretation

**Files:** create `app/models.py`, `tests/test_extraction_rules.py`; modify `app/agent.py`, `app/main.py`, `app/rules.py`, AGENTS.md Layout, and the project map.

**Interfaces:** produce the contracts above; `interpret_result(result_as_written: str, qualifier: str | None) -> tuple[Decimal | None, bool]`; `prepare_rows(output: PageExtraction, pages: PagePair) -> list[DraftRow]`. Raise `UnclearExtraction` for unusable numeric text, inconsistent references, or uncertain output.

- [ ] **1. Write failing tests**, including these exact interpretation assertions:

```python
assert interpret_result("<0.020", None) == (None, True)
assert interpret_result("ND", "U") == (None, True)
assert interpret_result("0.50 U", "U") == (None, True)
assert interpret_result("0.29", "J") == (Decimal("0.29"), False)
assert interpret_result("0.27 J", "J") == (Decimal("0.27"), False)
```

Also assert `<0.020` remains spelled exactly that way, a missing MDL stays null,
UJ is nondetect, and NaN/infinity/ambiguous numeric text produces unclear output.
`test_rejects_blank_required_fields` rejects empty or whitespace-only sample IDs,
analytes, result text, and excerpts before any substring grounding check.
`test_source_references_and_order` rejects out-of-range/nonascending source lines,
duplicate row references, excerpts absent from the named line, and sample IDs
absent from the results text. This is a grounding check, not proof that fields
belong to the right sample. `test_review_and_provenance_are_server_owned` rejects
model-supplied overrides and checks every DraftRow is unconfirmed.

- [ ] **2. Run** `uv run pytest tests/test_extraction_rules.py -v`; confirm failure for the missing contracts/functions; commit the failing tests (`test: specify draft extraction interpretation`).
- [ ] **3. Implement** the contracts and rules. Move existing schemas from agent.py into models.py unchanged and update main.py imports; preserve the demo's public response. Use exact Decimal parsing for finite detections, recognize ND/less-than/U/UJ nondetects, and retain all raw strings independently of interpreted values. Require increasing source_line values rather than silently sorting a questionable result. Convert the whole output to unclear if any row fails; never return the valid subset. Do not attempt analyte matching, unit conversion, screening, or confirmation.
- [ ] **4. Run all three checks**, including existing skeleton and numeric-rule tests; update the Layout/map for the schema move; commit (`feat: interpret unconfirmed extraction rows`).

## Task 3: Bounded model extraction with captured outputs

**Files:** implement `app/agent.py`; create `tests/conftest.py`, `tests/test_extraction_agent.py`; modify `.env.example`, AGENTS.md Layout, and the project map.

**Interfaces:** `load_model_config() -> ModelConfig` reads the three LLM environment variables; the token is a SecretStr. Produce `async extract_rows(pages: PagePair, config: ModelConfig, *, model: Model | None = None) -> AgentAttempt`. An injected TestModel bypasses live client construction. ModelConfig's public representation contains no token.

- [ ] **1. Write failing tests** using a TestModel whose `custom_output_args` represents each stored fixture, plus one unclear page. In an autouse fixture, wrap all tests with `override_allow_model_requests(False)`. Assert schema-valid fixture rows retain 21/35 counts and the missing MDL, not that a live model found them. Inspect captured messages to confirm source text/definitions are user data, environmental-only instructions are separate, margin tabs remain present, and no callable evidence tools are registered. Include source text containing instructions to demonstrate prompt separation without claiming injection resistance.

```python
# Define pages/config/output pytest fixtures in conftest.py; output is a draft
# PageExtraction dictionary for the stored Weck fixture, with source references.
attempt = await extract_rows(pages, config, model=TestModel(custom_output_args=output))
assert attempt.output is not None
assert len(attempt.output.rows) == 35
assert attempt.output.rows[0].mdl is None
```
- [ ] **2. Specify failure tests:** missing/invalid model config, schema-invalid/partial output, timeout, and a mocked transport exception containing a fake token. Assert safe failure, no success rows, available received messages retained, and the token absent from public configuration/errors. Inspect mocked client/agent construction to assert two-request limit, zero SDK retries, 30-second network timeout, 60-second outer deadline, one output retry, and 12,000 output-token limit. Use a controllable timeout fake; do not wait a minute in tests.
- [ ] **3. Run** `uv run pytest tests/test_extraction_agent.py -v`; confirm missing extraction behavior, then commit the failing tests (`test: specify bounded page extraction`).
- [ ] **4. Implement** the prompt with version `page-extraction-v1`: extract every environmental row across all samples in line order; exclude clearly marked QC/surrogates; treat text as data; preserve missing values, result spellings, and qualifiers; identify margin numbers; return unclear for uncertain boundaries, unusable text, or no environmental results. Number the results-text lines in the prompt without modifying stored page.txt, and require verbatim per-line excerpts. Store the complete prompt and SHA-256.
- [ ] **5. Wire** the locked Pydantic AI API: Agent with PageExtraction output and `retries={"output": 1, "tools": 0}`, `UsageLimits(request_limit=2)`, and an outer `asyncio.timeout(60)`. Construct AsyncOpenAI with the configured base URL/token, `max_retries=0`, and `timeout=30`; pass it through OpenAIProvider to OpenAIChatModel with an explicit generic tool-output profile, not model-name-derived capabilities. Use `max_tokens=12000`; no temperature override. Close the client after the attempt. Capture model messages for both successful and failed validation; store safe failure codes rather than raw exceptions. Add `LLM_MODEL=` with an explanation and no real model choice to .env.example. Load config only on extraction, so the demo starts without credentials.
- [ ] **6. Run all three checks**, update implemented/planned map labels without claiming live accuracy, and commit (`feat: extract page rows with bounded model calls`).

## Task 4: Durable run files and the extraction service

**Files:** create `app/runs.py`, `app/extraction.py`, `tests/test_runs.py`, `tests/test_extraction_service.py`; modify `.gitignore`, AGENTS.md Layout, and the project map.

**Interfaces:** `save_run(root: Path, record: RunRecord) -> None`, `load_run(root: Path, run_id: UUID) -> RunRecord`, `RunStorageError`; `ExtractionService(archive_root: Path | None, runs_root: Path, model: Model | None = None)` with `async run(request: ExtractionRequest) -> ExtractionResponse`. None archive_root uses environment lookup inside the attempt, not during application import. Default runs_root is the repository's `runs/` directory.

- [ ] **1. Write failing tests:** run-record round trip after constructing a fresh reader; concurrent distinct UUIDs; no overwrite of earlier records; atomic replacement failure leaves the previous JSON readable. A leftover running record represents an interrupted attempt, never success. Inject a disk-write failure and assert no model call occurs when the initial record cannot be created. No path strings supplied by the browser become run filenames.

```python
# Define a valid RunRecord fixture named record in test_runs.py.
save_run(tmp_path, record)
assert load_run(tmp_path, record.run_id).model_dump() == record.model_dump()
```
- [ ] **2. Write service tests** using temporary catalogs/PDFs, stored fixture text, and TestModel. Assert success returns 21 or 35 rows, correct doc/page provenance, and a complete saved attempt. For unknown/duplicate-excluded doc ID, missing/changed PDF, out-of-range page, blank/unusable text, unavailable archive/config, model failure/timeout, unclear output, and failed final save: assert zero displayed rows, preserved request, safe message, and saved failure when storage remains writable. For 60,001 combined characters assert no model call; at 60,000 allow it. Never auto-select just the 27 version-one IDs: both development fixtures must be selectable from usable catalog rows.
- [ ] **3. Run** `uv run pytest tests/test_runs.py tests/test_extraction_service.py -v`; confirm missing behavior; commit the failing tests (`test: specify recorded extraction attempts`).
- [ ] **4. Implement** atomic UTF-8 JSON writes to `runs/<uuid>.json` through a same-directory temporary file and replace; ignore `runs/`. Write status running before catalog/config/PDF work and update it on success, unclear, or error. Save available page text before applying the character limit or calling the model. Preserve PDF fingerprints, versions/options, prompt/version/hash, public config, captured outputs/usage, and interpreted rows; do not copy source PDFs or serialize clients/secrets.
- [ ] **5. Implement** service orchestration with existing archive functions and the interfaces from Tasks 1-3. Run blocking catalog/PDF/file work in a thread from async code. Map failures to stable messages naming doc_id/pages without leaking local paths or transport errors. If the final save fails, return a storage error with no rows; the initial running record is the honest surviving artifact. Each user resubmission creates a new run. Guard tests against fake-token leakage in responses, saved files, and application logs.
- [ ] **6. Run all three checks**, update Layout/map and setup guidance, and commit (`feat: preserve local extraction run records`).

## Task 5: Page-to-model routes and inspectable draft results

**Files:** modify `app/main.py`; create `app/extraction_page.html`, `app/static/extraction.js`, `tests/test_extraction_routes.py`; update AGENTS.md Layout, the project map, and README links as needed.

**Interfaces:** `GET /extract` serves the separate page; `POST /extract` accepts ExtractionRequest and returns ExtractionResponse. `get_extraction_service() -> ExtractionService` is the overridable dependency. Mount only app/static as static assets; never expose runs, the archive, or .env.

- [ ] **1. Write failing TestClient tests** with dependency_overrides and TestModel. Assert the existing `/` and `/trace` contracts stay intact, `/extract` has labeled inputs and an explicit unconfirmed notice, a valid request reaches the injected service, and returned rows retain raw values/blank fields. Assert strict invalid input returns 422 without a model call; unknown/missing source returns 404, changed file 409, bad/unreadable page 422, configuration/storage failure 503, model failure 502, timeout 504, and unclear output 200 with status unclear and no rows. Clear dependency overrides after each test.

```python
response = client.get("/extract")
assert response.status_code == 200
assert 'name="doc_id"' in response.text
assert "unconfirmed" in response.text.lower()
```
- [ ] **2. Run** `uv run pytest tests/test_extraction_routes.py -v`; confirm absent routes, then commit the failing tests (`test: specify the extraction page contract`).
- [ ] **3. Implement** thin routes that delegate to the service and map safe codes to the HTTP statuses above. In get_extraction_service, load the repository .env with `load_dotenv(..., override=False)` before environment lookup, without printing it; dependency overrides keep tests independent of that file. Show source text beside a table with sample, analyte, result-as-written, qualifier, units, row count, and an unconfirmed label. Provide a keyboard-operable details button per row for limits, dilution, method, lab sample ID, source excerpt, doc_id, and PDF page. Represent missing fields as missing, never zero. Include definitions text in an accessible disclosure and explain that text is sent to the configured model service.
- [ ] **4. Implement** client state transitions: on submission preserve inputs, clear old rows/details, disable submit, and announce progress in an aria-live status region. Use a submission ID so a response from an earlier attempt cannot replace the current one. On unclear/error/network failure leave rows empty, preserve inputs, show a specific message, and restore submit. On success label the table "Unconfirmed model output; completeness has not been verified." Render source/model text with textContent, not innerHTML; check malicious markup remains text. Keep styles with this application page.
- [ ] **5. Verify browser behavior** using the fixture-backed TestModel service: submit both fixtures, select rows by keyboard, check visible focus/status announcements, then submit a failing request and verify no stale rows remain. Check 200% zoom, 320-CSS-pixel reflow, and an actual screen-reader session; record the browser/screen reader and exactly what was checked. An unavailable screen reader stays an unchecked manual item, never an accessibility-conformance claim. Reuse the existing planned diagram; update its status labels only if the implemented flow actually matches.
- [ ] **6. Run all three checks**, update the project map's real processing and setup requirements, and commit (`feat: inspect unconfirmed page extraction results`).

## Task 6: Explicit live experiment and field-level scoring

**Files:** create `app/evaluation.py`, `scripts/evaluate_extraction.py`, `tests/test_evaluation.py`; update AGENTS.md Layout and the project map's experiment instructions.

**Interfaces:** `score_rows(expected: Sequence[dict[str, str | None]], actual: Sequence[DraftRow]) -> ScoreReport` is pure. ScoreReport contains `field_matches: dict[str, int]`, `expected_rows: int`, `missing_rows`/`extra_rows` keys, and `order_matches: bool`. The script's async `evaluate_fixture(fixture_dir: Path, service: ExtractionService) -> ScoreReport` reads a reviewed reference and uses the same service/run records as the page.

- [ ] **1. Write failing scoring tests:** compare all eleven expected CSV fields exactly as strings, normalizing only empty CSV cells to null; `<0.020` and `<0.02` differ. Match by sample_id/analyte/method plus occurrence number, never silently deduplicate or join across samples. Missing rows count against every field's expected-row denominator; report extras separately. Assert an incorrect J, `0` in place of missing MDL, reordered rows, duplicate analytes, and a missing/extra row are visible. No overall accuracy threshold is chosen in this slice.

```python
# expected and actual fixtures contain 35 Weck rows; only the missing MDL
# was wrongly filled with "0" in actual, instead of remaining null.
report = score_rows(expected, actual)
assert report.expected_rows == 35
assert report.field_matches["mdl"] == 34
assert report.missing_rows == []
assert report.extra_rows == []
```
- [ ] **2. Write experiment-boundary tests:** absent `--live`, draft/missing review metadata, changed reviewed-input hash (including edited source metadata or expected rows), reader version/options drift, source fingerprint mismatch, or regenerated page text differing from the stored text all prevent model requests. Inject TestModel and temporary archives to check the successful script path and score output without network calls. Declined/failed extractions produce no successful score.
- [ ] **3. Run** `uv run pytest tests/test_evaluation.py -v`; confirm missing behavior; commit the failing tests (`test: specify reviewed-fixture scoring`).
- [ ] **4. Implement** pure scoring and the separate CLI: `uv run python -m scripts.evaluate_extraction --live --fixture DOC-0033-p6` (or DOC-0003-p7). Load .env only in the CLI entry point with override=False, and keep the evaluator injectable for tests. Resolve source.json against the catalog; verify reviewed-input hash, source/text/reference hashes, and reader versions/options before calling the service. No automatic live test in pytest or CI. Store `runs/<uuid>.score.json` beside the extraction record with reference-file hash, fixture identity, and field-level results. Report model identity, settings, missing/extra rows, order differences, and every field denominator; never label unreviewed values as ground truth.
- [ ] **5. Run the two live experiments only when** A. Ceria has reviewed both expected files and selected a gateway-supported LLM_MODEL. Record their actual results and failure cases in the feature PR; a configurable model name is not a model choice. If review/model access remains pending, open a draft feature PR with those checks unchecked and state what evidence remains. Do not claim fixture validation, live accuracy, or feature readiness from TestModel tests alone.
- [ ] **6. Run all three checks** and `uv sync --locked --dev`, confirm no source PDFs/secrets/run artifacts are tracked, finish the current/planned project map and proposal consistency review, and commit (`feat: score explicit extraction experiments`).

## Completion and handoff

The owner reviews this plan before implementation. During the build, keep the
expected-row review and model selection explicit; do not guess either on her
behalf. Every feature PR links the design, this plan, proposal sections 10/19,
the relevant test evidence, and any remaining manual/live checks. Push the feature
branch, open its PR, watch latest-revision CI, and leave owner review pending.
Never merge. The separate evidence-review skill is a later change and PR; it is
not part of these six tasks.

API references used for planning: [pdfplumber extraction](https://github.com/jsvine/pdfplumber#extracting-text),
[Pydantic AI testing](https://ai.pydantic.dev/testing/),
[OpenAI-compatible model configuration](https://ai.pydantic.dev/models/openai/),
and [FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
Check the installed, locked API when implementing; planning inspected Pydantic AI
2.59.0 and its retry configuration without making model requests.
