# =====================================================
# app/services/vector_store.py
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Tuple
import uuid
import logging
from datetime import datetime

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.models.document import DocumentChunk

logger = logging.getLogger(__name__)

class VectorStore:
    """ChromaDB vector store for document chunks"""
    
    def __init__(self):
        try:
            # Initialize ChromaDB client with persistence
            self.client = chromadb.PersistentClient(
                path=settings.chroma_persist_directory,
                settings=chromadb.config.Settings(
                    anonymized_telemetry=False
                )
            )
            
            # Initialize embedding service
            self.embedding_service = EmbeddingService()
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"description": "Document chunks for RAG system"}
            )
            
            logger.info(f"ChromaDB initialized. Collection: {settings.chroma_collection_name}")
            logger.info(f"Current collection size: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            raise
    
    def add_document_chunks(self, chunks: List[DocumentChunk], document_metadata: Dict = None) -> bool:
        """Add document chunks to the vector store"""
        try:
            if not chunks:
                logger.warning("No chunks to add")
                return False
            
            # Prepare data for ChromaDB
            chunk_texts = [chunk.content for chunk in chunks]
            chunk_ids = [chunk.chunk_id for chunk in chunks]
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
            embeddings = self.embedding_service.encode_batch(chunk_texts)
            
            # Prepare metadata for each chunk
            metadatas = []
            for chunk in chunks:
                chunk_metadata = {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "char_count": len(chunk.content),
                    "word_count": len(chunk.content.split()),
                    "created_at": datetime.now().isoformat(),
                }
                
                # Add page number if available
                if hasattr(chunk, 'page_number') and chunk.page_number:
                    chunk_metadata["page_number"] = chunk.page_number
                
                # Add document metadata if provided
                if document_metadata:
                    chunk_metadata.update({
                        "original_filename": document_metadata.get("original_filename", ""),
                        "document_type": document_metadata.get("document_type", ""),
                        "upload_timestamp": document_metadata.get("upload_timestamp", "")
                    })
                
                metadatas.append(chunk_metadata)
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=metadatas,
                ids=chunk_ids
            )
            
            logger.info(f"Successfully added {len(chunks)} chunks to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding chunks to vector store: {e}")
            return False
    
    def search_similar_chunks(
        self, 
        query: str, 
        n_results: int = 5,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using semantic similarity"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.encode_text(query)
            
            # Build where clause for filtering by document IDs
            where_clause = None
            if document_ids:
                where_clause = {"document_id": {"$in": document_ids}}
            
            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0], 
                    results["distances"][0]
                )):
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance,  # Convert distance to similarity
                        "distance": distance,
                        "rank": i + 1
                    })
            
            logger.info(f"Found {len(formatted_results)} similar chunks for query")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(
                where={"document_id": document_id},
                include=["metadatas"]
            )
            
            if results["ids"]:
                # Delete the chunks
                self.collection.delete(
                    where={"document_id": document_id}
                )
                
                logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")
                return True
            else:
                logger.warning(f"No chunks found for document {document_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting document chunks: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store collection"""
        try:
            count = self.collection.count()
            
            # Get sample of documents to analyze
            sample_results = self.collection.get(limit=100, include=["metadatas"])
            
            # Analyze document types and sources
            doc_types = {}
            doc_sources = {}
            
            for metadata in sample_results.get("metadatas", []):
                doc_type = metadata.get("document_type", "unknown")
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                filename = metadata.get("original_filename", "unknown")
                doc_sources[filename] = doc_sources.get(filename, 0) + 1
            
            return {
                "total_chunks": count,
                "embedding_model": self.embedding_service.model_name,
                "embedding_dimension": self.embedding_service.embedding_dimension,
                "document_types": doc_types,
                "document_sources": list(doc_sources.keys())[:10],  # Top 10 sources
                "collection_name": settings.chroma_collection_name
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"error": str(e)}
    
    def reset_collection(self) -> bool:
        """Reset the entire collection (use with caution!)"""
        try:
            self.client.delete_collection(settings.chroma_collection_name)
            self.collection = self.client.create_collection(
                name=settings.chroma_collection_name,
                metadata={"description": "Document chunks for RAG system"}
            )
            logger.info("Collection reset successfully")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False

# Create global instance
vector_store = VectorStore()