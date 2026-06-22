# app/history.py
import hashlib
import json
import os
from typing import Dict, Any, Tuple, Optional

def calculate_sha256(text: str) -> str:
    """
    Computes a cryptographic SHA-256 hex string for the provided text.
    """
    if not text:
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

class HistoryManager:
    def __init__(self, history_path: str = "storage/crawl_history.json"):
        self.history_path = history_path
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        self.history = self._load_history()

    def _load_history(self) -> dict:
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {"pages": {}, "assets_cache": {}}

    def _save_history(self):
        try:
            with open(self.history_path, "w") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"[-] Failed to save crawl history: {e}")

    def get_sync_status(self, url: str, live_content: str, live_html: str) -> dict:
        """
        Evaluate live content and raw DOM hashes against history.
        Returns:
            dict: {
                "sync_type": "Full Sync" | "Incremental Delta Sync",
                "change_detected": bool,
                "optimization_signal": "NO_CHANGE" | "CHANGES_DETECTED" | None,
                "delta": dict,
                "content_hash": str,
                "dom_hash": str,
                "old_entry": dict or None
            }
        """
        content_hash = calculate_sha256(live_content)
        dom_hash = calculate_sha256(live_html)
        
        pages = self.history.setdefault("pages", {})
        
        if url not in pages:
            return {
                "sync_type": "Full Sync",
                "change_detected": True,
                "optimization_signal": None,
                "delta": {},
                "content_hash": content_hash,
                "dom_hash": dom_hash,
                "old_entry": None
            }
            
        old_entry = pages[url]
        old_content_hash = old_entry.get("content_hash")
        old_dom_hash = old_entry.get("dom_hash")
        
        if content_hash == old_content_hash and dom_hash == old_dom_hash:
            return {
                "sync_type": "Incremental Delta Sync",
                "change_detected": False,
                "optimization_signal": "NO_CHANGE",
                "delta": {},
                "content_hash": content_hash,
                "dom_hash": dom_hash,
                "old_entry": old_entry
            }
            
        return {
            "sync_type": "Incremental Delta Sync",
            "change_detected": True,
            "optimization_signal": "CHANGES_DETECTED",
            "delta": {},  # Will be computed using compute_delta
            "content_hash": content_hash,
            "dom_hash": dom_hash,
            "old_entry": old_entry
        }

    def compute_delta(self, old_data: dict, new_data: dict) -> dict:
        """
        Compare individual fields to isolate modified fields (delta extraction).
        """
        delta = {}
        fields = ["title", "description", "content", "canonical_url", "charset", "keywords"]
        for f in fields:
            old_val = old_data.get(f)
            new_val = new_data.get(f)
            if old_val != new_val:
                delta[f] = {
                    "old": old_val,
                    "new": new_val
                }
                
        complex_fields = ["links", "headings_list", "tables", "internal_links", "external_links", "download_links"]
        for f in complex_fields:
            old_val = old_data.get(f, [])
            new_val = new_data.get(f, [])
            if old_val != new_val:
                delta[f] = {
                    "old": old_val,
                    "new": new_val
                }
        return delta

    def get_cached_asset(self, asset_url: str) -> Optional[dict]:
        """
        Retrieve asset from global cache.
        """
        assets_cache = self.history.setdefault("assets_cache", {})
        return assets_cache.get(asset_url)

    def save_page_record(self, url: str, content_hash: str, dom_hash: str, page_data: dict, assets: list):
        """
        Update crawl history with the scraped page metadata and assets.
        """
        pages = self.history.setdefault("pages", {})
        assets_cache = self.history.setdefault("assets_cache", {})
        
        # Save page level assets and update global cache versioning
        page_assets = {}
        for asset in assets:
            url_ref = asset.get("original_url")
            if url_ref:
                # Retrieve from global cache to check version
                cached = assets_cache.get(url_ref)
                if cached:
                    version = cached.get("version", 1) + 1
                else:
                    version = asset.get("version", 1)
                
                asset_copy = dict(asset)
                asset_copy["version"] = version
                
                # Update global cache and record on page
                assets_cache[url_ref] = asset_copy
                page_assets[url_ref] = asset_copy

        pages[url] = {
            "content_hash": content_hash,
            "dom_hash": dom_hash,
            "title": page_data.get("title"),
            "description": page_data.get("description"),
            "content": page_data.get("content"),
            "canonical_url": page_data.get("canonical_url"),
            "charset": page_data.get("charset"),
            "keywords": page_data.get("keywords", []),
            "links": page_data.get("links", []),
            "headings_list": page_data.get("headings_list", []),
            "tables": page_data.get("tables", []),
            "internal_links": page_data.get("internal_links", []),
            "external_links": page_data.get("external_links", []),
            "download_links": page_data.get("download_links", []),
            "assets": page_assets,
            "full_scrape_result": page_data
        }
        
        self._save_history()
