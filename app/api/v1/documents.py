# app/api/v1/documents.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from typing import List, Optional
import logging

from app.services.document_service import document_service
from app.services.retrieval_service import retrieval_service
from app.models.document import Document

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=Document)
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document"""
    logger.info(f"Uploading document: {file.filename}")
    
    try:
        document = await document_service.upload_and_process_document(file)
        logger.info(f"Document processed successfully: {document.document_id}")
        return document
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Document])
async def get_all_documents():
    """Get all documents"""
    try:
        documents = document_service.get_all_documents()
        return documents
    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ready", response_model=List[Document])
async def get_ready_documents():
    """Get all documents that are ready for querying"""
    try:
        documents = document_service.get_ready_documents()
        return documents
    except Exception as e:
        logger.error(f"Error getting ready documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/vector-store")
async def debug_vector_store():
    """Debug vector store contents"""
    try:
        from app.services.vector_store import vector_store
        
        collection = vector_store.collection
        count = collection.count()
        
        # Get all documents in the collection - FIXED: removed 'ids' from include
        all_data = collection.get(include=["documents", "metadatas"])
        
        return {
            "collection_name": collection.name,
            "total_chunks": count,
            "chunk_ids": all_data.get("ids", []),
            "chunk_count_actual": len(all_data.get("ids", [])),
            "sample_metadata": all_data.get("metadatas", [])[:3],  # First 3 for preview
            "sample_content": [
                doc[:100] + "..." if len(doc) > 100 else doc 
                for doc in (all_data.get("documents", [])[:3])  # First 3 for preview
            ]
        }
        
    except Exception as e:
        logger.error(f"Error debugging vector store: {str(e)}")
        return {"error": str(e)}

@router.get("/debug/search-step-by-step")
async def debug_search_step_by_step(query: str = Query(...)):
    """Step by step search debugging"""
    try:
        from app.services.vector_store import vector_store
        from app.services.retrieval_service import retrieval_service
        
        result = {
            "query": query,
            "steps": []
        }
        
        # Step 1: Check ready documents
        ready_docs = document_service.get_ready_documents()
        result["steps"].append({
            "step": "1_check_ready_documents",
            "ready_document_count": len(ready_docs),
            "ready_document_ids": [doc.document_id for doc in ready_docs]
        })
        
        # Step 2: Check vector store
        collection_count = vector_store.collection.count()
        result["steps"].append({
            "step": "2_check_vector_store",
            "total_chunks_in_store": collection_count
        })
        
        # Step 3: Try direct vector search
        if collection_count > 0:
            try:
                # Generate query embedding
                query_embedding = vector_store.embedding_service.encode_text(query)
                
                # Direct ChromaDB search
                search_results = vector_store.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=5,
                    include=["documents", "metadatas", "distances"]
                )
                
                result["steps"].append({
                    "step": "3_direct_vector_search",
                    "success": True,
                    "results_found": len(search_results.get("documents", [{}])[0] if search_results.get("documents") else []),
                    "distances": search_results.get("distances", [{}])[0] if search_results.get("distances") else [],
                    "sample_content": [
                        doc[:100] + "..." 
                        for doc in (search_results.get("documents", [{}])[0][:2] if search_results.get("documents") else [])
                    ]
                })
            except Exception as e:
                result["steps"].append({
                    "step": "3_direct_vector_search",
                    "success": False,
                    "error": str(e)
                })
        
        # Step 4: Try retrieval service
        try:
            chunks = retrieval_service.retrieve_relevant_chunks(query, top_k=3)
            result["steps"].append({
                "step": "4_retrieval_service",
                "success": True,
                "chunks_returned": len(chunks),
                "chunk_previews": [
                    chunk.get("content", "")[:100] + "..." 
                    for chunk in chunks[:2]
                ]
            })
        except Exception as e:
            result["steps"].append({
                "step": "4_retrieval_service",
                "success": False,
                "error": str(e)
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in step-by-step debug: {str(e)}")
        return {"error": str(e)}

# Also, let's fix the search endpoint to provide better error information
@router.get("/search")
async def search_documents(
    query: str = Query(..., description="Search query"),
    document_ids: Optional[str] = Query(None, description="Comma-separated document IDs to search in"),
    top_k: int = Query(5, description="Number of results to return", ge=1, le=20),
    min_similarity: float = Query(0.3, description="Minimum similarity threshold", ge=0.0, le=1.0)
):
    """Search for similar chunks across documents using GET method"""
    try:
        logger.info(f"Search request - Query: '{query}', Document IDs: {document_ids}, Top K: {top_k}")
        
        # Parse document_ids if provided
        doc_ids = None
        if document_ids:
            doc_ids = [doc_id.strip() for doc_id in document_ids.split(",") if doc_id.strip()]
        
        # Get retrieval stats first for debugging
        stats = retrieval_service.get_retrieval_stats()
        logger.info(f"Current stats: {stats}")
        
        # Check if we have any chunks at all
        vector_stats = stats.get("vector_store_stats", {})
        total_chunks = vector_stats.get("total_chunks", 0)
        
        if total_chunks == 0:
            logger.warning("No chunks in vector store")
            return {
                "query": query,
                "total_results": 0,
                "results": [],
                "message": "No chunks found in vector store. Please upload and process documents first.",
                "debug_stats": stats
            }
        
        results = retrieval_service.retrieve_relevant_chunks(
            query=query,
            document_ids=doc_ids,
            top_k=top_k,
            min_similarity=min_similarity
        )
        
        if len(results) == 0:
            logger.warning(f"No results found for query: {query}")
            return {
                "query": query,
                "document_ids_searched": doc_ids,
                "total_results": 0,
                "results": [],
                "message": f"No relevant chunks found for query '{query}'. Try a different search term or lower the similarity threshold.",
                "debug_stats": stats
            }
        
        response = {
            "query": query,
            "document_ids_searched": doc_ids,
            "total_results": len(results),
            "results": results
        }
        
        logger.info(f"Search completed - returning {len(results)} results")
        return response
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test/vector-store")
async def test_vector_store():
    """Test vector store directly"""
    try:
        from app.services.vector_store import vector_store
        
        # Get collection info
        collection = vector_store.collection
        count = collection.count()
        
        # Get a sample of documents
        sample = collection.get(limit=3, include=["documents", "metadatas"])
        
        return {
            "collection_name": collection.name,
            "total_documents": count,
            "sample_count": len(sample.get("ids", [])),
            "sample_ids": sample.get("ids", []),
            "sample_metadata": sample.get("metadatas", []),
            "sample_content_preview": [
                doc[:100] + "..." if len(doc) > 100 else doc 
                for doc in sample.get("documents", [])
            ]
        }
        
    except Exception as e:
        logger.error(f"Error testing vector store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/{document_id}")
async def debug_document(document_id: str):
    """Debug document processing"""
    try:
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check vector store directly
        from app.services.vector_store import vector_store
        
        # Try to get chunks for this document from vector store
        try:
            vector_results = vector_store.collection.get(
                where={"document_id": document_id},
                include=["metadatas"]
            )
            chunks_in_vector_store = len(vector_results.get("ids", []))
        except Exception as e:
            chunks_in_vector_store = f"Error: {str(e)}"
        
        return {
            "document_id": document_id,
            "document_status": document.status,
            "chunks_in_document": len(document.chunks),
            "chunks_in_vector_store": chunks_in_vector_store,
            "document_metadata": {
                "filename": document.metadata.original_filename,
                "file_size": document.metadata.file_size,
                "word_count": document.metadata.word_count,
                "processing_timestamp": document.metadata.processing_timestamp
            },
            "first_chunk_sample": document.chunks[0].content[:200] + "..." if document.chunks else "No chunks",
            "error_message": document.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error debugging document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_documents_post(search_request: dict):
    """Search for similar chunks using POST method (for complex queries)"""
    try:
        query = search_request.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        document_ids = search_request.get("document_ids")
        top_k = search_request.get("top_k", 5)
        min_similarity = search_request.get("min_similarity", 0.3)
        
        results = retrieval_service.retrieve_relevant_chunks(
            query=query,
            document_ids=document_ids,
            top_k=top_k,
            min_similarity=min_similarity
        )
        
        return {
            "query": query,
            "document_ids_searched": document_ids,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test/health")
async def test_health():
    """Test endpoint to verify API is working"""
    try:
        return {
            "status": "healthy",
            "upload_dir_exists": os.path.exists(settings.upload_dir),
            "upload_dir": settings.upload_dir,
            "allowed_extensions": settings.allowed_extensions,
            "max_file_size": settings.max_file_size
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.post("/test/simple-upload")
async def test_simple_upload(file: UploadFile = File(...)):
    """Simple test upload without processing"""
    try:
        logger.info(f"Testing simple upload: {file.filename}")
        
        # Basic file info
        content = await file.read()
        
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(content),
            "first_100_chars": content[:100].decode('utf-8', errors='ignore') if content else "Empty file"
        }
        
    except Exception as e:
        logger.error(f"Error in test upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/retrieval")
async def get_retrieval_stats():
    """Get retrieval system statistics"""
    try:
        stats = retrieval_service.get_retrieval_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting retrieval stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/vector-store")
async def get_vector_store_stats():
    """Get vector store specific statistics"""
    try:
        from app.services.vector_store import vector_store
        stats = vector_store.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting vector store stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}", response_model=Document)
async def get_document(document_id: str):
    """Get a specific document by ID"""
    try:
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    try:
        success = document_service.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": f"Document {document_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str):
    """Get all chunks for a specific document"""
    try:
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "document_id": document_id,
            "total_chunks": len(document.chunks),
            "chunks": document.chunks
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunks for document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
