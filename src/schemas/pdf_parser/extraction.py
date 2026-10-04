from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class TableData(BaseModel):

    page: int
    data: list[list[str]] = Field(default_factory=list)
    extractor: str = "unknown"
    confidence: float | None = None


class PageText(BaseModel):

    page: int
    text: str


class ExtractionMetadata(BaseModel):

    extractor: str
    ocr_used: bool = False
    ocr_confidence: float | None = None
    dpi: int | None = None
    preprocessing: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):

    file: str
    source_format: Literal["pdf"] = "pdf"
    has_text_layer: bool
    pages_count: int
    text: str
    text_by_page: list[PageText] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    metadata: ExtractionMetadata
    errors: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def error_result(
    pdf_path: str | Path,
    error: str,
    *,
    extractor: str = "none",
    ocr_used: bool = False,
    dpi: int | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        file=str(pdf_path),
        has_text_layer=False,
        pages_count=0,
        text="",
        text_by_page=[],
        tables=[],
        metadata=ExtractionMetadata(
            extractor=extractor,
            ocr_used=ocr_used,
            dpi=dpi,
        ),
        errors=[error],
    )


def empty_result(
    pdf_path: str | Path,
    *,
    extractor: str = "pdfplumber",
    has_text_layer: bool = True,
) -> ExtractionResult:
    return ExtractionResult(
        file=str(pdf_path),
        has_text_layer=has_text_layer,
        pages_count=0,
        text="",
        text_by_page=[],
        tables=[],
        metadata=ExtractionMetadata(
            extractor=extractor,
            ocr_used=not has_text_layer,
        ),
        errors=[],
    )