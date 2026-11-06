"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {JSDOM} = require("jsdom");
const html = fs.readFileSync(path.join(__dirname, "../../app/extraction_page.html"), "utf8");
const source = fs.readFileSync(path.join(__dirname, "../../app/static/extraction.js"), "utf8");
const tick = () => new Promise((resolve) => setImmediate(resolve));

function setup() {
  const dom = new JSDOM(html, {url: "http://localhost/extract", runScripts: "outside-only"});
  const window = dom.window;
  const requests = [];
  window.fetch = (_url, options) => new Promise((resolve, reject) => requests.push({resolve, reject, options}));
  window.eval(source);
  const document = window.document;
  document.getElementById("doc-id").value = "DOC-0033";
  const submit = () => document.getElementById("extraction-form").dispatchEvent(new window.Event("submit", {bubbles: true, cancelable: true}));
  return {window, document, requests, submit};
}

function payload(changes = {}) {
  return {status: "success", message: "Unconfirmed output", total_rows: 1,
    pages: {doc_id: "DOC-0033", results_page: 6, definitions_page: 3, results_text: "Sample S1\nLead <0.020", definitions_text: "U not detected"},
    rows: [{doc_id: "DOC-0033", page_number: 6, sample_id: "S1", analyte: "Lead", result_as_written: "<0.020", qualifier: "U", units: "ug/L", mdl: null, ...changes}]};
}

function respond(request, data, status = 200) {
  request.resolve({ok: status < 400, status, json: async () => data});
}

test("draft rows preserve nondetect spelling and show a missing MDL", async () => {
  const {window, document, requests, submit} = setup();
  submit();
  assert.equal(document.getElementById("extract-button").disabled, true);
  respond(requests[0], payload());
  await tick();
  assert.equal(document.querySelectorAll("#result-rows tr").length, 1);
  assert.equal(document.querySelector("#result-rows tr").children[2].textContent, "<0.020");
  document.querySelector("#result-rows button").click();
  const mdl = [...document.querySelectorAll("#details-list dt")].find((el) => el.textContent === "MDL");
  assert.equal(mdl.nextElementSibling.textContent, "Missing");
  assert.equal(document.querySelector("#result-rows button").getAttribute("aria-expanded"), "true");
  assert.equal(document.getElementById("extract-button").disabled, false);
  window.close();
});

test("a new failed request clears old rows and retains input", async () => {
  const {window, document, requests, submit} = setup();
  submit(); respond(requests[0], payload()); await tick();
  submit();
  assert.equal(document.querySelectorAll("#result-rows tr").length, 0);
  respond(requests[1], {status: "error", message: "Source unavailable", rows: []}, 404);
  await tick();
  assert.equal(document.querySelectorAll("#result-rows tr").length, 0);
  assert.equal(document.getElementById("doc-id").value, "DOC-0033");
  assert.equal(document.getElementById("status").textContent, "Source unavailable");
  window.close();
});

test("late responses cannot replace the newest submission", async () => {
  const {window, document, requests, submit} = setup();
  submit();
  document.getElementById("doc-id").value = "DOC-0003";
  document.getElementById("doc-id").dispatchEvent(new window.Event("input", {bubbles: true}));
  assert.equal(requests[0].options.signal.aborted, true);
  submit();
  respond(requests[1], payload({sample_id: "NEW"})); await tick();
  respond(requests[0], payload({sample_id: "OLD"})); await tick();
  assert.equal(document.querySelector("#result-rows td").textContent, "NEW");
  assert.equal(document.getElementById("extract-button").disabled, false);
  window.close();
});

test("source and model markup render as text", async () => {
  const {window, document, requests, submit} = setup();
  const attack = '<img src=x onerror="window.injected=true">';
  const data = payload({analyte: attack, source_excerpt: "<script>window.injected=true</script>"});
  data.pages.results_text = attack;
  submit(); respond(requests[0], data); await tick();
  assert.equal(document.querySelector("#result-rows tr").children[1].textContent, attack);
  assert.equal(document.getElementById("source-text").textContent, attack);
  document.querySelector("#result-rows button").click();
  assert.equal(document.querySelectorAll("#result-rows img,#row-details script,#source-text img").length, 0);
  assert.equal(window.injected, undefined);
  window.close();
});

