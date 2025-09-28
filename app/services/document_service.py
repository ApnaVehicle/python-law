# app/services/document_service.py
import os
import uuid
import json  # ADDED: Missing import
import aiofiles
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException
import logging

from app.core.config import settings
from app.utils.file_processors import FileProcessor
from app.models.document import Document, DocumentStatus, DocumentMetadata, DocumentChunk

logger = logging.getLogger(__name__)

class DocumentService:
    """Service for handling document operations"""
    
    def __init__(self):
        self.file_processor = FileProcessor()
        self.documents: Dict[str, Document] = {}
        
        # Handle serverless environments (read-only file system)
        try:
            self.storage_file = os.path.join(settings.chroma_persist_directory, "documents.json")
            # Test if we can write to the directory
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            self.is_serverless = False
        except OSError as e:
            if "Read-only file system" in str(e) or e.errno == 30:
                # Use temporary directory for serverless
                import tempfile
                self.storage_file = os.path.join(tempfile.gettempdir(), "documents.json")
                self.is_serverless = True
                logger.info("Running in serverless mode - using temporary storage")
            else:
                raise
        
        # Load existing documents on startup
        self._load_documents()

    async def upload_and_process_document(self, file: UploadFile) -> Document:
        """Upload and process a document file"""
        document_id = None
        file_path = None
        
        try:
            logger.info(f"Starting document upload: {file.filename}")
            
            # Validate file
            self._validate_file(file)
            
            # Generate unique filename and document ID
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Handle serverless environments
            if self.is_serverless:
                import tempfile
                file_path = os.path.join(tempfile.gettempdir(), unique_filename)
            else:
                file_path = os.path.join(settings.upload_dir, unique_filename)
            
            document_id = str(uuid.uuid4())
            
            # Create document metadata
            metadata = DocumentMetadata(
                filename=unique_filename,
                original_filename=file.filename,
                file_size=0,  # Will be updated after saving
                document_type=self._get_document_type(file_extension),
                upload_timestamp=datetime.now()
            )
            
            # Create document object
            document = Document(
                document_id=document_id,
                status=DocumentStatus.UPLOADING,
                metadata=metadata
            )
            
            # Store document
            self.documents[document_id] = document
            logger.info(f"Document created with ID: {document_id}")
            
            # Save file
            await self._save_file(file, file_path)
            
            # Update file size
            file_stats = os.stat(file_path)
            document.metadata.file_size = file_stats.st_size
            logger.info(f"File saved, size: {file_stats.st_size} bytes")
            
            # Update status to processing
            document.status = DocumentStatus.PROCESSING
            
            # Process the file
            logger.info("Starting file processing...")
            processed_data = self.file_processor.process_file(file_path, file.filename)
            logger.info(f"File processed, created {len(processed_data['chunks'])} chunks")
            
            # Create document chunks
            chunks = [
                DocumentChunk(**chunk_data) 
                for chunk_data in processed_data["chunks"]
            ]
            
            # Update document with processed data
            document.chunks = chunks
            document.metadata.processing_timestamp = datetime.now()
            document.metadata.page_count = processed_data["metadata"].get("page_count")
            document.metadata.word_count = processed_data["metadata"]["word_count"]
            
            # Try to add to vector store
            try:
                logger.info("Adding chunks to vector store...")
                from app.services.vector_store_memory import memory_vector_store
                
                # Prepare document metadata for vector store
                document_metadata_dict = {
                    "original_filename": document.metadata.original_filename,
                    "document_type": document.metadata.document_type,
                    "upload_timestamp": document.metadata.upload_timestamp.isoformat()
                }
                
                success = await memory_vector_store.add_document_chunks(chunks, document_metadata_dict)
                
                if success:
                    document.status = DocumentStatus.READY
                    logger.info(f"Document processing completed successfully: {document_id}")
                else:
                    # Even if vector store fails, keep document in READY state
                    # This allows us to debug and retry later
                    document.status = DocumentStatus.READY
                    logger.warning("Vector store operation failed, but document is still usable")
                
            except Exception as vector_error:
                logger.error(f"Vector store error: {str(vector_error)}")
                # Don't fail the entire upload, just mark with warning
                document.status = DocumentStatus.READY
                document.error_message = f"Vector store warning: {str(vector_error)}"
            
            # FIXED: Save documents after successful processing
            self._save_documents()
            return document
                
        except Exception as e:
            logger.error(f"Error in upload_and_process_document: {str(e)}")
            
            # Cleanup on error
            if document_id and document_id in self.documents:
                if self.documents[document_id].status != DocumentStatus.READY:
                    self.documents[document_id].status = DocumentStatus.ERROR
                    self.documents[document_id].error_message = str(e)
            
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {cleanup_error}")
            
            raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        return self.documents.get(document_id)
    
    def get_all_documents(self) -> List[Document]:
        """Get all documents"""
        return list(self.documents.values())
    
    def get_ready_documents(self) -> List[Document]:
        """Get all documents that are ready for querying"""
        return [doc for doc in self.documents.values() if doc.status == DocumentStatus.READY]
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its file"""
        document = self.documents.get(document_id)
        if not document:
            return False
        
        # Delete from vector store first
        try:
            from app.services.vector_store_memory import memory_vector_store
            memory_vector_store.delete_document_chunks(document_id)
            logger.info(f"Deleted chunks from vector store for document: {document_id}")
        except Exception as e:
            logger.error(f"Error deleting from vector store: {e}")
        
        # Delete physical file
        try:
            file_path = os.path.join(settings.upload_dir, document.metadata.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
        
        # Remove from memory
        del self.documents[document_id]
        logger.info(f"Document deleted: {document_id}")
        
        # FIXED: Save documents after deletion
        self._save_documents()
        return True
    
    def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file"""
        if not file.filename:
            raise ValueError("No filename provided")
        
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if file_extension not in settings.allowed_extensions:
            raise ValueError(f"File type '{file_extension}' not allowed. Allowed types: {settings.allowed_extensions}")
    
    def _get_document_type(self, file_extension: str):
        """Get document type from file extension"""
        extension_map = {
            ".pdf": "pdf",
            ".docx": "docx", 
            ".txt": "txt"
        }
        return extension_map.get(file_extension.lower(), "unknown")
    
    async def _save_file(self, file: UploadFile, file_path: str) -> None:
        """Save uploaded file to disk"""
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                
                # Check file size
                if len(content) > settings.max_file_size:
                    raise ValueError(f"File size exceeds maximum allowed size of {settings.max_file_size} bytes")
                
                await f.write(content)
        except Exception as e:
            # Clean up partial file if exists
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e

    def _save_documents(self):
        """Save documents to disk"""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            # Convert documents to dict for JSON serialization
            docs_dict = {}
            for doc_id, doc in self.documents.items():
                docs_dict[doc_id] = doc.model_dump()
            
            with open(self.storage_file, 'w') as f:
                json.dump(docs_dict, f, default=str, indent=2)
                
            logger.info(f"Saved {len(self.documents)} documents to storage")
        except Exception as e:
            logger.error(f"Error saving documents: {e}")
    
    def _load_documents(self):
        """Load documents from disk"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    docs_dict = json.load(f)
                
                # Convert back to Document objects
                for doc_id, doc_data in docs_dict.items():
                    # Parse datetime strings back to datetime objects
                    if doc_data.get("metadata", {}).get("upload_timestamp"):
                        doc_data["metadata"]["upload_timestamp"] = datetime.fromisoformat(
                            doc_data["metadata"]["upload_timestamp"].replace("Z", "+00:00")
                        )
                    if doc_data.get("metadata", {}).get("processing_timestamp"):
                        doc_data["metadata"]["processing_timestamp"] = datetime.fromisoformat(
                            doc_data["metadata"]["processing_timestamp"].replace("Z", "+00:00")
                        )
                    
                    self.documents[doc_id] = Document(**doc_data)
                
                logger.info(f"Loaded {len(self.documents)} documents from storage")
            else:
                logger.info("No existing document storage found")
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            self.documents = {}

# Create global instance
document_service = DocumentService()