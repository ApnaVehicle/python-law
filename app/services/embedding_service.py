# app/services/embedding_service.py
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with a sentence transformer model
        
        all-MiniLM-L6-v2: Fast, good quality, 384 dimensions
        Alternative: all-mpnet-base-v2 (slower but better quality, 768 dim)
        """
        try:
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Loaded embedding model: {model_name} (dim: {self.embedding_dimension})")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            raise
    
    def encode_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            raise
    
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False, batch_size=32)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error encoding batch: {e}")
            raise
    
    def get_embedding_info(self) -> Dict[str, Any]:
        """Get information about the embedding model"""
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "max_sequence_length": self.model.max_seq_length
        }