#!/usr/bin/env python3
"""
Deployment script for minimal Vercel deployment
This script helps verify the deployment will work with minimal dependencies
"""

import os
import sys
import subprocess
import tempfile
import shutil

def check_deployment_size():
    """Check the size of the deployment package"""
    try:
        # Create a temporary directory to simulate deployment
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy essential files
            essential_files = [
                'api/',
                'app/',
                'requirements.txt',
                'vercel.json',
                '.vercelignore'
            ]
            
            for item in essential_files:
                src = os.path.join('.', item)
                dst = os.path.join(temp_dir, item)
                if os.path.exists(src):
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            
            # Calculate total size
            total_size = 0
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            size_mb = total_size / (1024 * 1024)
            print(f"📦 Deployment package size: {size_mb:.2f} MB")
            
            if size_mb < 50:
                print("✅ Size is well under Vercel's 250MB limit")
                return True
            elif size_mb < 250:
                print("⚠️  Size is under limit but getting close")
                return True
            else:
                print("❌ Size exceeds Vercel's 250MB limit")
                return False
                
    except Exception as e:
        print(f"❌ Error checking deployment size: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported"""
    try:
        print("🧪 Testing imports...")
        
        # Test core imports
        sys.path.append('.')
        
        from app.main import app
        print("✅ FastAPI app imported")
        
        from app.services.vector_store_memory import memory_vector_store
        print("✅ Memory vector store imported")
        
        from app.services.embedding_service_cloud import cloud_embedding_service
        print("✅ Cloud embedding service imported")
        
        from app.services.document_service import document_service
        print("✅ Document service imported")
        
        from app.services.chat_service import chat_service
        print("✅ Chat service imported")
        
        print("✅ All imports successful")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def main():
    """Main deployment check"""
    print("🚀 Vercel Minimal Deployment Check")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("❌ Import tests failed - deployment will likely fail")
        return False
    
    print()
    
    # Check size
    if not check_deployment_size():
        print("❌ Size check failed - deployment will likely fail")
        return False
    
    print()
    print("✅ All checks passed! Ready for deployment.")
    print()
    print("Next steps:")
    print("1. Set environment variables in Vercel dashboard:")
    print("   - OPENROUTER_API_KEY")
    print("   - OPENAI_API_KEY")
    print("2. Deploy with: vercel --prod")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
