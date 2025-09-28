# Vercel Environment Variables Setup

## The Problem
Your Vercel deployment is failing because it's missing required environment variables:

```
ValidationError: 1 validation error for Settings
openrouter_api_key
Field required [type=missing, input_value={}, input_type=dict]
```

## Solution: Set Environment Variables in Vercel

### Step 1: Go to Vercel Dashboard
1. Open https://vercel.com/dashboard
2. Find your project: `chat-backend`
3. Click on it

### Step 2: Navigate to Settings
1. Click on "Settings" tab
2. Click on "Environment Variables" in the left sidebar

### Step 3: Add Required Variables
Add these environment variables one by one:

#### Required Variables:
```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

#### Optional Variables (with defaults):
```bash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3-haiku
EMBEDDING_MODEL=text-embedding-3-small
USE_CLOUD_EMBEDDINGS=true
ENVIRONMENT=production
DEBUG=false
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=50000000
ALLOWED_EXTENSIONS=pdf,docx,txt
CHROMA_PERSIST_DIRECTORY=./data/chroma
CHROMA_COLLECTION_NAME=documents
```

### Step 4: Set Environment Scope
For each variable, set:
- **Environment**: Production, Preview, Development (select all)
- **Value**: Your actual API key

### Step 5: Redeploy
After adding all variables:
```bash
vercel --prod
```

## Alternative: Use Vercel CLI

You can also set environment variables via CLI:

```bash
# Set required variables
vercel env add OPENROUTER_API_KEY
vercel env add OPENAI_API_KEY

# Set optional variables
vercel env add OPENROUTER_MODEL production
vercel env add EMBEDDING_MODEL production
vercel env add USE_CLOUD_EMBEDDINGS production
vercel env add ENVIRONMENT production
vercel env add DEBUG production

# Redeploy
vercel --prod
```

## Verification

After setting environment variables and redeploying, test:

```bash
# Test health endpoint
curl https://your-app.vercel.app/health

# Test root endpoint
curl https://your-app.vercel.app/
```

## Common Issues

### 1. Variables Not Applied
- Make sure to redeploy after adding variables
- Check that variables are set for "Production" environment

### 2. Still Getting Authentication Page
- This is normal - Vercel has deployment protection enabled
- You can disable it in Project Settings > Security

### 3. API Key Invalid
- Verify your API keys are correct
- Check that keys have proper permissions

## Quick Fix Commands

```bash
# Set the two required variables
vercel env add OPENROUTER_API_KEY
# Enter your OpenRouter API key when prompted

vercel env add OPENAI_API_KEY  
# Enter your OpenAI API key when prompted

# Redeploy
vercel --prod
```

## Testing After Fix

Once environment variables are set and deployed:

```bash
# Test the deployed API
curl https://chat-backend-aaoweup2d-apnavehicles-projects.vercel.app/health
```

The deployment should work without the validation error!
