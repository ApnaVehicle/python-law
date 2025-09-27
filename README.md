# Chat Backend

A FastAPI-based document chat system with RAG (Retrieval-Augmented Generation) capabilities.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
# Create the .env file
touch .env
```

Then add the following content to the `.env` file:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3-haiku

# File Upload Settings
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=50000000
ALLOWED_EXTENSIONS=pdf,docx,txt

# ChromaDB Settings
CHROMA_PERSIST_DIRECTORY=./data/chroma
CHROMA_COLLECTION_NAME=documents

# App Settings
ENVIRONMENT=development
DEBUG=true
```

**Important**: Replace `your_openrouter_api_key_here` with your actual OpenRouter API key.

### 3. Run the Application

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /api/v1/documents/upload` - Upload documents
- `POST /api/v1/chat/message` - Send chat messages

## Features

- Document upload and processing (PDF, DOCX, TXT)
- Vector-based document search using ChromaDB
- Chat interface with RAG capabilities
- CORS support for frontend integration
