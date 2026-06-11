# app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class AssetSchema(BaseModel):
    """
    Blueprint for saving files like images and documents.
    Every asset must keep track of these specific details.
    """
    original_url: str
    local_path: str
    mime_type: str
    file_size: int
    alt_text: Optional[str] = None

class ScrapeResultSchema(BaseModel):
    """
    The master blueprint for our scraping output. 
    This exactly matches your mentor's required structural layout contract.
    """
    status: str = Field(..., description="success | partial | failed")
    failure_reason: Optional[str] = None
    failure_category: Optional[str] = None
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    images: List[AssetSchema] = []
    documents: List[AssetSchema] = []
    links: List[str] = []
    metadata: Dict[str, Any] = {}
    screenshots: List[str] = []
    logs: List[Dict[str, Any]] = []
    quality_score: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())