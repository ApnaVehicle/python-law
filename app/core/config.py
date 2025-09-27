# =====================================================
# app/core/config.py
import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3-haiku"
    
    # File Upload Settings
    upload_dir: str = "./uploads"
    max_file_size: int = 50000000  # 50MB
    allowed_extensions: Union[List[str], str] = ["pdf", "docx", "txt"]
    
    # ChromaDB Settings
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "documents"
    
    # App Settings
    environment: str = "development"
    debug: bool = True
    
    @field_validator('allowed_extensions', mode='before')
    @classmethod
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            # Handle comma-separated string from environment variable
            return [ext.strip() for ext in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()