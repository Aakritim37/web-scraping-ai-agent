# app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime, timezone

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
    width: Optional[int] = None
    height: Optional[int] = None
    healthy: Optional[bool] = True
    issue: Optional[str] = None
    version: int = 1

class ScrapeResultSchema(BaseModel):
    """
    The master blueprint for our scraping output. 
    This exactly matches your mentor's required structural layout contract.
    """
    status: str = Field(..., description="success | partial | failed")
    failure_reason: Optional[str] = None
    failure_category: Optional[str] = None
    error_screenshot_path: Optional[str] = None
    is_paywalled: bool = False
    paywall_provider: Optional[str] = None
    paywall_percentage: float = 0.0
    paywall_teaser_text: Optional[str] = None
    robots_content: Optional[str] = None
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    images: List[AssetSchema] = []
    documents: List[AssetSchema] = []
    links: List[str] = []
    metadata: Dict[str, Any] = {}
    telemetry: Dict[str, Any] = {}
    screenshots: List[str] = []
    logs: List[Dict[str, Any]] = []
    quality_score: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Technical & SEO Metadata additions
    canonical_url: Optional[str] = None
    keywords: List[str] = []
    charset: Optional[str] = None
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = {}
    language: Optional[str] = None
    forms: Optional[List[Dict[str, Any]]] = []
    buttons: Optional[List[Dict[str, Any]]] = []
    breadcrumbs: Optional[List[str]] = []
    footer_content: Optional[str] = None
    
    # Tabular Data addition (elevated to top-level)
    tables: List[Dict[str, Any]] = []

    # Hyperlink processing additions
    internal_links: List[str] = []
    external_links: List[str] = []
    redirect_chain: List[Dict[str, Any]] = []
    verified_links: List[Dict[str, Any]] = []
    download_links: List[str] = []

    # Media Asset Pipeline additions
    logos: List[AssetSchema] = []
    svgs: List[str] = []
    videos: List[AssetSchema] = []

    # Multi-Viewport screenshot additions
    desktop_above_fold: Optional[str] = None
    mobile_view: Optional[str] = None
    tablet_view: Optional[str] = None

class ScraperConfigSchema(BaseModel):
    """
    Validation schema for scraping configuration input parameter.
    Ensures input parameters are strictly configured.
    """
    browser_engine: Literal["chromium", "firefox", "webkit"] = "chromium"