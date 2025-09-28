# app/services/embedding_service_cloud.py
import httpx
from typing import List, Dict, Any
import logging
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

class CloudEmbeddingService:
    """Cloud-based embedding service using OpenAI API"""
    
    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        """Initialize with OpenAI API credentials
        
        Args:
            api_key: OpenAI API key (if None, will use settings)
            model: Embedding model to use (text-embedding-3-small is fast and cheap)
        """
        self.api_key = api_key or settings.openrouter_api_key  # Using same key for now
        self.model = model
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.embedding_dimension = 1536  # text-embedding-3-small dimension
        
        logger.info(f"Initialized CloudEmbeddingService with model: {model}")
    
    async def encode_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            embeddings = await self.encode_batch([text])
            return embeddings[0] if embeddings else []
        except Exception as e:
            logger.error(f"Error encoding single text: {e}")
            raise
    
    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        try:
            if not texts:
                return []
            
            # OpenAI API has a limit of 2048 texts per request
            batch_size = 100  # Conservative batch size
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = await self._call_embedding_api(batch)
                all_embeddings.extend(batch_embeddings)
                
                # Small delay to avoid rate limiting
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            logger.info(f"Generated {len(all_embeddings)} embeddings for {len(texts)} texts")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Error encoding batch: {e}")
            raise
    
    async def _call_embedding_api(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI embedding API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "input": texts,
                "encoding_format": "float"
            }
            
            response = await self.client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"OpenAI API error {response.status_code}: {error_detail}")
                raise Exception(f"OpenAI API error: {response.status_code}")
            
            result = response.json()
            
            if "data" not in result:
                raise Exception("No embedding data from OpenAI API")
            
            # Extract embeddings in the same order as input texts
            embeddings = []
            for item in result["data"]:
                embeddings.append(item["embedding"])
            
            return embeddings
            
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise Exception(f"Network error calling OpenAI: {str(e)}")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise
    
    def get_embedding_info(self) -> Dict[str, Any]:
        """Get information about the embedding model"""
        return {
            "model_name": self.model,
            "embedding_dimension": self.embedding_dimension,
            "service_type": "cloud",
            "provider": "openai"
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

# Create global instance
cloud_embedding_service = CloudEmbeddingService()
