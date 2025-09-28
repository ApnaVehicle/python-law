from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RetrievalService:
    """Service for retrieving relevant document chunks"""
    
    def __init__(self):
        # Import here to avoid circular imports
        from app.services.vector_store_memory import memory_vector_store
        from app.services.document_service import document_service
        self.vector_store = memory_vector_store
        self.document_service = document_service
    
    async def retrieve_relevant_chunks(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query"""
        try:
            logger.info(f"Retrieving chunks for query: '{query}' with document_ids: {document_ids}")
            
            # Check if we have any documents in vector store
            collection_stats = self.vector_store.get_collection_stats()
            total_chunks = collection_stats.get("total_chunks", 0)
            logger.info(f"Total chunks in vector store: {total_chunks}")
            
            if total_chunks == 0:
                logger.warning("No chunks found in vector store")
                return []
            
            # FIXED: Don't require ready documents from document service
            # If document_ids not specified, search ALL chunks in vector store
            search_document_ids = document_ids  # Can be None, that's fine
            
            if not document_ids:
                # Get all document IDs directly from vector store
                try:
                    all_docs = self.vector_store.collection.get(include=["metadatas"])
                    if all_docs.get("metadatas"):
                        all_doc_ids = list(set([
                            meta.get("document_id") for meta in all_docs["metadatas"] 
                            if meta.get("document_id")
                        ]))
                        search_document_ids = all_doc_ids if all_doc_ids else None
                        logger.info(f"Found document IDs in vector store: {search_document_ids}")
                except Exception as e:
                    logger.warning(f"Could not get doc IDs from vector store: {e}")
                    search_document_ids = None  # Search all
            
            # Search for similar chunks
            logger.info(f"Searching with query: '{query}', top_k: {top_k}")
            similar_chunks = await self.vector_store.search_similar_chunks(
                query=query,
                n_results=min(top_k * 2, 20),  # Get more candidates for filtering
                document_ids=search_document_ids
            )
            
            logger.info(f"Vector search returned {len(similar_chunks)} chunks")
            
            # If no results from vector search, return empty
            if not similar_chunks:
                logger.warning("No similar chunks found from vector search")
                return []
            
            # Filter by minimum similarity
            filtered_chunks = [
                chunk for chunk in similar_chunks 
                if chunk.get("similarity_score", 0) >= min_similarity
            ]
            
            logger.info(f"After similarity filtering: {len(filtered_chunks)} chunks")
            
            # Limit to top_k results
            final_chunks = filtered_chunks[:top_k]
            
            # Add some debug info to each chunk
            for i, chunk in enumerate(final_chunks):
                chunk["debug_info"] = {
                    "rank": i + 1,
                    "original_similarity": chunk.get("similarity_score", 0),
                    "chunk_preview": chunk.get("content", "")[:100] + "..."
                }
            
            logger.info(f"Returning {len(final_chunks)} relevant chunks")
            return final_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving chunks: {str(e)}", exc_info=True)
            return []
    
    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get statistics about the retrieval system"""
        try:
            vector_stats = self.vector_store.get_collection_stats()
            ready_docs = self.document_service.get_ready_documents()
            total_docs = self.document_service.get_all_documents()
            
            # Also get document info directly from vector store
            vector_doc_ids = []
            try:
                all_docs = self.vector_store.collection.get(include=["metadatas"])
                if all_docs.get("metadatas"):
                    vector_doc_ids = list(set([
                        meta.get("document_id") for meta in all_docs["metadatas"] 
                        if meta.get("document_id")
                    ]))
            except Exception as e:
                logger.warning(f"Could not get doc IDs from vector store: {e}")
            
            return {
                "vector_store_stats": vector_stats,
                "ready_documents": len(ready_docs),
                "total_documents": len(total_docs),
                "ready_document_ids": [doc.document_id for doc in ready_docs] if ready_docs else [],
                "vector_store_document_ids": vector_doc_ids,  # Documents that actually have chunks
                "can_search": len(vector_doc_ids) > 0 or vector_stats.get("total_chunks", 0) > 0
            }
        except Exception as e:
            logger.error(f"Error getting retrieval stats: {str(e)}")
            return {"error": str(e)}

# Create global instance
retrieval_service = RetrievalService()
