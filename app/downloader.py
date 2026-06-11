# app/downloader.py
import os
import requests
import mimetypes

class AssetDownloader:
    def __init__(self):
        # Establish point path to our local storage directory layer
        self.output_dir = "storage/assets"
        os.makedirs(self.output_dir, exist_ok=True)

    def download_asset(self, url: str) -> dict:
        """
        Streams binary data streams over HTTP, writes content securely to disk,
        and generates required file property tracing records.
        """
        try:
            # Request file download with a 10-second timeout safety trigger
            response = requests.get(url, timeout=10, stream=True)
            
            if response.status_code == 200:
                # Isolate the clean file name from the web link string structure
                file_name = url.split("/")[-1].split("?")[0]
                if not file_name or "." not in file_name:
                    file_name = "downloaded_asset.png" # default fallback signature
                
                local_path = os.path.join(self.output_dir, file_name)
                
                # Write raw binary data stream directly to laptop drive
                with open(local_path, "wb") as f:
                    f.write(response.content)

                # Fetch mechanical properties required by project rules
                file_size = os.path.getsize(local_path)
                mime_type, _ = mimetypes.guess_type(local_path)
                
                return {
                    "original_url": url,
                    "local_path": local_path,
                    "mime_type": mime_type or "application/octet-stream",
                    "file_size": file_size
                }
        except Exception:
            pass # Suppress failed drop links so they do not crash execution threads
        return None