# Vercel entry point for FastAPI
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI app from your main module
from app.main import app

# Vercel expects the app to be available as 'app'
# This is already satisfied since we're importing it from app.main
