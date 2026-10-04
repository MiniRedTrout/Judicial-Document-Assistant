from typing import Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    status: str


class DocumentResponse(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    file_path: str
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    stage: str
    message: str
    progress: int
    error: Optional[str] = None

class DocumentListItem(DocumentStatusResponse):
    file_name: str
    file_type: str


class BatchUploadError(BaseModel):
    file_name: Optional[str] = None
    error: str


class BatchUploadResponse(BaseModel):
    documents: list[UploadResponse] = Field(default_factory=list)
    errors: list[BatchUploadError] = Field(default_factory=list)