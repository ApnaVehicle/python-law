# app/utils/text_processors.py
import re
from typing import List, Dict, Any

class TextCleaner:
    """Clean and normalize extracted text"""
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
        
        # Remove extra newlines and tabs
        text = text.replace('\n', ' ').replace('\t', ' ')
        
        # Strip and return
        return text.strip()

class TextChunker:
    """Intelligent text chunking for better retrieval"""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, document_id: str) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks"""
        if not text:
            return []
            
        # Split by sentences first (better for semantic coherence)
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            # If adding this sentence would exceed chunk size
            if len(current_chunk + sentence) > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self._create_chunk(
                    current_chunk, document_id, chunk_index
                ))
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + sentence
                chunk_index += 1
            else:
                current_chunk += sentence + " "
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(self._create_chunk(
                current_chunk, document_id, chunk_index
            ))
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting - can be improved with spaCy/NLTK
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from the end of current chunk"""
        if len(text) <= self.overlap:
            return text
        return text[-self.overlap:]
    
    def _create_chunk(self, content: str, document_id: str, chunk_index: int) -> Dict[str, Any]:
        """Create a chunk dictionary"""
        return {
            "chunk_id": f"{document_id}_chunk_{chunk_index}",
            "document_id": document_id,
            "content": content.strip(),
            "chunk_index": chunk_index,
            "metadata": {
                "char_count": len(content),
                "word_count": len(content.split())
            }
        }
