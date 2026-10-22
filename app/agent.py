"""Request and output schemas; agent initialization is deferred."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


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
