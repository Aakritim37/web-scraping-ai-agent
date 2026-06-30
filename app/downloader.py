# app/downloader.py
import os
import requests
import mimetypes

class AssetDownloader:
    def __init__(self):
        # Create localized output directories
        self.base_output_dir = "storage/assets"
        self.output_dir = self.base_output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_output_dir, "documents"), exist_ok=True)
        os.makedirs(os.path.join(self.base_output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.base_output_dir, "videos"), exist_ok=True)

    def download_asset(self, url: str, alt_text: str = None, width: int = None, height: int = None, asset_type: str = "image") -> dict:
        """
        Streams binary data streams over HTTP, writes content securely to disk,
        and generates required file property tracing records.
        """
        try:
            # Route target directory based on type
            if asset_type == "document":
                target_dir = os.path.join(self.base_output_dir, "documents")
            elif asset_type == "video":
                target_dir = os.path.join(self.base_output_dir, "videos")
            else:
                target_dir = os.path.join(self.base_output_dir, "images")
                
            response = requests.get(url, timeout=10, stream=True)
            
            # Determine filename
            file_name = url.split("/")[-1].split("?")[0]
            if not file_name or "." not in file_name:
                if asset_type == "document":
                    file_name = "document.pdf"
                elif asset_type == "video":
                    file_name = "video.mp4"
                else:
                    file_name = "downloaded_asset.png"
                    
            local_path = os.path.join(target_dir, file_name)
            
            if response.status_code == 200:
                # Stream write
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            
                file_size = os.path.getsize(local_path)
                mime_type, _ = mimetypes.guess_type(local_path)
                
                # Fallback MIME-types
                if not mime_type:
                    if url.lower().endswith(".svg"):
                        mime_type = "image/svg+xml"
                    elif asset_type == "document":
                        mime_type = "application/pdf"
                    elif asset_type == "video":
                        mime_type = "video/mp4"
                    else:
                        mime_type = "application/octet-stream"
                        
                return {
                    "original_url": url,
                    "local_path": local_path,
                    "mime_type": mime_type,
                    "file_size": file_size,
                    "alt_text": alt_text,
                    "width": width,
                    "height": height,
                    "healthy": True,
                    "issue": None,
                    "version": 1
                }
            else:
                return {
                    "original_url": url,
                    "local_path": "",
                    "mime_type": "application/octet-stream",
                    "file_size": 0,
                    "alt_text": alt_text,
                    "width": width,
                    "height": height,
                    "healthy": False,
                    "issue": f"HTTP_STATUS_{response.status_code}",
                    "version": 1
                }
        except Exception as e:
            return {
                "original_url": url,
                "local_path": "",
                "mime_type": "application/octet-stream",
                "file_size": 0,
                "alt_text": alt_text,
                "width": width,
                "height": height,
                "healthy": False,
                "issue": str(e),
                "version": 1
            }