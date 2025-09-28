# app/main.py - Updated version with chat router
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router

# Create FastAPI app
app = FastAPI(
    title="Document Chat API",
    description="A professional document chat system with RAG capabilities",
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js default
        "http://127.0.0.1:3000",
        "https://your-nextjs-domain.com"  # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory if it doesn't exist (only in non-serverless environments)
try:
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_directory, exist_ok=True)
    # Static files for uploaded documents (only if directory creation succeeded)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
except OSError as e:
    # Handle read-only file system (e.g., Vercel serverless)
    if "Read-only file system" in str(e) or e.errno == 30:
        print(f"Warning: Cannot create directories in read-only file system: {e}")
        print("Running in serverless mode - file uploads will use temporary storage")
    else:
        raise

# Include API routes
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])

@app.get("/")
async def root():
    return {
        "message": "Document Chat API is running",
        "version": "1.0.0",
        "environment": settings.environment,
        "features": ["document_upload", "semantic_search", "ai_chat"]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )