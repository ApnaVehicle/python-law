# API Testing Guide

## ✅ Your API is Working Perfectly!

Your FastAPI chat backend is now running locally and all endpoints are functional.

## Local Testing (Recommended for Development)

### 1. Start Local Server
```bash
cd /Users/suryodayvadlamani/Projects/chat-backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Test All Endpoints

#### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```
**Response**: `{"status":"healthy"}`

#### Root Endpoint
```bash
curl -X GET "http://localhost:8000/"
```
**Response**: API information and features

#### List Conversations
```bash
curl -X GET "http://localhost:8000/api/v1/chat/conversations"
```
**Response**: List of all chat conversations

#### Send Chat Message
```bash
curl -X POST "http://localhost:8000/api/v1/chat/message" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?", "session_id": "test-123"}'
```

#### List All Sessions
```bash
curl -X GET "http://localhost:8000/api/v1/chat/sessions"
```

#### Get Session History
```bash
curl -X GET "http://localhost:8000/api/v1/chat/sessions/{session_id}/history"
```

#### Document Endpoints
```bash
# List all documents
curl -X GET "http://localhost:8000/api/v1/documents/"

# Get document by ID
curl -X GET "http://localhost:8000/api/v1/documents/{document_id}"
```

## Production Testing (Vercel Deployment)

### Issue: Deployment Protection
Your Vercel deployment has **deployment protection** enabled, which requires authentication.

### Solutions:

#### Option 1: Disable Deployment Protection (Recommended)
1. Go to your Vercel dashboard
2. Navigate to your project settings
3. Go to "Security" tab
4. Disable "Deployment Protection"
5. Redeploy: `vercel --prod`

#### Option 2: Use Authentication Bypass Token
1. Get bypass token from Vercel dashboard
2. Use in requests:
```bash
curl -X GET "https://your-app.vercel.app/api/v1/chat/conversations?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=YOUR_TOKEN"
```

#### Option 3: Test via Browser
1. Open browser
2. Go to: https://chat-backend-aaoweup2d-apnavehicles-projects.vercel.app
3. Authenticate with Vercel
4. Test endpoints

## Environment Variables Setup

### For Local Development
Create a `.env` file:
```bash
OPENROUTER_API_KEY=your_openrouter_key
OPENAI_API_KEY=your_openai_key
OPENROUTER_MODEL=anthropic/claude-3-haiku
EMBEDDING_MODEL=text-embedding-3-small
USE_CLOUD_EMBEDDINGS=true
ENVIRONMENT=development
DEBUG=true
```

### For Vercel Production
Set in Vercel dashboard:
```bash
OPENROUTER_API_KEY=your_openrouter_key
OPENAI_API_KEY=your_openai_key
OPENROUTER_MODEL=anthropic/claude-3-haiku
EMBEDDING_MODEL=text-embedding-3-small
USE_CLOUD_EMBEDDINGS=true
ENVIRONMENT=production
DEBUG=false
```

## API Endpoints Summary

### Chat Endpoints
- `GET /api/v1/chat/conversations` - List conversations
- `GET /api/v1/chat/sessions` - List all sessions
- `GET /api/v1/chat/sessions/{session_id}` - Get specific session
- `GET /api/v1/chat/sessions/{session_id}/history` - Get session history
- `POST /api/v1/chat/message` - Send chat message
- `POST /api/v1/chat/sessions/start` - Start new session
- `DELETE /api/v1/chat/sessions/{session_id}` - Delete session

### Document Endpoints
- `GET /api/v1/documents/` - List all documents
- `GET /api/v1/documents/{document_id}` - Get specific document
- `POST /api/v1/documents/upload` - Upload document
- `DELETE /api/v1/documents/{document_id}` - Delete document

### Utility Endpoints
- `GET /` - API information
- `GET /health` - Health check

## Testing with Different Tools

### 1. cURL (Command Line)
```bash
# Test conversations endpoint
curl -X GET "http://localhost:8000/api/v1/chat/conversations"

# Test chat message
curl -X POST "http://localhost:8000/api/v1/chat/message" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the Indian Penal Code?", "session_id": "test-123"}'
```

### 2. Postman
- Import the endpoints
- Set base URL: `http://localhost:8000`
- Test all endpoints

### 3. Browser
- Open: `http://localhost:8000/docs` for Swagger UI
- Interactive API documentation

### 4. Python Requests
```python
import requests

# Test conversations
response = requests.get("http://localhost:8000/api/v1/chat/conversations")
print(response.json())

# Test chat message
response = requests.post(
    "http://localhost:8000/api/v1/chat/message",
    json={"message": "Hello", "session_id": "test-123"}
)
print(response.json())
```

## Troubleshooting

### Common Issues

1. **Port 8000 already in use**
   ```bash
   # Kill existing process
   lsof -ti:8000 | xargs kill -9
   
   # Or use different port
   python3 -m uvicorn app.main:app --port 8001
   ```

2. **Environment variables not loaded**
   - Check `.env` file exists
   - Restart the server after adding variables

3. **API key errors**
   - Verify API keys are correct
   - Check API key permissions

4. **Import errors**
   - Run: `python3 deploy_minimal.py` to verify setup

## Success Indicators

✅ **Local server starts without errors**
✅ **Health endpoint returns 200**
✅ **Conversations endpoint returns data**
✅ **Chat endpoint responds to messages**
✅ **All endpoints accessible**

## Next Steps

1. **Continue local development** using `http://localhost:8000`
2. **Disable Vercel deployment protection** for production testing
3. **Set up environment variables** in Vercel dashboard
4. **Test production endpoints** after disabling protection

Your API is working perfectly! 🎉
