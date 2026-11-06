"""Generate tiny text PDFs for reader tests, without another PDF dependency."""

from pathlib import Path

from app.archive import ArchivedDocument, file_sha256


def write_pdf(path: Path, texts: tuple[str, ...]) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(
            f"{4 + 2 * n} 0 R" for n in range(len(texts))
        ) + f"] /Count {len(texts)} >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for n, text in enumerate(texts):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode()
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * n} 0 R >>").encode(),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ])
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{n} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                 f"startxref\n{start}\n%%EOF\n").encode())
    path.write_bytes(data)


def document_for(path: Path) -> ArchivedDocument:
    return ArchivedDocument(
        doc_id="DOC-0001", title="Test report", library_id="test", sdg="batch",
        doc_type="lab", path=path, sha256=file_sha256(path),
        source_url="https://example.org/report.pdf",
    )