test("HTTP errors cannot display a success-shaped payload", async () => {
  const {window, document, requests, submit} = setup();
  submit(); respond(requests[0], payload(), 500); await tick();
  assert.equal(document.querySelectorAll("#result-rows tr").length, 0);
  assert.match(document.getElementById("status").textContent, /failed/i);
  window.close();
});

test("either section can use the full width without losing the extraction", async () => {
  const {window, document, requests, submit} = setup();
  submit(); respond(requests[0], payload()); await tick();
  const sourceOnly = document.getElementById("view-source");
  assert.ok(sourceOnly, "a source-only view control is available");
  sourceOnly.click();
  assert.equal(document.getElementById("source-panel").hidden, false);
  assert.equal(document.getElementById("results-panel").hidden, true);
  assert.equal(sourceOnly.getAttribute("aria-pressed"), "true");
  document.getElementById("view-results").click();
  assert.equal(document.getElementById("source-panel").hidden, true);
  assert.equal(document.getElementById("results-panel").hidden, false);
  assert.equal(sourceOnly.getAttribute("aria-pressed"), "false");
  document.getElementById("view-both").click();
  assert.equal(document.getElementById("source-panel").hidden, false);
  assert.equal(document.getElementById("results-panel").hidden, false);
  assert.equal(document.querySelectorAll("#result-rows tr").length, 1);
  assert.match(document.getElementById("source-text").textContent, /Lead/);
  window.close();
});

test("the compact table fits five measured rows and can expand without dropping rows", async () => {
  const {window, document, requests, submit} = setup();
  // jsdom has no layout. Supply renderer measurements, with unequal row heights.
  const originalRect = window.HTMLElement.prototype.getBoundingClientRect;
  window.HTMLElement.prototype.getBoundingClientRect = function () {
    if (this.matches("thead")) return {height: 40};
    if (this.matches("#result-rows tr")) {
      return {height: [32, 48, 32, 64, 48, 96][this.sectionRowIndex]};
    }
    return originalRect.call(this);
  };
  const data = payload();
  data.rows = Array.from({length: 6}, (_, i) => ({...data.rows[0], analyte: `Analyte ${i + 1}`}));
  data.total_rows = 6;
  submit(); respond(requests[0], data); await tick();
  const viewport = document.getElementById("table-viewport");
  const toggle = document.getElementById("table-size");
  assert.ok(viewport, "results have a bounded table viewport");
  assert.ok(toggle, "the table can be expanded");
  assert.equal(viewport.style.maxHeight, "264px");
  assert.equal(document.querySelectorAll("#result-rows tr").length, 6);
  toggle.click();
  assert.equal(viewport.style.maxHeight, "none");
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  toggle.click();
  assert.equal(viewport.style.maxHeight, "264px");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  // Changing width/zoom can change wrapped row heights and add a horizontal bar.
  const rows = document.querySelectorAll("#result-rows tr");
  rows[0].getBoundingClientRect = () => ({height: 80});
  Object.defineProperty(viewport, "offsetHeight", {value: 300});
  Object.defineProperty(viewport, "clientHeight", {value: 284});
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(viewport.style.maxHeight, "328px");
  toggle.click();
  submit();
  assert.equal(document.getElementById("row-details").hidden, true);
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.equal(toggle.hidden, true);
  respond(requests[1], data); await tick();
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  window.close();
});

test("Details brings the selected information into focus and can return to the row", async () => {
  const {window, document, requests, submit} = setup();
  const data = payload();
  data.rows.push({...data.rows[0], analyte: "Benzene", mdl: "0.15"});
  data.total_rows = 2;
  submit(); respond(requests[0], data); await tick();
  const buttons = document.querySelectorAll("#result-rows button");
  buttons[1].click();
  assert.equal(document.activeElement.id, "details-heading");
  assert.match(document.activeElement.textContent, /Benzene/);
  assert.equal(buttons[0].getAttribute("aria-expanded"), "false");
  assert.equal(buttons[1].getAttribute("aria-expanded"), "true");
  document.getElementById("back-to-row").click();
  assert.equal(document.activeElement, buttons[1]);
  buttons[0].click();
  assert.match(document.getElementById("details-heading").textContent, /Lead/);
  assert.equal(document.activeElement.id, "details-heading");
  window.close();
});
