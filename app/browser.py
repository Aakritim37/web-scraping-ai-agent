# app/browser.py
import asyncio
import os
import random
import re
from playwright.async_api import async_playwright
from app.failures import (
    classify_failure,
    RobotsBlockedError,
    RobotsTxtError,
    DnsTimeoutError,
    SslHandshakeError,
    PaywallDetectedError,
    AntiBotChallengeError,
    ScraperTimeoutError,
    ScraperError,
    NetworkError,
    HttpStatusError,
    AccessError,
    ContentError,
    ShadowDomTimeoutError
)

# Device Profiles with user-agent, viewport size, scale factor, and platform
DEVICE_PROFILES = [
    {
        "name": "Desktop Chrome Mac",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 2,
        "is_mobile": False
    },
    {
        "name": "Desktop Chrome Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "platform": "Win32",
        "viewport": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "is_mobile": False
    },
    {
        "name": "iPhone Safari",
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        "platform": "iPhone",
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 3,
        "is_mobile": True
    },
    {
        "name": "Android Chrome",
        "ua": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "viewport": {"width": 412, "height": 915},
        "device_scale_factor": 2.6,
        "is_mobile": True
    },
    {
        "name": "Desktop Firefox Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "platform": "Win32",
        "viewport": {"width": 1366, "height": 768},
        "device_scale_factor": 1,
        "is_mobile": False
    }
]

