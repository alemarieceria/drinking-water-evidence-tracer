"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId("extraction-form");
  const submit = byId("extract-button");
  const status = byId("status");
  let submission = 0;
  let pending = null;
  let expandedTable = false;
  let selectedResult = null;
  const displayValue = (value) => value === null || value === undefined || value === "" ? "Missing" : String(value);

  function fitTable() {
    const viewport = byId("table-viewport");
    const rows = [...byId("result-rows").rows];
    if (expandedTable || rows.length <= 5) {
      viewport.style.maxHeight = "none";
      return;
    }
    const height = viewport.querySelector("thead").getBoundingClientRect().height
      + rows.slice(0, 5).reduce((sum, row) => sum + row.getBoundingClientRect().height, 0)
      + viewport.offsetHeight - viewport.clientHeight;
    // Hidden sections have no geometry. Their next reveal/resize measures again.
    if (height > 0) viewport.style.maxHeight = `${Math.ceil(height)}px`;
  }

  for (const view of ["both", "source", "results"]) {
    byId(`view-${view}`).addEventListener("click", () => {
      byId("extraction-panels").dataset.view = view;
      byId("source-panel").hidden = view === "results";
      byId("results-panel").hidden = view === "source";
      for (const choice of ["both", "source", "results"]) {
        byId(`view-${choice}`).setAttribute("aria-pressed", String(choice === view));
      }
      fitTable();
    });
  }

  byId("table-size").addEventListener("click", () => {
    expandedTable = !expandedTable;
    byId("table-size").setAttribute("aria-expanded", String(expandedTable));
    byId("table-size").textContent = expandedTable ? "Show five rows at a time" : "Expand table";
    fitTable();
  });
  byId("back-to-row").addEventListener("click", () => selectedResult?.focus());
  window.addEventListener("resize", fitTable);
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(fitTable).observe(byId("result-rows").closest("table"));
  }

  function clearOutput() {
    expandedTable = false;
    selectedResult = null;
    byId("table-size").hidden = true;
    byId("table-size").setAttribute("aria-expanded", "false");
    byId("table-size").textContent = "Expand table";
    byId("table-viewport").style.maxHeight = "";
    byId("result-rows").replaceChildren();
    byId("details-list").replaceChildren();
    byId("rows-region").hidden = true;
    byId("row-details").hidden = true;
    byId("row-count").textContent = "No current results.";
    byId("provenance").textContent = "No current page.";
    byId("source-text").textContent = "No current results-page text.";
    byId("definitions-text").textContent = "No current definitions page.";
  }

  function showDetails(row, button) {
    selectedResult = button;
    const list = byId("details-list");
    list.replaceChildren();
    for (const other of byId("result-rows").querySelectorAll("button")) {
      other.setAttribute("aria-expanded", String(other === button));
    }
    byId("details-heading").textContent = `${row.analyte} · ${row.sample_id}`;
    const fields = [
      ["Document", row.doc_id], ["Results PDF page", row.page_number],
      ["Sample ID", row.sample_id], ["Lab sample ID", row.lab_sample_id],
      ["Method", row.method], ["Result as written", row.result_as_written],
      ["Qualifier", row.qualifier], ["Units", row.units],
      ["Reporting limit (RL/MRL)", row.reporting_limit], ["MDL", row.mdl],
      ["Dilution", row.dilution], ["Analysis date", row.analysis_date],
      ["Review", "Unconfirmed"], ["Source excerpt", row.source_excerpt],
    ];
    for (const [label, value] of fields) {
      const term = document.createElement("dt");
      const detail = document.createElement("dd");
      term.textContent = label;
      if (label === "Source excerpt") {
        const text = document.createElement("pre");
        text.textContent = displayValue(value);
        detail.append(text);
      } else {
        detail.textContent = displayValue(value);
      }
      list.append(term, detail);
    }
    byId("row-details").hidden = false;
    status.textContent = `Showing unconfirmed details for ${row.analyte}, sample ${row.sample_id}.`;
    byId("details-heading").focus();
  }

  function showResponse(data) {
    if (data.pages) {
      byId("provenance").textContent = `${data.pages.doc_id} · Results PDF page ${data.pages.results_page} · Definitions PDF page ${data.pages.definitions_page}`;
      byId("source-text").textContent = data.pages.results_text;
      byId("definitions-text").textContent = data.pages.definitions_text;
    }
    if (data.status !== "success") return;
    byId("row-count").textContent = `${data.total_rows} unconfirmed result rows, in source order.`;
    for (const row of data.rows) {
      const tr = document.createElement("tr");
      for (const value of [row.sample_id, row.analyte, row.result_as_written, row.qualifier, row.units, "Unconfirmed"]) {
        const cell = document.createElement("td");
        cell.textContent = displayValue(value);
        tr.append(cell);
      }
      const cell = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Details";
      button.setAttribute("aria-label", `Details for ${row.analyte}, sample ${row.sample_id}`);
      button.setAttribute("aria-controls", "row-details");
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", () => showDetails(row, button));
      cell.append(button);
      tr.append(cell);
      byId("result-rows").append(tr);
    }
    byId("rows-region").hidden = false;
    byId("table-size").hidden = data.rows.length <= 5;
    fitTable();
  }

  form.addEventListener("input", () => {
    submission += 1;
    if (pending) pending.abort();
    pending = null;
    submit.disabled = false;
    clearOutput();
    status.textContent = "Inputs changed; previous output cleared. Extract to show current results.";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const current = ++submission;
    if (pending) pending.abort();
    const controller = new AbortController();
    pending = controller;
    clearOutput();
    submit.disabled = true;
    status.textContent = "Reading the source pages and extracting draft results…";
    const fields = new FormData(form);
    const request = {
      doc_id: fields.get("doc_id"),
      results_page: Number(fields.get("results_page")),
      definitions_page: Number(fields.get("definitions_page")),
    };
    try {
      const response = await fetch("/extract", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(request), signal: controller.signal,
      });
      const data = await response.json();
      if (current !== submission) return;
      if (!response.ok) {
        showResponse({...data, status: "error", rows: []});
        status.textContent = data.status === "error" && data.message ? data.message : `Extraction failed (${response.status}). No results are presented.`;
        return;
      }
      showResponse(data);
      status.textContent = data.message || `Extraction failed (${response.status}). Check the document ID and PDF page numbers.`;
    } catch (error) {
      if (current !== submission) return;
      clearOutput();
      status.textContent = "Unable to load an extraction. Your inputs were kept; submit again to retry.";
    } finally {
      if (current === submission) {
        submit.disabled = false;
        pending = null;
      }
    }
  });
})();
