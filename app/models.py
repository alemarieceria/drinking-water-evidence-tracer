"""Data contracts for the demonstration and extraction workflow."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
    model_validator,
)

from app.pages import PagePair


class DocumentMetadata(BaseModel):
    publication_id: str
    title: str
    batch: str | None = None
    laboratory: str | None = None
    report_level: str | None = None
    revision: str | None = None


class PageContext(BaseModel):
    page_text: str
    page_number: int = Field(ge=1)
    document: DocumentMetadata
    qualifier_definitions: dict[str, str] = Field(default_factory=dict)


class TraceRequest(BaseModel):
    sample_id: str | None = None
    analyte: str | None = None
    page_context: PageContext | None = None


class SourcePage(BaseModel):
    document: DocumentMetadata
    page_number: int = Field(ge=1)
    url: str | None = None


class Location(BaseModel):
    location_id: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    flushing_zone: str


class Sample(BaseModel):
    field_sample_id: str
    collection_date: date
    collection_time: time | None = None
    sample_type: str | None = None
    requested_analyses: list[str] = Field(default_factory=list)
    batch_count: int
    location: Location


class ScreeningLevel(BaseModel):
    value: Decimal
    units: str
    type: str
    source: SourcePage


class Result(BaseModel):
    field_sample_id: str
    lab_sample_id: str | None = None
    analyte: str
    method: str
    result_as_written: str
    value: Decimal | None = None
    units: str
    qualifier: str | None = None
    reporting_limit: Decimal | None = None
    detection_limit: Decimal | None = None
    dilution: Decimal | None = None
    analysis_date: date | None = None
    source_pages: list[SourcePage] = Field(default_factory=list)
    screening_levels: list[ScreeningLevel] = Field(default_factory=list)
    review_status: str = "unconfirmed"
    unclear: bool = False


class ValidationFinding(BaseModel):
    sample_ids: list[str]
    analytes: list[str]
    qualifier: str
    reason: str
    source_page: SourcePage


class ReviewDecision(BaseModel):
    decision: Literal["confirm", "correct", "flag"]
    corrected_value: Decimal | None = None
    note: str | None = None
    reviewer: str
    timestamp: datetime


class InventoryItem(BaseModel):
    analyte: str
    method: str
    batch: str | None = None
    status: str


class TraceRow(BaseModel):
    result: Result
    validation_status: str
    validation_findings: list[ValidationFinding] = Field(default_factory=list)
    summary_value: str | None = None
    summary_source: SourcePage | None = None
    status: str
    review_decision: ReviewDecision | None = None


class EvidenceSet(BaseModel):
    name: str
    selection: list[str]
    included_results: list[Result]
    export_date: date | None = None


class TraceResponse(BaseModel):
    placeholder: bool = True
    message: str
    sample: Sample
    inventory: list[InventoryItem]
    trace: list[TraceRow]
    source_preview: str
    evidence_sets: list[EvidenceSet] = Field(default_factory=list)


Nonblank = Annotated[str, Field(min_length=1, pattern=r"\S")]


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    doc_id: str = Field(pattern=r"^DOC-\d{4}$")
    results_page: int = Field(ge=1)
    definitions_page: int = Field(ge=1)


class ExtractedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: Nonblank
    analyte: Nonblank
    result_as_written: Nonblank
    source_line: int = Field(strict=True, ge=1)
    source_excerpt: Nonblank
    lab_sample_id: str | None = None
    method: str | None = None
    qualifier: str | None = None
    reporting_limit: str | None = None
    mdl: str | None = None
    units: str | None = None
    dilution: str | None = None
    analysis_date: str | None = None


class PageExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["extracted", "unclear"]
    reason: str | None = None
    rows: list[ExtractedRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_outcome(self) -> Self:
        if self.status == "extracted" and (not self.rows or self.reason is not None):
            raise ValueError("Extracted requires rows and no reason.")
        if self.status == "unclear" and (self.rows or not (self.reason or "").strip()):
            raise ValueError("Unclear requires an explanation and no rows.")
        return self


class DraftRow(ExtractedRow):
    doc_id: str
    page_number: int
    row_number: int
    value: Decimal | None
    is_nondetect: bool
    review_status: Literal["unconfirmed"] = "unconfirmed"


class AgentAttempt(BaseModel):
    output: PageExtraction | None = None
    messages: list[JsonValue] = Field(default_factory=list)
    requested_model: str | None = None
    returned_model: str | None = None
    usage: dict[str, JsonValue] = Field(default_factory=dict)
    public_config: dict[str, JsonValue] = Field(default_factory=dict)
    runtime_versions: dict[str, str] = Field(default_factory=dict)
    prompt: str = ""
    prompt_version: str = "page-extraction-v1"
    prompt_sha256: str = ""
    error_code: str | None = None


class ExtractionResponse(BaseModel):
    request: ExtractionRequest
    run_id: UUID | None = None
    status: Literal["success", "unclear", "error"]
    error_code: str | None = None
    message: str
    pages: PagePair | None = None
    rows: list[DraftRow] = Field(default_factory=list)

    @computed_field
    def total_rows(self) -> int:
        return len(self.rows)

    @model_validator(mode="after")
    def check_no_partial_rows(self) -> Self:
        if self.status != "success" and self.rows:
            raise ValueError("Failed/unclear responses must not display partial rows.")
        return self


class RunRecord(BaseModel):
    schema_version: int = 1
    run_id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    request: ExtractionRequest
    status: Literal["running", "success", "unclear", "error"] = "running"
    pages: PagePair | None = None
    attempt: AgentAttempt | None = None
    rows: list[DraftRow] = Field(default_factory=list)
    error_code: str | None = None
    message: str = "Extraction started."