class PlaywrightManager:
    def __init__(self, proxy_list: list = None):
        self.screenshot_dir = "storage/screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.proxy_list = proxy_list or []

    def _parse_proxy(self, proxy_str: str) -> dict:
        """Parses a proxy URL string into Playwright format."""
        if not proxy_str:
            return None
        proxy_str = proxy_str.strip()
        protocol = "http://"
        temp = proxy_str
        if "://" in proxy_str:
            protocol, temp = proxy_str.split("://", 1)
            protocol = f"{protocol}://"
            
        if "@" in temp:
            creds, server = temp.split("@", 1)
            if ":" in creds:
                username, password = creds.split(":", 1)
            else:
                username = creds
                password = ""
            return {
                "server": f"{protocol}{server}",
                "username": username,
                "password": password
            }
        else:
            return {"server": f"{protocol}{temp}"}

    def generate_device_profile(self) -> dict:
        """Dynamically generates matching user-agent, viewport size, scale factor, and platform."""
        profile = random.choice(DEVICE_PROFILES)
        res = dict(profile)
        
        # Randomize viewports slightly to prevent exact screen resolution fingerprinting
        w, h = res["viewport"]["width"], res["viewport"]["height"]
        if res["is_mobile"]:
            w_rand = w + random.randint(-10, 10)
            h_rand = h + random.randint(-20, 20)
        else:
            w_rand = w + random.randint(-60, 60)
            h_rand = h + random.randint(-40, 40)
            
        res["viewport"] = {"width": w_rand, "height": h_rand}
        return res

    def calculate_bezier_points(self, start_x, start_y, end_x, end_y, steps=25):
        """Calculates points along a cubic Bezier curve with randomized control points."""
        min_x = min(start_x, end_x)
        max_x = max(start_x, end_x)
        min_y = min(start_y, end_y)
        max_y = max(start_y, end_y)
        
        offset_x = (max_x - min_x) * 0.4
        offset_y = (max_y - min_y) * 0.4
        
        control1_x = start_x + random.uniform(-offset_x, offset_x) + (end_x - start_x) * 0.25
        control1_y = start_y + random.uniform(-offset_y, offset_y) + (end_y - start_y) * 0.25
        
        control2_x = start_x + random.uniform(-offset_x, offset_x) + (end_x - start_x) * 0.75
        control2_y = start_y + random.uniform(-offset_y, offset_y) + (end_y - start_y) * 0.75
        
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = ((1 - t) ** 3) * start_x + 3 * ((1 - t) ** 2) * t * control1_x + 3 * (1 - t) * (t ** 2) * control2_x + (t ** 3) * end_x
            y = ((1 - t) ** 3) * start_y + 3 * ((1 - t) ** 2) * t * control1_y + 3 * (1 - t) * (t ** 2) * control2_y + (t ** 3) * end_y
            points.append((int(x), int(y)))
        return points

    async def glide_mouse_bezier(self, page, end_x, end_y, start_x=None, start_y=None, steps=25):
        """Glides mouse pointer to end_x, end_y using Bezier curves from current/random position."""
        try:
            if start_x is None or start_y is None:
                viewport = page.viewport_size or {"width": 1280, "height": 800}
                start_x = random.randint(10, viewport["width"] - 10)
                start_y = random.randint(10, viewport["height"] - 10)
                
            points = self.calculate_bezier_points(start_x, start_y, end_x, end_y, steps)
            for x, y in points:
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.005, 0.015))
        except Exception:
            pass

    async def humanized_click(self, page, locator):
        """Glides mouse using Bezier curves to element coordinates and clicks human-like."""
        try:
            await locator.wait_for(state="visible", timeout=5000)
            box = await locator.bounding_box()
            if box:
                # Target coordinates offset from element center
                target_x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
                target_y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)
                
                await self.glide_mouse_bezier(page, target_x, target_y)
                
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.08, 0.2))
                await page.mouse.up()
                print(f"[+] Humanized Bezier click performed successfully.")
            else:
                await locator.click()
                print(f"[!] Warning: Bounding box not found, fell back to direct click.")
        except Exception as e:
            print(f"[!] Warning: Humanized Bezier click failed: {str(e)}")
            try:
                await locator.click()
            except Exception:
                pass

    async def configure_network_throttling(self, page, preset: str):
        """Configures network speed emulation (latency, throughput throttling) via CDP session."""
        if not preset or preset.lower() == "fastest":
            return
            
        presets = {
            "fast 3g": {
                "offline": False,
                "latency": 150,
                "downloadThroughput": int(1.6 * 1000 * 1000 / 8),
                "uploadThroughput": int(750 * 1000 / 8)
            },
            "slow 3g": {
                "offline": False,
                "latency": 450,
                "downloadThroughput": int(400 * 1000 / 8),
                "uploadThroughput": int(200 * 1000 / 8)
            }
        }
        
        cfg = presets.get(preset.lower())
        if not cfg:
            return
            
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Network.emulateNetworkConditions", cfg)
            print(f"[+] Network emulation configured: {preset.upper()} (Latency: {cfg['latency']}ms)")
        except Exception as e:
            print(f"[!] Warning: Failed to configure network throttling: {str(e)}")

    async def emulate_human_behavior(self, page):
        """Emulates active human interactions (mouse movement using Bezier curves)."""
        try:
            viewport = page.viewport_size or {"width": 1920, "height": 1080}
            w, h = viewport["width"], viewport["height"]
            curr_x, curr_y = random.randint(100, 300), random.randint(100, 300)
            await page.mouse.move(curr_x, curr_y)
            for _ in range(random.randint(2, 3)):
                target_x = random.randint(100, w - 100)
                target_y = random.randint(100, h - 100)
                await self.glide_mouse_bezier(page, target_x, target_y, start_x=curr_x, start_y=curr_y)
                curr_x, curr_y = target_x, target_y
                await asyncio.sleep(random.uniform(0.15, 0.35))
        except Exception:
            pass

    async def scroll_page_infinitely(self, page, max_scrolls=20, settle_timeout=2.0):
        """
        Intelligently and adaptively scrolls the page infinitely, monitoring the scroll height
        and continuing until no new height changes or elements are loaded.
        """
        try:
            previous_height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            previous_height = 0
            
        scroll_count = 0
        no_change_count = 0
        
        while scroll_count < max_scrolls:
            try:
                # Simulate human-like smooth scrolling down to the current bottom
                steps = random.randint(5, 10)
                target_scroll = previous_height
                current_scroll = await page.evaluate("window.scrollY")
                scroll_delta = target_scroll - current_scroll
                
                if scroll_delta <= 100:
                    # Page is already at or near bottom
                    await page.evaluate("window.scrollBy(0, 300);")
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                else:
                    for i in range(steps):
                        step_amount = int(scroll_delta / steps) + random.randint(-10, 10)
                        await page.evaluate(f"window.scrollBy(0, {step_amount});")
                        await asyncio.sleep(random.uniform(0.04, 0.10))
                
                scroll_count += 1
                await asyncio.sleep(0.8)
                new_height = await page.evaluate("document.body.scrollHeight")
                
                if new_height == previous_height:
                    no_change_count += 1
                    if no_change_count >= 2:
                        # Give it a final safety wait to settle network streams
                        await asyncio.sleep(settle_timeout)
                        final_check_height = await page.evaluate("document.body.scrollHeight")
                        if final_check_height == previous_height:
                            break
                        else:
                            previous_height = final_check_height
                            no_change_count = 0
                else:
                    previous_height = new_height
                    no_change_count = 0
            except Exception:
                break

    async def bypass_cookie_banners(self, page):
        """Intelligently scans the DOM and clicks common cookie banners accept buttons."""
        selectors = [
            "button:has-text('Accept All')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "button:has-text('Allow Cookies')",
            "button:has-text('Allow cookies')",
            "button:has-text('Allow All')",
            "button:has-text('Allow all')",
            "button:has-text('Agree')",
            "button:has-text('I Accept')",
            "button:has-text('I accept')",
            "button:has-text('Consent')",
            "a:has-text('Accept All')",
            "a:has-text('Allow Cookies')",
            "[id*='cookie-consent'] button",
            "[class*='cookie-consent'] button",
            "[id*='cookieconsent'] button",
            "[class*='cookieconsent'] button",
            "[id*='cookie-banner'] button",
            "[class*='cookie-banner'] button",
            "[id*='cookiebanner'] button",
            "[class*='cookiebanner'] button",
            "button[class*='accept']",
            "button[id*='accept']",
            "button[class*='consent']",
            "button[id*='consent']"
        ]
        for sel in selectors:
            try:
                locator = page.locator(sel)
                count = await locator.count()
                for i in range(count):
                    el = locator.nth(i)
                    if await el.is_visible():
                        print(f"[+] Cookie Banner Auto-Bypass: Clicking element matching selector '{sel}'")
                        await self.humanized_click(page, el)
                        await page.wait_for_timeout(1000)
                        return # Exit after successful click to avoid multi-clicking
            except Exception:
                pass

    async def perform_form_actions(self, page, actions: list):
        """Executes form actions (typing, clicking) on target elements."""
        if not actions:
            return
        print(f"[*] Executing {len(actions)} form orchestration actions...")
        for act in actions:
            selector = act.get("selector")
            action = act.get("action")
            value = act.get("value", "")
            if not selector or not action:
                continue
            
            try:
                locator = page.locator(selector)
                await locator.scroll_into_view_if_needed()
                await locator.wait_for(state="visible", timeout=5000)
                
                if action == "type":
                    await locator.focus()
                    await locator.fill("")
                    for char in value:
                        await page.keyboard.type(char, delay=random.uniform(30, 80))
                        await asyncio.sleep(random.uniform(0.04, 0.12))
                    print(f"[+] Typed value into selector '{selector}'")
                elif action == "click":
                    await self.humanized_click(page, locator)
                    await page.wait_for_timeout(1000)
                    print(f"[+] Clicked selector '{selector}'")
            except Exception as e:
                print(f"[!] Warning: Form action failed on '{selector}': {str(e)}")

    async def capture_page(
        self,
        url: str,
        form_actions: list = None,
        next_page_selector: str = None,
        max_pages: int = 1,
        session_persistence: bool = True,
        cookie_bypass: bool = True,
        network_throttling: str = "Fastest"
    ):
        """
        Launches browser with rotated identity, anti-bot stealth patches,
        emulates human usage, tracks requests/redirects, and profiles page performance.
        Supports session persistence, cookie consent auto-bypass, form orchestration,
        and multi-page crawling via next page click.
        """
        profile = self.generate_device_profile()
        user_agent = profile["ua"]
        platform = profile["platform"]
        viewport_w = profile["viewport"]["width"]
        viewport_h = profile["viewport"]["height"]
        device_scale_factor = profile["device_scale_factor"]
        is_mobile = profile["is_mobile"]
        
        proxy_str = random.choice(self.proxy_list) if self.proxy_list else None
        proxy_dict = self._parse_proxy(proxy_str)

        async with async_playwright() as p:
            # 1. Chromium launch with stealth parameters and evasion options
            launch_args = {
                "headless": True,
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--no-sandbox"
                ]
            }
            if proxy_dict:
                launch_args["proxy"] = proxy_dict
                
            browser = await p.chromium.launch(**launch_args)
            
            # 2. Browser context with custom locales, viewport, and user-agent
            context_args = {
                "user_agent": user_agent,
                "viewport": {"width": viewport_w, "height": viewport_h},
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "device_scale_factor": device_scale_factor,
                "is_mobile": is_mobile,
                "has_touch": is_mobile
            }
            storage_path = "storage/session_state.json"
            
            # Evasion: Clean up any cached state files if session_persistence is False
            if not session_persistence:
                if os.path.exists(storage_path):
                    try:
                        os.remove(storage_path)
                        print(f"[+] Cleared cached session state file: {storage_path}")
                    except Exception as e:
                        print(f"[!] Warning: Failed to clear cached session state file: {str(e)}")
            
            if session_persistence and os.path.exists(storage_path):
                context_args["storage_state"] = storage_path
                print(f"[+] Loaded session state from {storage_path}")

            context = await browser.new_context(**context_args)
            page = await context.new_page()
            
            # Configure network throttling preset via CDP session
            await self.configure_network_throttling(page, network_throttling)
            
            # 3. Apply stealth init scripts to bypass automated WAF/Cloudflare detector scripts
            await page.add_init_script(f"""
                // Delete the navigator.webdriver property
                delete Navigator.prototype.webdriver;

                // Override platform
                Object.defineProperty(navigator, 'platform', {{
                    get: () => '{platform}'
                }});

                // Spoof languages
                Object.defineProperty(navigator, 'languages', {{
                    get: () => ['en-US', 'en']
                }});

                // Spoof permissions.query to prevent detecting automation
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications' ?
                        Promise.resolve({{ state: Notification.permission }}) :
                        originalQuery(parameters);

                // Spoof device memory and hardware concurrency
                Object.defineProperty(navigator, 'deviceMemory', {{
                    get: () => 8
                }});
                Object.defineProperty(navigator, 'hardwareConcurrency', {{
                    get: () => 8
                }});

                // Spoof WebGL vendor and renderer to look like regular desktop GPUs
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) {{
                        return 'Intel Inc.';
                    }}
                    if (parameter === 37446) {{
                        return 'Intel(R) Iris(TM) Plus Graphics 640';
                    }}
                    return getParameter.apply(this, [parameter]);
                }};

                // Mock chrome global APIs
                window.chrome = {{
                    runtime: {{}},
                    loadTimes: function() {{}},
                    csi: function() {{}},
                    app: {{}}
                }};

                // Mock plugins array to look like a standard desktop browser
                Object.defineProperty(navigator, 'plugins', {{
                    get: () => [
                        {{ name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
                        {{ name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
                        {{ name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }}
                    ]
                }});
            """)

            # Track console outputs and build Console Diagnostics Pipeline
            browser_logs = []
            console_errors = []
            
            def handle_console(msg):
                browser_logs.append({"type": msg.type, "text": msg.text})
                if msg.type in ["error", "warning"]:
                    console_errors.append({
                        "type": msg.type,
                        "text": msg.text,
                        "location": msg.location if hasattr(msg, "location") else {}
                    })
            page.on("console", handle_console)

            # Hook WebSocket listeners to track lifecycle and frame transfer sizes
            def log_websocket(ws):
                browser_logs.append({"type": "info", "text": f"[WebSocket] Opened connection: {ws.url}"})
                
                # Fired when data frames are sent/received
                ws.on("framereceived", lambda payload: browser_logs.append({
                    "type": "log",
                    "text": f"[WebSocket] Received frame data size: {len(payload) if isinstance(payload, (str, bytes)) else len(str(payload))} chars"
                }))
                ws.on("framesent", lambda payload: browser_logs.append({
                    "type": "log",
                    "text": f"[WebSocket] Sent frame data size: {len(payload) if isinstance(payload, (str, bytes)) else len(str(payload))} chars"
                }))
                ws.on("close", lambda: browser_logs.append({
                    "type": "info",
                    "text": f"[WebSocket] Closed connection: {ws.url}"
                }))
                
            page.on("websocket", log_websocket)

            # Hook network event listeners for full request/response and failed resources tracking
            requests_list = []
            responses_by_url = {}
            all_requests = []
            all_responses = []
            failed_resources = []
            
            def handle_request_telemetry(req):
                try:
                    all_requests.append({
                        "url": req.url,
                        "method": req.method,
                        "resource_type": req.resource_type,
                        "headers": dict(req.headers)
                    })
                except Exception:
                    pass
            page.on("request", handle_request_telemetry)

            def handle_response_telemetry(res):
                try:
                    responses_by_url[res.url] = res
                    all_responses.append({
                        "url": res.url,
                        "status": res.status,
                        "headers": dict(res.headers)
                    })
                    
                    # Track failed resource loads (status < 200 or status >= 400)
                    # Monitor image, stylesheet, script, font, xhr, fetch
                    req = res.request
                    resource_type = req.resource_type if req else "unknown"
                    if resource_type in ["image", "stylesheet", "script", "font", "xhr", "fetch"]:
                        if res.status < 200 or res.status >= 400:
                            failed_resources.append({
                                "url": res.url,
                                "resource_type": resource_type,
                                "status": res.status,
                                "reason": f"HTTP {res.status} Error"
                            })
                except Exception:
                    pass
            page.on("response", handle_response_telemetry)

            def handle_request_failed_telemetry(req):
                try:
                    resource_type = req.resource_type if req else "unknown"
                    if resource_type in ["image", "stylesheet", "script", "font", "xhr", "fetch"]:
                        failed_resources.append({
                            "url": req.url,
                            "resource_type": resource_type,
                            "status": None,
                            "reason": req.failure.error_text if req.failure else "Request failed"
                        })
                except Exception:
                    pass
            page.on("requestfailed", handle_request_failed_telemetry)
            page.on("requestfinished", lambda req: requests_list.append(req))

            try:
                # 4. Navigate to target URL
                try:
                    # Introduce randomized pre-navigation delay
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    # Wait for initial layout content to load robustly via domcontentloaded
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if not response:
                        raise ScraperError("Received empty navigation response from browser.")
                    
                    # Next, wait for networkidle with a soft timeout threshold of 10 seconds
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        print("[-] Soft timeout: Network did not quiet down within 10s. Proceeding with dynamic interaction.")
                except Exception as e:
                    exc_str = str(e).lower()
                    if any(p in exc_str for p in ["shadow", "shadowroot", "shadow-root"]) and any(p in exc_str for p in ["timeout", "timed out", "navigation", "waiting for selector"]):
                        raise ShadowDomTimeoutError(f"Shadow DOM navigation/rendering timed out: {str(e)}") from e
                    elif "name_not_resolved" in exc_str or "dns" in exc_str or "err_name" in exc_str:
                        raise DnsTimeoutError(f"DNS resolution failed: {str(e)}") from e
                    elif any(p in exc_str for p in ["ssl", "cert", "handshake"]):
                        raise SslHandshakeError(f"SSL secure handshake failed: {str(e)}") from e
                    elif "timeout" in exc_str or "timed out" in exc_str:
                        raise ScraperTimeoutError(f"Navigation timed out: {str(e)}") from e
                    else:
                        raise NetworkError(str(e)) from e

                # 5. Check for anti-bot or paywall roadblocks using the status and content
                status_code = response.status
                headers = response.headers
                raw_rendered_html = await page.content()

                err_info = classify_failure(status_code=status_code, page_content=raw_rendered_html, headers=headers)
                cat = err_info["category"].upper()
                if cat == "ANTI_BOT":
                    raise AntiBotChallengeError(err_info["reason"])
                elif cat == "PAYWALLS":
                    raise PaywallDetectedError(err_info["reason"])
                elif cat == "ACCESS":
                    raise AccessError(err_info["reason"])
                elif cat == "ROBOTS_TXT":
                    raise RobotsTxtError(err_info["reason"])
                elif cat == "CONTENT":
                    raise ContentError(err_info["reason"])
                elif cat == "HTTP_STATUS":
                    raise HttpStatusError(err_info["reason"])
                elif status_code >= 400:
                    raise HttpStatusError(f"Server returned HTTP status code {status_code}.")

                # Optional cookie bypass and form actions
                if cookie_bypass:
                    await self.bypass_cookie_banners(page)

                if form_actions:
                    await self.perform_form_actions(page, form_actions)

                # 6. Simulate human interactions (Mouse movement & Scrolling)
                await self.emulate_human_behavior(page)
                await self.scroll_page_infinitely(page)

                # 7. Absolute file erasure of stale screenshot files on disk before capturing new ones
                for sf in os.listdir(self.screenshot_dir):
                    if sf.endswith(".png"):
                        try:
                            os.remove(os.path.join(self.screenshot_dir, sf))
                        except Exception:
                            pass

                # Scroll back to top to ensure above-the-fold area is captured cleanly
                await page.evaluate("window.scrollTo(0, 0);")
                await asyncio.sleep(0.5)

                screenshot_paths = []
                desktop_above_fold_path = os.path.join(self.screenshot_dir, "desktop_above_fold.png")
                full_page_img_path = os.path.join(self.screenshot_dir, "full_page.png")
                await page.screenshot(path=desktop_above_fold_path, full_page=False)
                await page.screenshot(path=full_page_img_path, full_page=True)
                screenshot_paths.extend([desktop_above_fold_path, full_page_img_path])

                # Resize viewport for Tablet and capture tablet_view.png
                tablet_view_path = os.path.join(self.screenshot_dir, "tablet_view.png")
                desktop_size = page.viewport_size or {"width": viewport_w, "height": viewport_h}
                await page.set_viewport_size({"width": 768, "height": 1024})
                await asyncio.sleep(0.5)
                await page.screenshot(path=tablet_view_path, full_page=True)
                screenshot_paths.append(tablet_view_path)
                # Restore desktop viewport size
                await page.set_viewport_size(desktop_size)

                # Spawn separate mobile context for mobile device simulation (375x812, mobile UA)
                mobile_view_path = os.path.join(self.screenshot_dir, "mobile_view.png")
                try:
                    mobile_context_args = {
                        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
                        "viewport": {"width": 375, "height": 812},
                        "locale": "en-US"
                    }
                    if session_persistence and os.path.exists(storage_path):
                        mobile_context_args["storage_state"] = storage_path
                    mobile_context = await browser.new_context(**mobile_context_args)
                    mobile_page = await mobile_context.new_page()
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    # Wait for domcontentloaded first
                    await mobile_page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    # Next, wait for networkidle with a soft timeout threshold of 10 seconds
                    try:
                        await mobile_page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    await mobile_page.screenshot(path=mobile_view_path, full_page=True)
                    await mobile_context.close()
                    screenshot_paths.append(mobile_view_path)
                except Exception as e:
                    print(f"[!] Warning: Mobile screenshot capture failed: {str(e)}")
                    mobile_view_path = None

                # 8. Extract page performance statistics
                timing_metrics = await page.evaluate("""() => {
                    const [timing] = performance.getEntriesByType('navigation');
                    if (!timing) return null;
                    return {
                        dom_ready_time: timing.domContentLoadedEventEnd - timing.startTime,
                        load_duration: timing.loadEventEnd || performance.now()
                    };
                }""")
                
                dom_ready = timing_metrics.get("dom_ready_time", 0) if timing_metrics else 0
                load_duration = timing_metrics.get("load_duration", 0) if timing_metrics else 0

                # 9. Sum network payload sizes
                total_payload_bytes = 0
                for req in requests_list:
                    try:
                        sizes = await req.sizes()
                        total_payload_bytes += sizes.get("responseBodySize", 0) + sizes.get("responseHeadersSize", 0)
                    except Exception:
                        pass

                # 10. Form redirect chain history
                redirect_chain = []
                current_req = response.request
                while current_req.redirected_from:
                    parent_req = current_req.redirected_from
                    parent_resp = responses_by_url.get(parent_req.url)
                    redirect_chain.insert(0, {
                        "url": parent_req.url,
                        "status": parent_resp.status if parent_resp else 302,
                        "request_headers": dict(parent_req.headers) if parent_req else {},
                        "response_headers": dict(parent_resp.headers) if parent_resp else {}
                    })
                    current_req = parent_req

                # Update HTML payload using deep DOM piercing script (Shadow DOM & Iframe contents)
                js_serializer = """
                () => {
                    function serializeNode(node) {
                        if (!node) return '';
                        
                        switch (node.nodeType) {
                            case Node.TEXT_NODE:
                                return node.nodeValue.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                            case Node.COMMENT_NODE:
                                return `<!--${node.nodeValue}-->`;
                            case Node.DOCUMENT_TYPE_NODE:
                                return `<!DOCTYPE ${node.name}>`;
                            case Node.ELEMENT_NODE:
                                let tagName = node.tagName.toLowerCase();
                                if (tagName === 'script' || tagName === 'style') {
                                    return node.outerHTML;
                                }
                                
                                let html = `<${tagName}`;
                                for (let i = 0; i < node.attributes.length; i++) {
                                    let attr = node.attributes[i];
                                    html += ` ${attr.name}="${attr.value.replace(/"/g, '&quot;')}"`;
                                }
                                html += '>';
                                
                                if (node.shadowRoot) {
                                    html += `<template shadowrootmode="${node.shadowRoot.mode || 'open'}">`;
                                    for (let child of node.shadowRoot.childNodes) {
                                        html += serializeNode(child);
                                    }
                                    html += '</template>';
                                }
                                
                                if (tagName === 'iframe') {
                                    try {
                                        let iframeDoc = node.contentDocument || node.contentWindow.document;
                                        if (iframeDoc) {
                                            let iframeSrc = node.src || '';
                                            html += `<iframe-content src="${iframeSrc}">`;
                                            for (let child of iframeDoc.childNodes) {
                                                html += serializeNode(child);
                                            }
                                            html += `</iframe-content>`;
                                        }
                                    } catch (e) {
                                        // Cross-origin iframe
                                    }
                                }
                                
                                for (let child of node.childNodes) {
                                    html += serializeNode(child);
                                }
                                
                                html += `</${tagName}>`;
                                return html;
                            case Node.DOCUMENT_NODE:
                            case Node.DOCUMENT_FRAGMENT_NODE:
                                let docHtml = '';
                                for (let child of node.childNodes) {
                                    docHtml += serializeNode(child);
                                }
                                return docHtml;
                            default:
                                return '';
                        }
                    }
                    return serializeNode(document);
                }
                """
                
                pages_html = []
                updated_rendered_html = await page.evaluate(js_serializer)
                pages_html.append(updated_rendered_html)

                # Pagination Multi-Page Loop
                current_page_idx = 1
                while current_page_idx < max_pages and next_page_selector:
                    print(f"[*] Crawling page {current_page_idx + 1} of {max_pages}...")
                    next_btn = page.locator(next_page_selector).first
                    if not await next_btn.is_visible():
                        print("[-] Next page button not visible/found. Stopping pagination.")
                        break

                    try:
                        await next_btn.scroll_into_view_if_needed()
                        async with page.expect_navigation(wait_until="domcontentloaded", timeout=10000) as nav:
                            await self.humanized_click(page, next_btn)
                    except Exception:
                        try:
                            await self.humanized_click(page, next_btn)
                        except Exception as click_err:
                            print(f"[-] Click next page button failed: {str(click_err)}")
                            break

                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass

                    if cookie_bypass:
                        await self.bypass_cookie_banners(page)

                    await self.scroll_page_infinitely(page, max_scrolls=5)

                    # Serialize page HTML and append
                    page_html_data = await page.evaluate(js_serializer)
                    pages_html.append(page_html_data)

                    # Take pagination screenshots
                    try:
                        await page.evaluate("window.scrollTo(0, 0);")
                        await asyncio.sleep(0.5)
                        above_fold_p = os.path.join(self.screenshot_dir, f"desktop_above_fold_p{current_page_idx+1}.png")
                        full_page_p = os.path.join(self.screenshot_dir, f"full_page_p{current_page_idx+1}.png")
                        await page.screenshot(path=above_fold_p, full_page=False)
                        await page.screenshot(path=full_page_p, full_page=True)
                        screenshot_paths.extend([above_fold_p, full_page_p])
                    except Exception as e:
                        print(f"[!] Warning: Pagination screenshot failed for page {current_page_idx+1}: {str(e)}")

                    current_page_idx += 1

                metrics = {
                    "status_code": status_code,
                    "headers": dict(headers),
                    "redirect_chain": redirect_chain,
                    "dom_ready_time": round(dom_ready, 2),
                    "load_duration": round(load_duration, 2),
                    "total_payload_bytes": total_payload_bytes,
                    "user_agent": user_agent,
                    "proxy": proxy_str,
                    "desktop_above_fold": desktop_above_fold_path,
                    "tablet_view": tablet_view_path,
                    "mobile_view": mobile_view_path,
                    "telemetry": {
                        "requests": all_requests,
                        "responses": all_responses,
                        "failed_resources": failed_resources,
                        "console_errors": console_errors
                    }
                }

                # Filter out None paths
                screenshot_paths = [p for p in screenshot_paths if p is not None]

                return pages_html, screenshot_paths, browser_logs, metrics

            finally:
                if 'context' in locals() and context and session_persistence:
                    try:
                        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                        await context.storage_state(path=storage_path)
                        print(f"[+] Saved updated session state to {storage_path}")
                    except Exception as e:
                        print(f"[!] Warning: Failed to save storage state: {str(e)}")
                if 'context' in locals() and context:
                    await context.close()
                if 'browser' in locals() and browser:
                    await browser.close()