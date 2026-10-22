"""HTTP routes and a basic page backed by a fixed demonstration response."""

from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.agent import (
    DocumentMetadata,
    InventoryItem,
    Location,
    Result,
    Sample,
    SourcePage,
    TraceRequest,
    TraceResponse,
    TraceRow,
)

app = FastAPI(title="Drinking Water Evidence Tracer")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Drinking Water Evidence Tracer</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f6f8; color: #1e293b;
           font: 16px/1.5 system-ui, sans-serif; }
    main { max-width: 1100px; margin: auto; padding: 24px; }
    h1 { margin-bottom: 8px; font-size: 1.8rem; }
    h2 { margin-top: 0; font-size: 1.1rem; }
    section { padding: 20px; border: 1px solid #cbd5e1; border-radius: 8px;
              background: white; margin-top: 20px; min-width: 0; }
    form, .actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }
    label { display: grid; gap: 4px; flex: 1; }
    input, button { padding: 10px; font: inherit; border: 1px solid #94a3b8;
                    border-radius: 4px; }
    button { background: #e0edff; color: #1e293b; cursor: pointer; }
    button:disabled { opacity: .55; cursor: default; }
    .columns { display: grid; grid-template-columns: 3fr 2fr; gap: 20px; }
    .table-scroll { overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; font-size: .9rem; }
    th, td { padding: 10px 8px; text-align: left; border-bottom: 1px solid #e2e8f0; }
    .example-row { background: #fff8df; }
    .notice { padding: 12px; background: #fff8df; border: 1px solid #e6c76b;
              border-radius: 4px; }
    .muted { color: #475569; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f8;
          padding: 12px; font-size: .85rem; }
    @media (max-width: 800px) { .columns { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>Drinking Water Evidence Tracer</h1>
  <p class="notice">Skeleton demonstration: every search returns the same fixed
    HT03 lead example. Values and flags are placeholders for display.</p>
  <section aria-labelledby="search-heading">
    <h2 id="search-heading">1. Find a sample or analyte</h2>
    <form id="trace-form" action="/trace" method="post">
      <label>Sample ID
        <input name="sample_id" value="220113-I1-HT03" placeholder="Sample ID">
      </label>
      <label>Analyte
        <input name="analyte" value="Lead" placeholder="Analyte name">
      </label>
      <button id="submit-button" type="submit">Trace results</button>
    </form>
    <p id="request-status" role="status" aria-live="polite">Submit to display the example.</p>
    <p id="sample-details" class="muted">Sample details will appear here.</p>
  </section>
  <div class="columns">
    <div>
      <section aria-labelledby="inventory-heading">
        <h2 id="inventory-heading">2. Analyte inventory</h2>
        <p class="muted">Detected · Estimated (J) · Nondetect · Qualified · Not requested</p>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Analyte</th><th>Method</th><th>Batch</th><th>Status</th></tr></thead>
            <tbody id="inventory-body"></tbody>
          </table>
        </div>
      </section>
      <section aria-labelledby="trace-heading">
        <h2 id="trace-heading">3. Trace: lab report → validation → Navy summary</h2>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Analyte</th><th>Lab result</th><th>Validation</th>
              <th>Summary</th><th>Status</th><th>Source</th></tr></thead>
            <tbody id="trace-body"></tbody>
          </table>
        </div>
      </section>
    </div>
    <section aria-labelledby="review-heading">
      <h2 id="review-heading">4. Review on the source page</h2>
      <p id="source-reference" class="muted">Source reference will appear here.</p>
      <pre id="source-preview">Source-page preview placeholder.</pre>
      <p id="result-details" class="muted"></p>
      <div class="actions">
        <button type="button" disabled>Confirm</button>
        <button type="button" disabled>Correct</button>
        <button type="button" disabled>Flag</button>
      </div>
      <p class="muted">Review controls and PDF viewing are not implemented.</p>
    </section>
  </div>
  <section aria-labelledby="evidence-heading">
    <h2 id="evidence-heading">5. Saved evidence sets</h2>
    <p id="evidence-status">No saved evidence sets.</p>
    <div class="actions">
      <button type="button" disabled>Save evidence set</button>
      <button type="button" disabled>Open</button>
      <button type="button" disabled>Export CSV</button>
    </div>
    <p class="muted">Saving and export are not implemented.</p>
  </section>
</main>
<script>
  function fillRows(id, rows) {
    const body = document.getElementById(id);
    body.replaceChildren();
    for (const values of rows) {
      const row = document.createElement('tr');
      row.className = 'example-row';
      for (const value of values) {
        const cell = document.createElement('td');
        cell.textContent = value ?? '—';
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
  }

  function sourceLabel(source) {
    return `${source.document.publication_id} · p. ${source.page_number}`;
  }

  function displayTrace(data) {
    const sample = data.sample;
    const location = sample.location;
    document.getElementById('sample-details').textContent =
      `${sample.field_sample_id} · ${location.location_id} · ${location.address} · ` +
      `Zone ${location.flushing_zone} · collected ${sample.collection_date} · ` +
      `${sample.batch_count} batches`;
    fillRows('inventory-body', data.inventory.map(item =>
      [item.analyte, item.method, item.batch, item.status]));
    fillRows('trace-body', data.trace.map(row =>
      [row.result.analyte, `${row.result.result_as_written} ${row.result.units}`,
       row.validation_status, row.summary_value, row.status,
       row.result.source_pages.map(sourceLabel).join('; ')]));
    document.getElementById('source-preview').textContent = data.source_preview;
    const result = data.trace[0]?.result;
    document.getElementById('source-reference').textContent = result
      ? result.source_pages.map(sourceLabel).join('; ') : 'No source reference.';
    document.getElementById('result-details').textContent = result
      ? `Reporting limit: ${result.reporting_limit ?? '—'} ${result.units} · ` +
        `Detection limit: ${result.detection_limit ?? '—'} ${result.units} · ` +
        `Review: ${result.review_status}` : '';
    document.getElementById('evidence-status').textContent = data.evidence_sets.length
      ? data.evidence_sets.map(set => set.name).join(', ') : 'No saved evidence sets.';
  }

  document.getElementById('trace-form').addEventListener('submit', async event => {
    event.preventDefault();
    const status = document.getElementById('request-status');
    const button = document.getElementById('submit-button');
    const form = new FormData(event.currentTarget);
    button.disabled = true;
    status.textContent = 'Loading placeholder response…';
    try {
      const response = await fetch('/trace', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          sample_id: form.get('sample_id') || null,
          analyte: form.get('analyte') || null
        })
      });
      if (!response.ok) throw new Error(`Request failed (${response.status}).`);
      const data = await response.json();
      displayTrace(data);
      status.textContent = data.message;
    } catch (error) {
      status.textContent = `Unable to load the example: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


@app.post("/trace", response_model=TraceResponse)
def trace(request: TraceRequest) -> TraceResponse:
    """Return the same example for every valid request, without processing it."""
    source = SourcePage(
        document=DocumentMetadata(
            publication_id="pub_002925",
            title="Example laboratory report (placeholder)",
        ),
        page_number=10,
    )
    return TraceResponse(
        message="Fixed placeholder response; your search has not been processed.",
        sample=Sample(
            field_sample_id="220113-I1-HT03",
            collection_date=date(2022, 1, 13),
            requested_analyses=["Metals"],
            batch_count=4,
            location=Location(
                location_id="I1-MADR1832",
                address="1832 Madrona Place",
                flushing_zone="I1",
            ),
        ),
        inventory=[
            InventoryItem(
                analyte="Lead",
                method="EPA 200.8",
                status="Estimated (J) — placeholder",
            )
        ],
        trace=[
            TraceRow(
                result=Result(
                    field_sample_id="220113-I1-HT03",
                    analyte="Lead",
                    method="EPA 200.8",
                    result_as_written="0.27 J",
                    value=Decimal("0.27"),
                    units="µg/L",
                    qualifier="J",
                    reporting_limit=Decimal("0.50"),
                    detection_limit=Decimal("0.088"),
                    source_pages=[source],
                ),
                validation_status="Placeholder — not reviewed",
                summary_value="0.270",
                status="Qualifier dropped — placeholder",
            )
        ],
        source_preview=(
            "Placeholder preview (not a loaded PDF)\n\n"
            "Client Sample ID: 220113-I1-HT03\n"
            "Lead    0.27 J    RL 0.50    DL 0.088 µg/L\n\n"
            "No extraction, cross-check, or review has been performed."
        ),
    )
