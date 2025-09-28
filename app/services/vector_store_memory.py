# app/services/vector_store_memory.py
import json
import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
# Removed numpy and scikit-learn dependencies for ultra-minimal deployment

from app.core.config import settings
from app.services.embedding_service_cloud import CloudEmbeddingService
from app.models.document import DocumentChunk

logger = logging.getLogger(__name__)

class MemoryVectorStore:
    """In-memory vector store for Vercel deployment (no ChromaDB dependency)"""
    
    def __init__(self):
        try:
            # Initialize cloud embedding service
            self.embedding_service = CloudEmbeddingService()
            
            # In-memory storage
            self.embeddings = {}  # {chunk_id: embedding_vector}
            self.documents = {}   # {chunk_id: document_text}
            self.metadatas = {}   # {chunk_id: metadata_dict}
            self.document_index = {}  # {document_id: [chunk_ids]}
            
            # Storage file for persistence (handle serverless environments)
            try:
                self.storage_file = os.path.join(settings.chroma_persist_directory, "memory_vector_store.json")
                # Test if we can write to the directory
                os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
                self.is_serverless = False
            except OSError as e:
                if "Read-only file system" in str(e) or e.errno == 30:
                    # Use temporary directory for serverless
                    import tempfile
                    self.storage_file = os.path.join(tempfile.gettempdir(), "memory_vector_store.json")
                    self.is_serverless = True
                    logger.info("Memory vector store running in serverless mode - using temporary storage")
                else:
                    raise
            
            # Load existing data if available
            self._load_data()
            
            logger.info(f"MemoryVectorStore initialized with {len(self.embeddings)} chunks")
            
        except Exception as e:
            logger.error(f"Error initializing MemoryVectorStore: {e}")
            raise
    
    async def add_document_chunks(self, chunks: List[DocumentChunk], document_metadata: Dict = None) -> bool:
        """Add document chunks to the in-memory vector store"""
        try:
            if not chunks:
                logger.warning("No chunks to add")
                return False
            
            # Prepare data
            chunk_texts = [chunk.content for chunk in chunks]
            chunk_ids = [chunk.chunk_id for chunk in chunks]
            
            # Generate embeddings using cloud service
            logger.info(f"Generating cloud embeddings for {len(chunk_texts)} chunks...")
            embeddings = await self.embedding_service.encode_batch(chunk_texts)
            
            # Store in memory
            for i, chunk in enumerate(chunks):
                chunk_id = chunk.chunk_id
                
                # Store embedding
                self.embeddings[chunk_id] = embeddings[i]
                
                # Store document text
                self.documents[chunk_id] = chunk.content
                
                # Store metadata
                chunk_metadata = {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "char_count": len(chunk.content),
                    "word_count": len(chunk.content.split()),
                    "created_at": datetime.now().isoformat(),
                    "embedding_service": "cloud",
                    "vector_store": "memory"
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
                
                self.metadatas[chunk_id] = chunk_metadata
                
                # Update document index
                if chunk.document_id not in self.document_index:
                    self.document_index[chunk.document_id] = []
                self.document_index[chunk.document_id].append(chunk_id)
            
            # Save to disk
            self._save_data()
            
            logger.info(f"Successfully added {len(chunks)} chunks to memory vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding chunks to memory vector store: {e}")
            return False
    
    async def search_similar_chunks(
        self, 
        query: str, 
        n_results: int = 5,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using cosine similarity"""
        try:
            if not self.embeddings:
                logger.warning("No embeddings in memory vector store")
                return []
            
            # Generate query embedding
            query_embedding = await self.embedding_service.encode_text(query)
            
            # Filter chunks by document IDs if specified
            candidate_chunk_ids = []
            if document_ids:
                for doc_id in document_ids:
                    if doc_id in self.document_index:
                        candidate_chunk_ids.extend(self.document_index[doc_id])
            else:
                candidate_chunk_ids = list(self.embeddings.keys())
            
            if not candidate_chunk_ids:
                logger.warning("No candidate chunks found")
                return []
            
            # Calculate similarities using simple dot product
            similarities = []
            for chunk_id in candidate_chunk_ids:
                if chunk_id in self.embeddings:
                    chunk_embedding = self.embeddings[chunk_id]
                    # Simple dot product similarity (normalized)
                    similarity = self._dot_product_similarity(query_embedding, chunk_embedding)
                    similarities.append((chunk_id, similarity))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Format results
            formatted_results = []
            for i, (chunk_id, similarity) in enumerate(similarities[:n_results]):
                formatted_results.append({
                    "content": self.documents[chunk_id],
                    "metadata": self.metadatas[chunk_id],
                    "similarity_score": float(similarity),
                    "distance": float(1 - similarity),
                    "rank": i + 1
                })
            
            logger.info(f"Found {len(formatted_results)} similar chunks using memory vector store")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching memory vector store: {e}")
            return []
    
    def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            if document_id not in self.document_index:
                logger.warning(f"No chunks found for document {document_id}")
                return False
            
            chunk_ids = self.document_index[document_id]
            
            # Remove from all storage
            for chunk_id in chunk_ids:
                self.embeddings.pop(chunk_id, None)
                self.documents.pop(chunk_id, None)
                self.metadatas.pop(chunk_id, None)
            
            # Remove from document index
            del self.document_index[document_id]
            
            # Save to disk
            self._save_data()
            
            logger.info(f"Deleted {len(chunk_ids)} chunks for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document chunks: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        try:
            total_chunks = len(self.embeddings)
            
            # Analyze document types and sources
            doc_types = {}
            doc_sources = {}
            
            for metadata in self.metadatas.values():
                doc_type = metadata.get("document_type", "unknown")
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                filename = metadata.get("original_filename", "unknown")
                doc_sources[filename] = doc_sources.get(filename, 0) + 1
            
            return {
                "total_chunks": total_chunks,
                "embedding_model": self.embedding_service.model,
                "embedding_dimension": self.embedding_service.embedding_dimension,
                "embedding_service": "cloud",
                "vector_store": "memory",
                "document_types": doc_types,
                "document_sources": list(doc_sources.keys())[:10],
                "collection_name": "memory_documents"
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"error": str(e)}
    
    def reset_collection(self) -> bool:
        """Reset the entire collection"""
        try:
            self.embeddings.clear()
            self.documents.clear()
            self.metadatas.clear()
            self.document_index.clear()
            
            # Save empty state
            self._save_data()
            
            logger.info("Memory vector store reset successfully")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False
    
    def _save_data(self):
        """Save data to disk for persistence"""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            data = {
                "embeddings": self.embeddings,
                "documents": self.documents,
                "metadatas": self.metadatas,
                "document_index": self.document_index
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved {len(self.embeddings)} chunks to disk")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def _load_data(self):
        """Load data from disk"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                
                self.embeddings = data.get("embeddings", {})
                self.documents = data.get("documents", {})
                self.metadatas = data.get("metadatas", {})
                self.document_index = data.get("document_index", {})
                
                logger.info(f"Loaded {len(self.embeddings)} chunks from disk")
            else:
                logger.info("No existing data found")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            # Initialize empty
            self.embeddings = {}
            self.documents = {}
            self.metadatas = {}
            self.document_index = {}
    
    def _dot_product_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity using dot product (no numpy required)"""
        try:
            if len(vec1) != len(vec2):
                return 0.0
            
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            
            # Calculate magnitudes
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5
            
            # Avoid division by zero
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            # Return cosine similarity
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

# Create global instance
memory_vector_store = MemoryVectorStore()
