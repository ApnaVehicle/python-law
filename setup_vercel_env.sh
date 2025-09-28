#!/bin/bash

echo "🚀 Setting up Vercel Environment Variables"
echo "=========================================="

echo ""
echo "This script will help you set up the required environment variables for your Vercel deployment."
echo ""

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Please install it first:"
    echo "   npm install -g vercel"
    exit 1
fi

echo "✅ Vercel CLI found"
echo ""

# Set required environment variables
echo "Setting up required environment variables..."
echo ""

echo "1. Setting OPENROUTER_API_KEY..."
vercel env add OPENROUTER_API_KEY

echo ""
echo "2. Setting OPENAI_API_KEY..."
vercel env add OPENAI_API_KEY

echo ""
echo "3. Setting optional environment variables..."

# Set optional variables with defaults
vercel env add OPENROUTER_MODEL production <<< "anthropic/claude-3-haiku"
vercel env add EMBEDDING_MODEL production <<< "text-embedding-3-small"
vercel env add USE_CLOUD_EMBEDDINGS production <<< "true"
vercel env add ENVIRONMENT production <<< "production"
vercel env add DEBUG production <<< "false"

echo ""
echo "✅ Environment variables set successfully!"
echo ""
echo "🚀 Deploying to production..."
vercel --prod

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Test your API:"
echo "curl https://your-app.vercel.app/health"
echo ""
echo "Note: You may still see authentication page due to deployment protection."
echo "To disable it: Go to Vercel Dashboard > Project Settings > Security > Disable Deployment Protection"
