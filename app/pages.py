"""Read reproducible page text from an unchanged archived PDF; never call a model."""

from importlib.metadata import version

import pdfplumber
from pydantic import BaseModel, Field

from app.archive import ArchivedDocument, file_sha256


class PageReadError(Exception):
    """Safe code/message for a source that cannot be read as requested."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PagePair(BaseModel):
    doc_id: str
    title: str
    source_url: str
    sha256: str
    results_page: int
    definitions_page: int
    results_text: str
    definitions_text: str
    reader_versions: dict[str, str] = Field(default_factory=dict)
    extraction_options: dict[str, bool | int | float] = Field(default_factory=dict)


def _verify_file(document: ArchivedDocument) -> None:
    if not document.sha256:
        raise PageReadError("missing_fingerprint", "No source fingerprint is recorded.")
    try:
        actual = file_sha256(document.path)
    except FileNotFoundError as error:
        raise PageReadError("missing_file", "The source PDF is unavailable.") from error
    except OSError as error:
        raise PageReadError(
            "unreadable_pdf", "The source PDF cannot be read."
        ) from error
    if actual != document.sha256:
        raise PageReadError(
            "changed_file", "The source PDF differs from its catalog fingerprint."
        )


def _page_text(pdf: pdfplumber.PDF, number: int) -> str:
    if type(number) is not int or not 1 <= number <= len(pdf.pages):
        raise PageReadError(
            "invalid_page", "Choose a PDF page number within this document."
        )
    text = (
        pdf.pages[number - 1].extract_text(
            layout=True,
            x_tolerance=3,
            y_tolerance=3,
            x_density=7.25,
            y_density=13,
        )
        or ""
    )
    if not text.strip():
        raise PageReadError(
            "empty_page",
            "This page has no extractable text; OCR is outside this experiment.",
        )
    return text


def read_pages(
    document: ArchivedDocument,
    results_page: int,
    definitions_page: int,
) -> PagePair:
    """Keep source text intact, validating the entire PDF before and after reading."""
    _verify_file(document)
    try:
        with pdfplumber.open(document.path) as pdf:
            results = _page_text(pdf, results_page)
            definitions = _page_text(pdf, definitions_page)
    except PageReadError:
        raise
    except Exception as error:
        raise PageReadError(
            "unreadable_pdf", "The source PDF cannot be decoded."
        ) from error
    _verify_file(document)
    return PagePair(
        doc_id=document.doc_id,
        title=document.title,
        source_url=document.source_url,
        sha256=document.sha256,
        results_page=results_page,
        definitions_page=definitions_page,
        results_text=results,
        definitions_text=definitions,
        reader_versions={
            "pdfplumber": version("pdfplumber"),
            "pdfminer.six": version("pdfminer.six"),
        },
        extraction_options={
            "layout": True,
            "x_tolerance": 3,
            "y_tolerance": 3,
            "x_density": 7.25,
            "y_density": 13,
        },
    )
