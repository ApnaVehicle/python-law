#!/usr/bin/env python3
"""
Migration script to switch from local embeddings to cloud embeddings
This script helps migrate existing data to use the new cloud-based embedding service
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.vector_store_cloud import cloud_vector_store
from app.services.embedding_service_cloud import cloud_embedding_service

logger = logging.getLogger(__name__)

async def migrate_existing_data():
    """Migrate existing ChromaDB data to use cloud embeddings"""
    try:
        logger.info("Starting migration to cloud embeddings...")
        
        # Check if we have existing data
        stats = cloud_vector_store.get_collection_stats()
        total_chunks = stats.get("total_chunks", 0)
        
        if total_chunks == 0:
            logger.info("No existing data to migrate")
            return
        
        logger.info(f"Found {total_chunks} existing chunks to migrate")
        
        # Get all existing chunks
        all_chunks = cloud_vector_store.collection.get(include=["documents", "metadatas"])
        
        if not all_chunks.get("documents"):
            logger.info("No documents found to migrate")
            return
        
        # Check if chunks already have cloud embeddings
        sample_metadata = all_chunks["metadatas"][0] if all_chunks["metadatas"] else {}
        if sample_metadata.get("embedding_service") == "cloud":
            logger.info("Data already migrated to cloud embeddings")
            return
        
        logger.info("Starting migration process...")
        
        # Process in batches to avoid memory issues
        batch_size = 50
        total_batches = (len(all_chunks["documents"]) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(all_chunks["documents"]))
            
            batch_documents = all_chunks["documents"][start_idx:end_idx]
            batch_ids = all_chunks["ids"][start_idx:end_idx]
            batch_metadatas = all_chunks["metadatas"][start_idx:end_idx]
            
            logger.info(f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch_documents)} chunks)")
            
            # Generate new cloud embeddings
            new_embeddings = await cloud_embedding_service.encode_batch(batch_documents)
            
            # Update metadata to indicate cloud embeddings
            updated_metadatas = []
            for metadata in batch_metadatas:
                metadata["embedding_service"] = "cloud"
                metadata["migrated_at"] = "2024-01-01T00:00:00"  # You can update this timestamp
                updated_metadatas.append(metadata)
            
            # Update the chunks in ChromaDB
            cloud_vector_store.collection.update(
                ids=batch_ids,
                embeddings=new_embeddings,
                metadatas=updated_metadatas
            )
            
            logger.info(f"Updated batch {batch_idx + 1} with cloud embeddings")
        
        logger.info("Migration completed successfully!")
        
        # Verify migration
        final_stats = cloud_vector_store.get_collection_stats()
        logger.info(f"Final stats: {final_stats}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

async def test_cloud_embeddings():
    """Test the cloud embedding service"""
    try:
        logger.info("Testing cloud embedding service...")
        
        test_texts = [
            "This is a test document about Indian law.",
            "The Supreme Court of India has jurisdiction over constitutional matters.",
            "Section 420 of the Indian Penal Code deals with cheating."
        ]
        
        # Test single embedding
        single_embedding = await cloud_embedding_service.encode_text(test_texts[0])
        logger.info(f"Single embedding dimension: {len(single_embedding)}")
        
        # Test batch embeddings
        batch_embeddings = await cloud_embedding_service.encode_batch(test_texts)
        logger.info(f"Batch embeddings: {len(batch_embeddings)} embeddings, each with {len(batch_embeddings[0])} dimensions")
        
        # Test vector search
        search_results = await cloud_vector_store.search_similar_chunks(
            query="What is the Indian Penal Code?",
            n_results=3
        )
        logger.info(f"Search test returned {len(search_results)} results")
        
        logger.info("Cloud embedding service test completed successfully!")
        
    except Exception as e:
        logger.error(f"Cloud embedding test failed: {e}")
        raise

async def main():
    """Main migration function"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Test cloud embeddings first
        await test_cloud_embeddings()
        
        # Migrate existing data
        await migrate_existing_data()
        
        logger.info("Migration process completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
