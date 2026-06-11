# app/main.py
import asyncio
import json
import sys
from app.browser import PlaywrightManager
from app.extractor import ContentExtractor
from app.downloader import AssetDownloader
from app.schemas import ScrapeResultSchema

async def run_prototype(url: str):
    print(f"[*] Initializing universal agent prototype target thread: {url}")
    
    browser_agent = PlaywrightManager()
    downloader = AssetDownloader()

    try:
        # Step 1: Open page browser instance and capture HTML / Viewport Snapshots
        html_data, screenshots, browser_logs = await browser_agent.capture_page(url)
        
        # Step 2: Extract structured text elements and hyperlink nodes
        parsed_data = ContentExtractor.extract(html_data, url)

        # Step 3: Loop and download the first 2 discovered images as a proof-of-concept
        downloaded_images = []
        for img_url in parsed_data["images"][:2]: 
            # Simple filter to skip tiny tracking pixels or empty links
            if img_url.startswith("http") and not img_url.endswith(".gif"):
                print(f"[+] Downloading layout asset: {img_url}")
                asset_info = downloader.download_asset(img_url)
                if asset_info:
                    downloaded_images.append(asset_info)

        # Step 4: Compute Data Quality Score (Baseline out of 1.0)
        quality_score = 1.0
        if not parsed_data["content"] or len(parsed_data["content"].strip()) < 50:
            quality_score -= 0.5  # Penalize heavy score if body context is empty
            
        # Step 5: Bind organized elements to our strict output contract schema blueprint
        final_output = ScrapeResultSchema(
            status="success",
            url=url,
            title=parsed_data["title"],
            content=parsed_data["content"][:400] + "...", # Preview snippet summary text
            images=downloaded_images,
            links=parsed_data["links"][:5], # Keep preview bounded to first 5 paths
            metadata={"description": parsed_data["description"]},
            screenshots=screenshots,
            logs=browser_logs,
            quality_score=quality_score
        )

        # Step 6: Convert model data to JSON layout format and save file to local drive
        output_filename = "prototype_output.json"
        with open(output_filename, "w") as f:
            json.dump(final_output.dict(), f, indent=4)
            
        print(f"\n[✓] Scraping loop completed successfully! File '{output_filename}' generated.")
        print(json.dumps(final_output.dict(), indent=4))

    except Exception as e:
        print(f"[-] Execution layout error occurred: {str(e)}")

if __name__ == "__main__":
    # Check if the user provided a URL in the terminal
    if len(sys.argv) > 1:
        target_site = sys.argv[1]
    else:
        # Fallback default if you just run 'python -m app.main' without arguments
        target_site = "https://quotes.toscrape.com/js/" 
        
    asyncio.run(run_prototype(target_site))