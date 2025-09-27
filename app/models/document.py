# =====================================================
# app/models/document.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"

class DocumentStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

class DocumentMetadata(BaseModel):
    filename: str
    original_filename: str
    file_size: int
    document_type: str
    upload_timestamp: datetime
    processing_timestamp: Optional[datetime] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    page_number: Optional[int] = None
    chunk_index: int
    metadata: Optional[Dict[str, Any]] = None

class Document(BaseModel):
    document_id: str
    status: DocumentStatus
    metadata: DocumentMetadata
    chunks: Optional[List[DocumentChunk]] = None
    error_message: Optional[str] = None

class DocumentUpload(BaseModel):
    filename: str
    content_type: str
    size: int

class DocumentInfo(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    upload_date: datetime
    processed: bool = False

class DocumentSearchResult(BaseModel):
    document_id: str
    filename: str
    content: str
    score: float
    page_number: Optional[int] = None