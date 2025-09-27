# app/api/v1/chat.py - Enhanced version with session-document mapping
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from app.services.chat_service import chat_service
from app.models.chat import ChatRequest, ChatResponse, ChatMessage, ChatSession, SessionStartRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# NEW: Document-aware session management

@router.post("/sessions/start", response_model=ChatSession)
async def start_session_with_documents(request: SessionStartRequest):
    """Start a new chat session with specific documents"""
    try:
        logger.info(f"Starting session with documents: {request.document_ids}")
        
        session = chat_service.start_session_with_documents(request)
        
        logger.info(f"Session started: {session.session_id} with {len(session.active_document_ids)} documents")
        return session
        
    except Exception as e:
        logger.error(f"Error starting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@router.post("/sessions/{session_id}/documents")
async def add_documents_to_session(session_id: str, document_ids: List[str]):
    """Add documents to an existing session"""
    try:
        success = chat_service.add_documents_to_session(session_id, document_ids)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "message": f"Added {len(document_ids)} documents to session {session_id}",
            "document_ids": document_ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding documents to session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}/documents")
async def remove_documents_from_session(session_id: str, document_ids: List[str]):
    """Remove documents from a session"""
    try:
        success = chat_service.remove_documents_from_session(session_id, document_ids)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "message": f"Removed {len(document_ids)} documents from session {session_id}",
            "document_ids": document_ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing documents from session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/documents")
async def get_session_documents(session_id: str):
    """Get documents associated with a session"""
    try:
        session = chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "session_name": session.session_name,
            "active_document_ids": session.active_document_ids,
            "document_context": session.document_context,
            "document_count": len(session.active_document_ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ENHANCED: Existing endpoints with better document context

@router.post("/message", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest):
    """Send a chat message and get AI response with document context"""
    try:
        logger.info(f"Received chat message: '{request.message[:50]}...' for session: {request.session_id}")
        
        response = await chat_service.process_chat_message(request)
        
        logger.info(f"Chat response generated in {response.processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.get("/sessions")
async def get_all_sessions():
    """Get all chat sessions with document context"""
    try:
        sessions = chat_service.get_all_sessions()
        return {
            "total_sessions": len(sessions),
            "sessions": [
                {
                    "session_id": session.session_id,
                    "session_name": session.session_name,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "message_count": session.message_count,
                    "active_document_count": len(session.active_document_ids),
                    "active_documents": [
                        session.document_context.get(doc_id, {}).get("filename", doc_id)
                        for doc_id in session.active_document_ids
                    ]
                }
                for session in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str):
    """Get a specific chat session"""
    try:
        session = chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(50, description="Maximum number of messages to return")
):
    """Get chat history for a session"""
    try:
        history = chat_service.get_session_history(session_id, limit)
        
        return {
            "session_id": session_id,
            "message_count": len(history),
            "messages": history
        }
    except Exception as e:
        logger.error(f"Error getting session history {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session"""
    try:
        success = chat_service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": f"Session {session_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add this endpoint to your existing app/api/v1/chat.py file

@router.get("/conversations")
async def list_conversations():
    """List all conversations like Claude's sidebar"""
    try:
        sessions = chat_service.get_all_sessions()
        
        # Sort by last activity (most recent first)
        sorted_sessions = sorted(sessions, key=lambda x: x.last_activity, reverse=True)
        
        conversations = []
        for session in sorted_sessions:
            # Get first user message for preview
            first_message = ""
            for msg in session.messages:
                if msg.role == "user":
                    first_message = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    break
            
            conversations.append({
                "id": session.session_id,
                "title": session.session_name,
                "preview": first_message,
                "last_activity": session.last_activity,
                "message_count": session.message_count,
                "document_count": len(session.active_document_ids),
                "created_at": session.created_at
            })
        
        return {
            "conversations": conversations,
            "total_count": len(conversations)
        }
        
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
# NEW: Document-specific session queries

@router.get("/documents/{document_id}/sessions")
async def get_sessions_for_document(document_id: str):
    """Get all sessions that include a specific document"""
    try:
        sessions = chat_service.get_sessions_for_document(document_id)
        
        return {
            "document_id": document_id,
            "session_count": len(sessions),
            "sessions": [
                {
                    "session_id": session.session_id,
                    "session_name": session.session_name,
                    "created_at": session.created_at,
                    "message_count": session.message_count,
                    "total_documents": len(session.active_document_ids)
                }
                for session in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Error getting sessions for document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ENHANCED: Test endpoints with document context

@router.get("/test/document-aware")
async def test_document_aware_chat(
    query: str = Query(..., description="Test query"),
    document_ids: str = Query(..., description="Comma-separated document IDs")
):
    """Test document-aware chat functionality"""
    try:
        # Parse document IDs
        doc_ids = [doc_id.strip() for doc_id in document_ids.split(",")]
        
        # Start session with documents
        session_request = SessionStartRequest(
            document_ids=doc_ids,
            session_name=f"Test session for query: {query[:30]}"
        )
        
        session = chat_service.start_session_with_documents(session_request)
        
        # Send test message
        chat_request = ChatRequest(
            message=query,
            session_id=session.session_id,
            max_history=3
        )
        
        response = await chat_service.process_chat_message(chat_request)
        
        return {
            "test_query": query,
            "session_id": session.session_id,
            "documents_used": doc_ids,
            "response": response.response,
            "sources_count": len(response.sources),
            "sources": response.sources,
            "processing_time": response.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error in document-aware chat test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test")
async def test_chat_system(
    query: str = Query(..., description="Test query"),
    session_id: Optional[str] = Query(None, description="Optional session ID")
):
    """Test the complete chat system (legacy - searches all documents)"""
    try:
        # Create a test request
        test_request = ChatRequest(
            message=query,
            session_id=session_id,
            document_ids=None,  # Will search all documents
            max_history=3
        )
        
        # Process the message
        response = await chat_service.process_chat_message(test_request)
        
        return {
            "test_query": query,
            "response": response.response,
            "session_id": response.session_id,
            "sources_count": len(response.sources),
            "sources": response.sources,
            "processing_time": response.processing_time,
            "model_used": response.model_used,
            "search_scope": "all_documents"
        }
        
    except Exception as e:
        logger.error(f"Error in chat system test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))