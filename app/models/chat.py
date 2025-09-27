# app/models/chat.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    sources: Optional[List[Dict[str, Any]]] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    conversation_history: Optional[List[ChatMessage]] = None
    max_history: int = 5

class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: List[Dict[str, Any]] = []
    processing_time: float
    model_used: str
    
class ChatSession(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    messages: List[ChatMessage] = []
    # Document context for this session
    active_document_ids: List[str] = []
    session_name: Optional[str] = None
    document_context: Dict[str, Any] = {}  # Metadata about documents in this session

class SessionStartRequest(BaseModel):
    document_ids: List[str]
    session_name: Optional[str] = None
    session_id: Optional[str] = None  # Optional: use specific session ID