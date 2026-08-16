"""Unit tests for the pypdf-based document parser (v0.6)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pypdf import PdfReader, PdfWriter

from growth.application.ports.document_parser import DocumentParseError
from growth.infrastructure.parsers.pdf import PypdfParser


def _build_pdf(pages: list[str]) -> bytes:
    """Build a minimal valid PDF, one text line per page.

    Hand-rolled (no reportlab) so the test suite has zero extra
    dependencies: objects are laid out deterministically —

      page i: content (3i+1), font (3i+2), page (3i+3)
      then:   Pages (3n+1), Catalog (3n+2)

    The xref table is written with real byte offsets, so pypdf reads
    it without needing to rebuild the structure.
    """
    n = len(pages)
    pages_num = 3 * n + 1
    body = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]

    def emit(num: int, obj: bytes) -> None:
        offsets.append(len(body))
        body.extend(f"{num} 0 obj\n".encode() + obj + b"\nendobj\n")

    for i, text in enumerate(pages):
        content_num = 3 * i + 1
        font_num = 3 * i + 2
        page_num = 3 * i + 3
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        emit(
            content_num,
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
        )
        emit(font_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        emit(
            page_num,
            (
                f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_num} 0 R "
                f"/Resources << /Font << /F1 {font_num} 0 R >> >> >>"
            ).encode(),
        )

    kids = " ".join(f"{3 * i + 3} 0 R" for i in range(n))
    emit(pages_num, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    emit(3 * n + 2, f"<< /Type /Catalog /Pages {pages_num} 0 R >>".encode())

    xref_pos = len(body)
    body.extend(f"xref\n0 {3 * n + 3}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        body.extend(f"{off:010d} 00000 n \n".encode())
    body.extend(
        f"trailer\n<< /Size {3 * n + 3} /Root {3 * n + 2} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(body)


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """A two-page PDF with distinct text on each page."""
    path = tmp_path / "sample.pdf"
    path.write_bytes(_build_pdf(["Hello Growth PDF", "Second page content"]))
    return path


class TestPypdfParser:
    def test_extracts_text_and_page_count(self, pdf_file: Path) -> None:
        doc = PypdfParser().extract(pdf_file)
        assert doc.format == "pdf"
        assert doc.title == "sample.pdf"
        assert doc.page_count == 2
        assert "Hello Growth PDF" in doc.text
        assert "Second page content" in doc.text

    def test_pages_joined_with_blank_lines(self, pdf_file: Path) -> None:
        doc = PypdfParser().extract(pdf_file)
        assert "\n\n" in doc.text

    def test_single_page(self, tmp_path: Path) -> None:
        path = tmp_path / "one.pdf"
        path.write_bytes(_build_pdf(["Only page"]))
        doc = PypdfParser().extract(path)
        assert doc.page_count == 1
        assert doc.text == "Only page"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DocumentParseError, match="cannot open"):
            PypdfParser().extract(tmp_path / "nope.pdf")

    def test_garbage_bytes_raise(self, tmp_path: Path) -> None:
        path = tmp_path / "fake.pdf"
        path.write_bytes(b"this is definitely not a pdf at all")
        with pytest.raises(DocumentParseError):
            PypdfParser().extract(path)

    def test_empty_pdf_yields_empty_text(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.pdf"
        path.write_bytes(_build_pdf([]))
        doc = PypdfParser().extract(path)
        assert doc.page_count == 0
        assert doc.text == ""

    def test_encrypted_pdf_raises(self, tmp_path: Path) -> None:
        source = tmp_path / "open.pdf"
        source.write_bytes(_build_pdf(["secret text"]))
        locked = tmp_path / "locked.pdf"
        writer = PdfWriter()
        writer.append(str(source))
        writer.encrypt("hunter2", algorithm="RC4-128")
        with locked.open("wb") as fh:
            writer.write(fh)

        reader = PdfReader(str(locked))
        assert reader.is_encrypted  # sanity: fixture really is encrypted

        with pytest.raises(DocumentParseError, match="encrypted"):
            PypdfParser().extract(locked)

    def test_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DocumentParseError):
            PypdfParser().extract(tmp_path)

    def test_page_extraction_failure_maps_to_parse_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A page that fails mid-extraction becomes DocumentParseError."""

        class _FakePage:
            def extract_text(self) -> str:
                raise ValueError("broken cmap")

        class _FakeReader:
            is_encrypted = False
            pages: ClassVar[list] = [_FakePage()]

        monkeypatch.setattr(
            "growth.infrastructure.parsers.pdf.PdfReader",
            lambda _path: _FakeReader(),
        )
        source = tmp_path / "tricky.pdf"
        source.write_bytes(_build_pdf(["x"]))

        with pytest.raises(DocumentParseError, match="cannot extract text"):
            PypdfParser().extract(source)
