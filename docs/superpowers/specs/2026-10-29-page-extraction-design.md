# One-page laboratory result extraction

**Proposed, not implemented.** Build a small page that reads one archived report
page, sends its text to a model, and shows draft results beside that text. The
final layout can change.

## At a glance

![Planned flow: choose one archived page, extract its result rows, then inspect an unconfirmed table in page order; keep a local run record and explain failures.](../../assets/project/planned-page-extraction-flow.svg)

*All steps and connections are planned. Unconfirmed means a person still needs
to check the result.* [Full-size diagram](../../assets/project/planned-page-extraction-flow.svg)
· [Editable source](../../assets/project/planned-page-extraction-flow.excalidraw)

**Text equivalent:** You choose a document by its archive ID and a page number.
The app reads that page's text from the archived PDF. The model extracts
environmental result rows. You inspect the draft table in page order. The app
keeps a local record of the attempt. If extraction fails or the page is too
unclear, it explains the problem without presenting a successful result list.

## What you will do

| Step | What happens |
| --- | --- |
| Choose a page | Open the extraction page. Enter an archive document ID (such as `DOC-0033`), the PDF page number of a results page, and the PDF page number of its qualifier definitions. PDF page numbers can differ from the page labels printed in a report. |
| Read the text | The app finds the PDF through the archive catalog, checks its fingerprint, and pulls the text of both pages with one fixed PDF library. Nothing is uploaded, and no PDF is displayed. |
| Extract | Select **Extract page**. The app sends the page text and definitions to the configured model and shows progress. |
| Inspect | See every returned environmental analyte row in page order, with the total count, beside the page text. Select a row for its limits, qualifier, sample IDs, and source excerpt. |

For example, `DOC-0033` page 6 should return **21 analyte rows across three
samples**, excluding nine surrogate recovery rows. All results stay unconfirmed.

## Important boundaries

- Extract environmental analyte results, not QC measurements, surrogate recoveries,
  or headings. Keep each row attached to its own sample, document, and page.
- Preserve result text, qualifiers, units, and decimal precision. Missing fields
  stay missing. A nondetect such as `<0.020` is not a measured value of `0.020`.
- Ignore text that is not part of the table. Eurofins pages have page-tab numbers
  in the right margin, and extracted text places them at the ends of rows: in
  `Perylene-d12 96 70 - 130 ... 1    10`, the dilution factor is 1 and 10 is a tab.
- Clearly separated QC/surrogate sections can be excluded. If section boundaries
  are uncertain, report an unclear page instead of claiming a successful extraction.
- Errors preserve the user's input and never make old or partial output look
  current. A returned row count does not prove extraction is complete or correct.

## Choices proposed for your review

| Choice | Why |
| --- | --- |
| Choose pages from the archive instead of pasting text | Copied text differs by tool (Acrobat, a browser, `pdftotext`), so pasted input cannot be reproduced. A fingerprinted file and one PDF library give the same text on every run. |
| Rows in page order; no search, filter, or sort yet | This slice tests whether extraction is accurate. Table controls belong in a later slice, once there are enough rows to need them. |
| Separate extraction page; existing demo stays labeled | Makes the real experiment distinct from the fixed demonstration response. |
| Local run files, no database or history screen | Preserve the document ID, page numbers, file fingerprint, PDF library version, extracted text, prompt/model/settings, outputs, and errors so attempts can be investigated after restart. These are not confirmed evidence sets. |
| Model extracts; Python interprets; people confirm later | Keep evidence rules separate from model calls and presentation. Page text is data, not instructions. |
| Bounded requests; explicit server-side model configuration | Avoid unlimited retries and hidden model choices. Credentials never reach browser output or run records. |

Exact request limits, file formats, function names, the PDF library, and module
splits belong in the implementation plan. Document them there before building;
update AGENTS.md and the project map if responsibilities move. No particular model
is selected yet. Live runs need the Shared Drive (`ARCHIVE_ROOT`); tests do not.

**Out of scope:** PDF upload/viewing, search/filter/sort, RAG, a database,
cross-checks, summary matching, inventory updates, confirmation/correction,
evidence export, and a full UI redesign. No claim of extraction accuracy across
all five laboratory formats is made.

## How we will check it

| Development input | What it checks |
| --- | --- |
| `DOC-0033` (`pub_002948.pdf`; Eurofins South Bend, batch 810-12365-1), PDF p. 6; definitions p. 3 | 21 nondetect rows across three samples, less-than values, limits that differ by sample, nine surrogate rows excluded, and margin tab numbers not read as values. |
| `DOC-0003` (Laboratory Reports for Zone I1 Stage 2, 24 January 2022; Weck report 2A05051), PDF p. 7; definitions p. 16 | 35 rows for one sample: ordinary detections, a J qualifier, ND/U results, and a missing MDL that must not be invented. |

The archive catalog records both PDFs' source URLs and SHA-256 fingerprints.
These are development fixtures only: neither expands the proposal's version-one
corpus. `DOC-0003` page 7 is also outside Zone I1: its sample, 20220104-A1-ZT03,
is from Zone A1, although the Navy filed it with the I1 release.

Each fixture is stored in the repository as its extracted page text (margin
numbers included), with the PDF library version that produced it, and a
hand-checked expected-rows file. That file lists every row's sample ID, analyte,
result as written, qualifier, reporting limit (RL or MRL), MDL, and units. Tests
use these stored files, never a neighboring checkout or the Shared Drive archive.

Offline tests block real model requests and check field handling, sample
boundaries, failures, and local run records. Check keyboard use, focus, zoom,
narrow layouts, and screen-reader behavior. Run Ruff, mypy, and pytest.

A separately invoked live experiment reads the fixture pages from the archive,
runs the configured model, and compares each returned row with the expected-rows
file field by field. It reports matches per field, missing rows, and extra rows.
Offline tests alone cannot establish extraction accuracy.

## Why this approach, and what comes next

We chose **one-page extraction** to establish the page-to-model connection first.
Two-page cross-checking adds matching work; validation-narrative extraction tests
a different problem. Both remain later options, as do search, filter, and sort.

After design review, write and review the implementation plan, then build and
verify the feature. The [proposal's sections 10 and 19](../../proposal.md#10-llm-role)
define the project scope; this document describes only this change.
