# app/browser.py
import asyncio
import os
from playwright.async_api import async_playwright

class PlaywrightManager:
    def __init__(self):
        # Point to the local directory folders we created earlier
        self.screenshot_dir = "storage/screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)

    async def capture_page(self, url: str):
        """
        Launches browser, emulates a desktop view, captures layout metrics,
        and saves visual viewport snapshots to disk.
        """
        async with async_playwright() as p:
            # Start a real, invisible Chromium browser engine
            browser = await p.chromium.launch(headless=True)
            
            # Use a humanized device profile signature to bypass rudimentary checks
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            # An array to catch any errors or console warnings happening on the website
            browser_logs = []
            page.on("console", lambda msg: browser_logs.append({"type": msg.type, "text": msg.text}))

            try:
                # 1. Navigate to the target web page and wait for structural layout loading
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # 2. Upgraded Human Emulation: Scroll deep and wait for infinite scroll data to load
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, window.innerHeight);")
                    await asyncio.sleep(1.5) # Give the internet a moment to load elements

                # 3. Snap responsive screenshot assets for your mentor demo
                desktop_img_path = os.path.join(self.screenshot_dir, "desktop.png")
                full_page_img_path = os.path.join(self.screenshot_dir, "full_page.png")
                
                await page.screenshot(path=desktop_img_path, full_page=False)
                await page.screenshot(path=full_page_img_path, full_page=True)

                # 4. Pull down the completely loaded static HTML markup
                raw_rendered_html = await page.content()
                
                return raw_rendered_html, [desktop_img_path, full_page_img_path], browser_logs

            finally:
                # Always safely close files and processes to save computer memory
                await context.close()
                await browser.close()