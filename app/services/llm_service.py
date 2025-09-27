import httpx
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with OpenRouter LLM API"""
    
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.model = settings.openrouter_model
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate a response using OpenRouter API with retrieved document context"""
        try:
            # Build context from retrieved chunks
            context = self._build_context_from_chunks(retrieved_chunks)
            
            # Build conversation history
            conversation_context = self._build_conversation_context(conversation_history)
            
            # Create the prompt
            prompt = self._create_contextual_prompt(query, context, conversation_context)
            
            # Prepare the API request
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that answers questions based on provided document context. Always cite the source documents when referencing specific information."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Call OpenRouter API
            response = await self._call_openrouter_api(messages, max_tokens)
            
            return {
                "response": response.get("content", ""),
                "model_used": self.model,
                "tokens_used": response.get("usage", {}).get("total_tokens", 0),
                "sources": [
                    {
                        "document_id": chunk.get("metadata", {}).get("document_id", ""),
                        "filename": chunk.get("metadata", {}).get("original_filename", ""),
                        "similarity_score": chunk.get("similarity_score", 0),
                        "content_preview": chunk.get("content", "")[:200] + "..."
                    }
                    for chunk in retrieved_chunks[:3]  # Top 3 sources
                ],
                "processing_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    def _build_context_from_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved document chunks"""
        if not chunks:
            return "No relevant documents found."
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            content = chunk.get("content", "")
            filename = metadata.get("original_filename", "Unknown Document")
            
            context_part = f"""
Document {i}: {filename}
Content: {content}
---"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _build_conversation_context(self, conversation_history: Optional[List[Dict[str, str]]]) -> str:
        """Build conversation context from history"""
        if not conversation_history:
            return ""
        
        context_parts = ["Previous conversation:"]
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_parts.append(f"{role.capitalize()}: {content}")
        
        return "\n".join(context_parts)
    
    def _create_contextual_prompt(
        self, 
        query: str, 
        document_context: str, 
        conversation_context: str
    ) -> str:
        """Create a contextual prompt for the LLM"""
        prompt_parts = []
        
        if conversation_context:
            prompt_parts.append(conversation_context)
            prompt_parts.append("\n" + "="*50 + "\n")
        
        prompt_parts.extend([
            "Based on the following documents, please answer the user's question.",
            "If the answer is not in the documents, say so clearly.",
            "Always cite which document(s) you're referencing.",
            "\nDOCUMENTS:",
            document_context,
            "\nQUESTION:",
            query,
            "\nPlease provide a helpful and accurate answer based on the documents above:"
        ])
        
        return "\n".join(prompt_parts)
    
    async def _call_openrouter_api(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int
    ) -> Dict[str, Any]:
        """Call the OpenRouter API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Document Chat System"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": False
            }
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"OpenRouter API error {response.status_code}: {error_detail}")
                raise Exception(f"OpenRouter API error: {response.status_code}")
            
            result = response.json()
            
            if "choices" not in result or not result["choices"]:
                raise Exception("No response choices from OpenRouter API")
            
            return {
                "content": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {})
            }
            
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise Exception(f"Network error calling OpenRouter: {str(e)}")
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {str(e)}")
            raise
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

# Create global instance
llm_service = LLMService()