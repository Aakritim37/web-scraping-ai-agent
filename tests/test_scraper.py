# tests/test_scraper.py
import unittest
import asyncio
import os
from unittest.mock import patch, MagicMock
from app.failures import (
    classify_failure,
    RobotsBlockedError,
    AntiBotChallengeError,
    PaywallDetectedError,
    retry_on_antibot
)
from app.extractor import ContentExtractor
from app.history import HistoryManager, calculate_sha256

class TestFailuresEngine(unittest.TestCase):
    def test_classify_robots_blocked(self):
        err = RobotsBlockedError("Crawl blocked")
        res = classify_failure(exception=err)
        self.assertEqual(res["category"], "ROBOTS_TXT")
        self.assertIn("robots.txt", res["reason"])

    def test_classify_antibot_by_status(self):
        res = classify_failure(status_code=403, page_content="Cloudflare protection")
        self.assertEqual(res["category"], "ANTI_BOT")
        self.assertIn("anti-bot", res["reason"])

    def test_classify_antibot_by_content(self):
        res = classify_failure(exception=Exception("Forbidden"), page_content="Checking your browser before accessing...")
        self.assertEqual(res["category"], "ANTI_BOT")
        self.assertIn("anti-bot", res["reason"])

    def test_classify_amazon_captcha_page(self):
        # Amazon validate captcha path
        res1 = classify_failure(page_content="amazon.com/gp/errors/validatecaptcha")
        self.assertEqual(res1["category"], "ANTI_BOT")
        
        # Amazon typical captcha text
        res2 = classify_failure(page_content="To discuss automated access to Amazon data please contact api-services@amazon.com")
        self.assertEqual(res2["category"], "ANTI_BOT")
        self.assertIn("to discuss automated access to amazon data", res2["reason"])

    def test_classify_paywall(self):
        res = classify_failure(status_code=402)
        self.assertEqual(res["category"], "PAYWALLS")
        
        res2 = classify_failure(page_content="Please register to read the full article")
        self.assertEqual(res2["category"], "PAYWALLS")

    def test_classify_ssl_error(self):
        res = classify_failure(exception=Exception("net::ERR_CERT_COMMON_NAME_INVALID"))
        self.assertEqual(res["category"], "NETWORK")

    def test_classify_dns_timeout(self):
        res = classify_failure(exception=Exception("net::ERR_NAME_NOT_RESOLVED"))
        self.assertEqual(res["category"], "NETWORK")
        self.assertIn("DNS", res["reason"])

    def test_classify_shadow_dom_timeout(self):
        from app.failures import ShadowDomTimeoutError
        res1 = classify_failure(exception=ShadowDomTimeoutError("waiting for selector in shadowroot"))
        self.assertEqual(res1["category"], "NETWORK")
        self.assertIn("Shadow DOM", res1["reason"])

        res2 = classify_failure(exception=Exception("navigation timed out waiting for shadow-root"))
        self.assertEqual(res2["category"], "NETWORK")
        self.assertIn("Shadow DOM", res2["reason"])

    def test_classify_turnstile_and_cloudflare_headers(self):
        # Scan headers for cloudflare signals
        res1 = classify_failure(headers={"CF-RAY": "abcdef123", "server": "cloudflare"})
        self.assertEqual(res1["category"], "ANTI_BOT")

        # Scan content for Turnstile widget elements
        res2 = classify_failure(page_content="<div class='cf-turnstile' data-sitekey='...'></div>")
        self.assertEqual(res2["category"], "ANTI_BOT")
        self.assertIn("turnstile", res2["reason"])

    def test_classify_access_denied(self):
        res1 = classify_failure(status_code=401)
        self.assertEqual(res1["category"], "ACCESS")

        res2 = classify_failure(status_code=403, page_content="some generic forbidden error message")
        self.assertEqual(res2["category"], "ACCESS")
        self.assertIn("Access denied", res2["reason"])

    def test_classify_content_error(self):
        # Empty/missing content
        res1 = classify_failure(page_content="")
        self.assertEqual(res1["category"], "CONTENT")

        # Invalid schema/extraction error
        res2 = classify_failure(page_content="<html><body>content-extraction-error</body></html>")
        self.assertEqual(res2["category"], "CONTENT")
        self.assertIn("extraction validation", res2["reason"])

class TestRetryEngine(unittest.TestCase):
    def test_retry_success_after_failure(self):
        attempts = 0
        async def mock_capture():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise AntiBotChallengeError("Mocked anti-bot screen")
            return "scraped_data_payload"

        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            res = asyncio.run(retry_on_antibot(mock_capture, max_retries=3))
            self.assertEqual(res, "scraped_data_payload")
            self.assertEqual(attempts, 2)
            mock_sleep.assert_called_once()

    def test_retry_exhausted(self):
        attempts = 0
        async def mock_capture_always_fails():
            nonlocal attempts
            attempts += 1
            raise AntiBotChallengeError("Mocked anti-bot screen")

        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            with self.assertRaises(AntiBotChallengeError):
                asyncio.run(retry_on_antibot(mock_capture_always_fails, max_retries=3))
            self.assertEqual(attempts, 3)
            self.assertEqual(mock_sleep.call_count, 2)

class TestExtractor(unittest.TestCase):
    def test_deep_parsing(self):
        mock_html = """
        <html>
            <head>
                <title>Test Scraping App</title>
                <meta charset="utf-8">
                <meta name="description" content="A robust scraper test page">
                <meta name="keywords" content="scraper, python, test">
                <link rel="canonical" href="https://example.com/canonical-page">
                <link rel="shortcut icon" href="/assets/favicon.ico">
                <meta property="og:title" content="OpenGraph Test title">
                <meta name="twitter:card" content="summary_large_image">
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": "Test Page"
                }
                </script>
            </head>
            <body>
                <h1>Header 1</h1>
                <h3>Header 3</h3>
                <h5>Header 5</h5>
                <p>Paragraph body content.</p>
                <ul>
                    <li>Bullet point 1</li>
                    <li>Bullet point 2</li>
                </ul>
                <table>
                    <thead>
                        <tr><th>Header A</th><th>Header B</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Cell A1</td><td>Cell B1</td></tr>
                        <tr><td>Cell A2</td><td>Cell B2</td></tr>
                    </tbody>
                </table>
                <a href="/relative/path">Link 1</a>
                <a href="https://example.com/document.pdf">Download PDF</a>
                <a href="https://example.com/movie.mp4">Video Link</a>
                <img src="/assets/image.png" alt="Test image" width="300" height="200" />
                <img src="/assets/logo.png" alt="Main Brand Logo" />
                <svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" /></svg>
                <video src="https://example.com/video.webm"></video>
            </body>
        </html>
        """
        result = ContentExtractor.extract(mock_html, "https://example.com")
        
        self.assertEqual(result["title"], "Test Scraping App")
        self.assertEqual(result["description"], "A robust scraper test page")
        self.assertIn("Header 5", result["headings_list"])
        self.assertIn("Paragraph body content.", result["content"])
        
        # Lists
        self.assertEqual(len(result["lists"]), 1)
        self.assertEqual(result["lists"][0]["type"], "ul")
        self.assertEqual(result["lists"][0]["items"], ["Bullet point 1", "Bullet point 2"])
        
        # Tables
        self.assertEqual(len(result["tables"]), 1)
        self.assertEqual(result["tables"][0]["headers"], ["Header A", "Header B"])
        self.assertEqual(result["tables"][0]["rows"], [["Cell A1", "Cell B1"], ["Cell A2", "Cell B2"]])
        
        # Social media og/twitter
        self.assertEqual(result["social_metadata"]["og:title"], "OpenGraph Test title")
        self.assertEqual(result["social_metadata"]["twitter:card"], "summary_large_image")
        
        # JSON-LD
        self.assertEqual(len(result["json_ld"]), 1)
        self.assertEqual(result["json_ld"][0]["name"], "Test Page")
        
        # Assets & Links
        self.assertIn("https://example.com/relative/path", result["links"])
        self.assertIn("https://example.com/document.pdf", result["documents"])
        
        # Classifications & Downloads
        self.assertIn("https://example.com/relative/path", result["internal_links"])
        self.assertIn("https://example.com/document.pdf", result["internal_links"])
        self.assertIn("https://example.com/document.pdf", result["download_links"])

        # Alt-text and layout metrics
        self.assertEqual(len(result["images"]), 2)
        img1 = next(img for img in result["images"] if "image.png" in img["url"])
        self.assertEqual(img1["alt"], "Test image")
        self.assertEqual(img1["width"], 300)
        self.assertEqual(img1["height"], 200)

        # Logos
        self.assertIn("https://example.com/assets/favicon.ico", result["logos"])
        self.assertIn("https://example.com/assets/logo.png", result["logos"])

        # SVGs
        self.assertEqual(len(result["svgs"]), 1)
        self.assertIn('<svg viewbox="0 0 100 100">', result["svgs"][0])

        # Videos
        self.assertIn("https://example.com/movie.mp4", result["videos"])
        self.assertIn("https://example.com/video.webm", result["videos"])

        # Technical & SEO Properties
        self.assertEqual(result["canonical_url"], "https://example.com/canonical-page")
        self.assertEqual(result["keywords"], ["scraper", "python", "test"])
        self.assertEqual(result["charset"], "utf-8")

    def test_scrape_result_schema_tables(self):
        from app.schemas import ScrapeResultSchema
        schema = ScrapeResultSchema(
            status="success",
            url="https://example.com",
            tables=[{"headers": ["A"], "rows": [["1"]]}]
        )
        self.assertEqual(schema.tables, [{"headers": ["A"], "rows": [["1"]]}])
        serialized = schema.model_dump()
        self.assertEqual(serialized["tables"], [{"headers": ["A"], "rows": [["1"]]}])

    @patch("requests.get")
    def test_robots_txt_allowed(self, mock_get):
        # Mock robots.txt allowing all
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /"
        mock_get.return_value = mock_response
        
        allowed = ContentExtractor.check_robots_allowed("https://testsite.com/page")
        self.assertTrue(allowed)

    @patch("requests.get")
    def test_robots_txt_disallowed(self, mock_get):
        # Mock robots.txt disallowing all
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /"
        mock_get.return_value = mock_response
        
        allowed = ContentExtractor.check_robots_allowed("https://testsite.com/page")
        self.assertFalse(allowed)

class TestLinkVerification(unittest.TestCase):
    @patch("requests.head")
    @patch("requests.get")
    def test_verify_link_status_success(self, mock_get, mock_head):
        from app.main import verify_link_status_sync
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_head.return_value = mock_resp
        
        res = verify_link_status_sync("https://google.com")
        self.assertEqual(res["status"], "active")
        self.assertEqual(res["status_code"], 200)
        mock_head.assert_called_once()
        mock_get.assert_not_called()

    @patch("requests.head")
    @patch("requests.get")
    def test_verify_link_status_fallback(self, mock_get, mock_head):
        from app.main import verify_link_status_sync
        mock_resp_head = MagicMock()
        mock_resp_head.status_code = 405
        mock_head.return_value = mock_resp_head
        
        mock_resp_get = MagicMock()
        mock_resp_get.status_code = 200
        mock_get.return_value = mock_resp_get
        
        res = verify_link_status_sync("https://google.com")
        self.assertEqual(res["status"], "active")
        self.assertEqual(res["status_code"], 200)
        mock_head.assert_called_once()
        mock_get.assert_called_once()

    @patch("requests.head")
    def test_verify_link_status_exception(self, mock_head):
        from app.main import verify_link_status_sync
        mock_head.side_effect = Exception("Connection timeout")
        
        res = verify_link_status_sync("https://google.com")
        self.assertEqual(res["status"], "broken")
        self.assertEqual(res["status_code"], None)
        self.assertIn("Connection timeout", res["error"])

    def test_verify_link_status_async(self):
        from app.main import verify_link_status
        with patch("app.main.verify_link_status_sync") as mock_sync:
            mock_sync.return_value = {"url": "https://google.com", "status_code": 200, "status": "active"}
            res = asyncio.run(verify_link_status("https://google.com"))
            self.assertEqual(res["status"], "active")
            mock_sync.assert_called_once_with("https://google.com")

class TestMultiViewportScreenshots(unittest.TestCase):
    def test_schema_screenshot_attributes(self):
        from app.schemas import ScrapeResultSchema
        schema = ScrapeResultSchema(
            status="success",
            url="https://example.com",
            desktop_above_fold="storage/screenshots/desktop_above_fold.png",
            mobile_view="storage/screenshots/mobile_view.png",
            tablet_view="storage/screenshots/tablet_view.png"
        )
        self.assertEqual(schema.desktop_above_fold, "storage/screenshots/desktop_above_fold.png")
        self.assertEqual(schema.mobile_view, "storage/screenshots/mobile_view.png")
        self.assertEqual(schema.tablet_view, "storage/screenshots/tablet_view.png")
        
        serialized = schema.model_dump()
        self.assertEqual(serialized["desktop_above_fold"], "storage/screenshots/desktop_above_fold.png")
        self.assertEqual(serialized["mobile_view"], "storage/screenshots/mobile_view.png")
        self.assertEqual(serialized["tablet_view"], "storage/screenshots/tablet_view.png")

class TestDynamicSupport(unittest.TestCase):
    def test_shadow_dom_extraction(self):
        mock_html = """
        <html>
            <body>
                <div id="host">
                    <template shadowrootmode="open">
                        <h1>Shadow DOM Header</h1>
                        <p>Shadow paragraph content.</p>
                        <a href="shadow-page.html">Shadow Link</a>
                        <img src="shadow-img.png" alt="Shadow Image" />
                    </template>
                </div>
            </body>
        </html>
        """
        result = ContentExtractor.extract(mock_html, "https://example.com/main/")
        self.assertIn("Shadow DOM Header", result["headings_list"])
        self.assertIn("Shadow paragraph content.", result["content"])
        self.assertIn("https://example.com/main/shadow-page.html", result["links"])
        
        img_urls = [img["url"] for img in result["images"]]
        self.assertIn("https://example.com/main/shadow-img.png", img_urls)

    def test_iframe_nesting_and_url_resolution(self):
        mock_html = """
        <html>
            <body>
                <iframe-content src="frame1/index.html">
                    <a href="link1.html">Frame 1 Link</a>
                    <iframe-content src="inner/frame2.html">
                        <a href="link2.html">Frame 2 Link</a>
                        <img src="../logo.png" alt="Nested Logo" />
                    </iframe-content>
                </iframe-content>
            </body>
        </html>
        """
        result = ContentExtractor.extract(mock_html, "https://example.com/")
        
        # Test links resolution
        self.assertIn("https://example.com/frame1/link1.html", result["links"])
        self.assertIn("https://example.com/frame1/inner/link2.html", result["links"])
        
        # Test images resolution inside nested frame
        img_urls = [img["url"] for img in result["images"]]
        self.assertIn("https://example.com/frame1/logo.png", img_urls)

    def test_websocket_logging_binding(self):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        # Mock objects
        mock_page = MagicMock()
        mock_ws = MagicMock()
        mock_ws.url = "wss://example.com/socket"
        
        browser_logs = []
        
        # Capture websocket registration
        register_ws_listener = None
        def mock_on(event, callback):
            nonlocal register_ws_listener
            if event == "websocket":
                register_ws_listener = callback
            elif event == "console":
                pass
        
        mock_page.on = mock_on
        
        # Simulate websocket bindings
        # Create a tiny function simulating browser.py listener logic
        def setup_listeners(page):
            def log_websocket(ws):
                browser_logs.append(f"OPEN: {ws.url}")
                ws.on("framereceived", lambda payload: browser_logs.append(f"RX: {len(payload)}"))
                ws.on("close", lambda: browser_logs.append("CLOSE"))
            page.on("websocket", log_websocket)
            
        setup_listeners(mock_page)
        
        self.assertIsNotNone(register_ws_listener)
        register_ws_listener(mock_ws)
        
        # Verify frame listeners were bound to mock_ws
        bind_calls = {call[0][0]: call[0][1] for call in mock_ws.on.call_args_list}
        self.assertIn("framereceived", bind_calls)
        self.assertIn("close", bind_calls)
        
        # Fire mock events and verify logging
        bind_calls["framereceived"]("Hello World")
        bind_calls["close"]()
        
        self.assertIn("OPEN: wss://example.com/socket", browser_logs)
        self.assertIn("RX: 11", browser_logs)
        self.assertIn("CLOSE", browser_logs)

    def test_scroll_page_infinitely_loop(self):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        mock_page = MagicMock()
        
        # Simulate scroll heights: increases twice, then stays static
        heights = [1000, 2000, 3000, 3000, 3000]
        call_count = 0
        
        async def mock_evaluate(script):
            nonlocal call_count
            if "scrollHeight" in script:
                val = heights[min(call_count, len(heights) - 1)]
                call_count += 1
                return val
            return 0
            
        mock_page.evaluate = mock_evaluate
        
        # Run scroll loop with tight limits for testing speed
        with patch("asyncio.sleep", return_value=None):
            coro = manager.scroll_page_infinitely(mock_page, max_scrolls=10, settle_timeout=0.01)
            asyncio.run(coro)
            
        # Verify loop executed multiple scroll attempts
        self.assertGreater(call_count, 2)

class TestBrowserSimulation(unittest.TestCase):
    def test_merge_tables_identical_headers(self):
        from app.main import merge_tables
        tables_p1 = [
            {"headers": ["Name", "Age"], "rows": [["Alice", "24"], ["Bob", "30"]]}
        ]
        tables_p2 = [
            {"headers": ["Name ", "age"], "rows": [["Charlie", "28"], ["Alice", "24"]]} # whitespace and case variance
        ]
        
        merged = merge_tables([tables_p1, tables_p2])
        self.assertEqual(len(merged), 1)
        self.assertEqual([h.strip().lower() for h in merged[0]["headers"]], ["name", "age"])
        self.assertEqual(len(merged[0]["rows"]), 3)
        self.assertIn(["Alice", "24"], merged[0]["rows"])
        self.assertIn(["Charlie", "28"], merged[0]["rows"])

    def test_merge_tables_different_headers(self):
        from app.main import merge_tables
        tables_p1 = [
            {"headers": ["Name", "Age"], "rows": [["Alice", "24"]]}
        ]
        tables_p2 = [
            {"headers": ["City", "Population"], "rows": [["Paris", "2.2M"]]}
        ]
        
        merged = merge_tables([tables_p1, tables_p2])
        self.assertEqual(len(merged), 2)

    @patch("playwright.async_api.Page")
    def test_cookie_banner_bypass(self, mock_page_class):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        mock_page = MagicMock()
        mock_locator = MagicMock()
        
        # We need mock_locator to act like an async method or mock value when awaited
        async def mock_count():
            return 1
        async def mock_is_visible():
            return True
        async def mock_click():
            pass
            
        mock_locator.count = mock_count
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = mock_is_visible
        mock_locator.click = mock_click
        
        mock_page.locator.return_value = mock_locator
        
        # Test bypass_cookie_banners clicks visible cookie elements
        asyncio.run(manager.bypass_cookie_banners(mock_page))
        self.assertTrue(mock_page.locator.called)

    @patch("playwright.async_api.Page")
    def test_perform_form_actions(self, mock_page_class):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        mock_page = MagicMock()
        mock_locator = MagicMock()
        
        async def mock_wait_for(state=None, timeout=None):
            pass
        async def mock_scroll():
            pass
        async def mock_focus():
            pass
        async def mock_fill(val):
            pass
        async def mock_click():
            pass
            
        mock_locator.wait_for = mock_wait_for
        mock_locator.scroll_into_view_if_needed = mock_scroll
        mock_locator.focus = mock_focus
        mock_locator.fill = mock_fill
        mock_locator.click = mock_click
        
        mock_page.locator.return_value = mock_locator
        
        # Mock page.keyboard.type as a regular function since we await type inside loop
        # Wait, the code calls page.keyboard.type(char) which is normally awaited in Playwright,
        # but in our implementation we did: `await page.keyboard.type(char)`
        async def mock_keyboard_type(char, **kwargs):
            pass
        mock_page.keyboard.type = mock_keyboard_type
        
        actions = [
            {"selector": "input.username", "action": "type", "value": "testuser"},
            {"selector": "button.submit", "action": "click"}
        ]
        
        asyncio.run(manager.perform_form_actions(mock_page, actions))
        self.assertTrue(mock_page.locator.called)

class TestAgentMocking(unittest.TestCase):
    def test_bezier_curve_points(self):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        start_x, start_y = 10, 20
        end_x, end_y = 200, 300
        steps = 30
        
        points = manager.calculate_bezier_points(start_x, start_y, end_x, end_y, steps)
        self.assertEqual(len(points), steps + 1)
        self.assertEqual(points[0], (start_x, start_y))
        self.assertEqual(points[-1], (end_x, end_y))
        for x, y in points:
            self.assertIsInstance(x, int)
            self.assertIsInstance(y, int)

    def test_device_profile_rotation(self):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        profile = manager.generate_device_profile()
        self.assertIn("name", profile)
        self.assertIn("ua", profile)
        self.assertIn("platform", profile)
        self.assertIn("viewport", profile)
        self.assertIn("device_scale_factor", profile)
        
        # Verify viewport width and height are integers
        self.assertIsInstance(profile["viewport"]["width"], int)
        self.assertIsInstance(profile["viewport"]["height"], int)

    @patch("playwright.async_api.Page")
    def test_network_throttling_mapping(self, mock_page_class):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        mock_page = MagicMock()
        mock_cdp = MagicMock()
        
        async def mock_cdp_session(page_arg):
            return mock_cdp
        mock_page.context.new_cdp_session = mock_cdp_session
        
        called = False
        async def mock_send(method, params):
            nonlocal called
            called = True
            # Verify correct parameters mapped
            if method == "Network.emulateNetworkConditions":
                self.assertEqual(params["offline"], False)
                self.assertGreater(params["latency"], 0)
                self.assertGreater(params["downloadThroughput"], 0)
                self.assertGreater(params["uploadThroughput"], 0)
        mock_cdp.send = mock_send
        
        asyncio.run(manager.configure_network_throttling(mock_page, "Slow 3G"))
        self.assertTrue(called)

    def test_proxy_parsing(self):
        from app.browser import PlaywrightManager
        manager = PlaywrightManager()
        
        # Test basic proxy IP:Port without protocol
        res = manager._parse_proxy("12.34.56.78:9000")
        self.assertEqual(res, {"server": "http://12.34.56.78:9000"})
        
        # Test proxy IP:Port with http:// protocol
        res = manager._parse_proxy("http://12.34.56.78:9000")
        self.assertEqual(res, {"server": "http://12.34.56.78:9000"})
        
        # Test proxy with credentials and protocol
        res = manager._parse_proxy("socks5://myuser:mypass@1.2.3.4:1080")
        self.assertEqual(res, {
            "server": "socks5://1.2.3.4:1080",
            "username": "myuser",
            "password": "mypass"
        })
        
        # Test proxy with credentials and no protocol
        res = manager._parse_proxy("user:pwd@5.6.7.8:8080")
        self.assertEqual(res, {
            "server": "http://5.6.7.8:8080",
            "username": "user",
            "password": "pwd"
        })
        
        # Test None
        self.assertIsNone(manager._parse_proxy(None))
        self.assertIsNone(manager._parse_proxy(""))

class TestTelemetryEngine(unittest.TestCase):
    def test_scrape_result_schema_telemetry(self):
        from app.schemas import ScrapeResultSchema
        # Verify schema accepts telemetry field
        res = ScrapeResultSchema(
            status="success",
            url="https://example.com",
            telemetry={
                "requests": [{"url": "https://example.com", "method": "GET", "headers": {"user-agent": "test"}}],
                "responses": [{"url": "https://example.com", "status": 200, "headers": {"server": "test"}}],
                "failed_resources": [
                    {"url": "https://example.com/asset.js", "resource_type": "script", "status": 404, "reason": "HTTP 404 Error"}
                ],
                "console_errors": [
                    {"type": "error", "text": "Uncaught SyntaxError", "location": {"url": "https://example.com/main.js"}}
                ]
            }
        )
        self.assertIn("requests", res.telemetry)
        self.assertEqual(res.telemetry["requests"][0]["url"], "https://example.com")
        self.assertEqual(res.telemetry["failed_resources"][0]["resource_type"], "script")
        self.assertEqual(res.telemetry["console_errors"][0]["type"], "error")

class TestDataQualityValidation(unittest.TestCase):
    def test_text_deduplication(self):
        title = "Target Title"
        content = "Target Title\nFirst paragraph\nSecond paragraph\nFirst paragraph\n\nSecond paragraph\n"
        dedup_content, raw_count, dedup_count = ContentExtractor.deduplicate_text(title, content)
        self.assertEqual(dedup_content, "First paragraph\nSecond paragraph")
        self.assertEqual(raw_count, 5)
        self.assertEqual(dedup_count, 2)

    def test_image_health_checker(self):
        # Healthy image
        h1 = ContentExtractor.check_image_health("https://example.com/logo.png", "Company Logo")
        self.assertTrue(h1["healthy"])
        self.assertIsNone(h1["issue"])

        # Missing src
        h2 = ContentExtractor.check_image_health("", "Empty Src")
        self.assertFalse(h2["healthy"])
        self.assertEqual(h2["issue"], "missing_src")

        # Base64 placeholder
        h3 = ContentExtractor.check_image_health("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "Base64 Pixel")
        self.assertFalse(h3["healthy"])
        self.assertEqual(h3["issue"], "inline_base64_placeholder")

        # Broken URL (invalid characters or missing parts)
        h4 = ContentExtractor.check_image_health("https://{domain}/image.png", "Broken URL")
        self.assertFalse(h4["healthy"])
        self.assertEqual(h4["issue"], "broken_url")

        # Unresolved relative path
        h5 = ContentExtractor.check_image_health("/assets/img.png", "Relative Path")
        self.assertFalse(h5["healthy"])
        self.assertEqual(h5["issue"], "unresolved_relative_path")

        # Layout placeholders
        h6 = ContentExtractor.check_image_health("https://example.com/pixel.gif", "Spacer")
        self.assertFalse(h6["healthy"])
        self.assertEqual(h6["issue"], "layout_placeholder")

        h7 = ContentExtractor.check_image_health("https://example.com/img.png", "loading placeholder spinner")
        self.assertFalse(h7["healthy"])
        self.assertEqual(h7["issue"], "layout_placeholder")

    def test_metric_formulas(self):
        from app.main import run_prototype
        
        async def mock_capture(*args, **kwargs):
            html = """
            <html>
                <head>
                    <title>Test Page</title>
                </head>
                <body>
                    <h1>Test Page</h1>
                    <p>This is a long paragraph that should be long enough to exceed the 100 character length threshold. We want to test how the completeness score, confidence score, and quality score are calculated based on this content.</p>
                    <img src="https://example.com/image.png" alt="Healthy image" />
                    <img src="https://example.com/pixel.gif" alt="Layout spacer" />
                    <a href="https://example.com/link1">Link 1</a>
                </body>
            </html>
            """
            screenshots = []
            browser_logs = [
                {"type": "error", "text": "Console error occurred"},
                {"text": "warning: Bounding box not found for click"}
            ]
            metrics = {
                "dom_ready_time": 100.0,
                "load_duration": 200.0,
                "total_payload_bytes": 1024,
                "user_agent": "mock-ua",
                "proxy": None,
                "status_code": 200,
                "headers": {},
                "redirect_chain": [{"url": "https://redirect1.com"}, {"url": "https://redirect2.com"}]
            }
            return html, screenshots, browser_logs, metrics

        with patch("app.extractor.ContentExtractor.check_robots_allowed", return_value=True), \
             patch("app.browser.PlaywrightManager.capture_page", side_effect=mock_capture), \
             patch("app.main.verify_link_status", return_value={"url": "https://example.com/link1", "status_code": 200, "status": "active"}), \
             patch("app.downloader.AssetDownloader.download_asset", return_value={"original_url": "https://example.com/image.png", "local_path": "storage/assets/image.png", "mime_type": "image/png", "file_size": 100}):
            
            result = asyncio.run(run_prototype("https://example.com", max_pages=1))
            
            self.assertEqual(result.status, "success")
            self.assertEqual(result.metadata["completeness_score"], 1.0)
            self.assertEqual(result.metadata["confidence_score"], 0.75)
            self.assertEqual(result.metadata["quality_score"], 0.39)
            self.assertEqual(result.quality_score, 0.39)

class TestIncrementalCrawling(unittest.TestCase):
    def setUp(self):
        self.test_history_path = "storage/test_crawl_history.json"
        if os.path.exists(self.test_history_path):
            os.remove(self.test_history_path)
        self.mgr = HistoryManager(self.test_history_path)

    def tearDown(self):
        if os.path.exists(self.test_history_path):
            os.remove(self.test_history_path)

    def test_calculate_sha256(self):
        self.assertEqual(calculate_sha256(""), calculate_sha256(None))
        self.assertEqual(calculate_sha256("hello"), "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")

    def test_sync_status_full_to_incremental_no_change(self):
        url = "https://example.com/target"
        content = "Some extracted body text contents."
        dom = "<html><body>Some extracted body text contents.</body></html>"
        
        # 1st call: should be Full Sync
        s1 = self.mgr.get_sync_status(url, content, dom)
        self.assertEqual(s1["sync_type"], "Full Sync")
        self.assertTrue(s1["change_detected"])
        self.assertIsNone(s1["optimization_signal"])
        
        # Save a page record
        self.mgr.save_page_record(url, s1["content_hash"], s1["dom_hash"], {"title": "Target"}, [])
        
        # 2nd call: identical content, should be Incremental Delta Sync (NO_CHANGE)
        mgr2 = HistoryManager(self.test_history_path)
        s2 = mgr2.get_sync_status(url, content, dom)
        self.assertEqual(s2["sync_type"], "Incremental Delta Sync")
        self.assertFalse(s2["change_detected"])
        self.assertEqual(s2["optimization_signal"], "NO_CHANGE")

    def test_sync_status_with_changes_and_delta(self):
        url = "https://example.com/target"
        content1 = "Original text content."
        dom1 = "<html><body>Original text content.</body></html>"
        
        s1 = self.mgr.get_sync_status(url, content1, dom1)
        page_data1 = {
            "title": "Original Title",
            "description": "Original description.",
            "content": content1,
            "links": ["https://example.com/1", "https://example.com/2"]
        }
        self.mgr.save_page_record(url, s1["content_hash"], s1["dom_hash"], page_data1, [])
        
        # Modify content and verify CHANGES_DETECTED and delta extraction
        content2 = "Modified text content."
        dom2 = "<html><body>Modified text content.</body></html>"
        
        s2 = self.mgr.get_sync_status(url, content2, dom2)
        self.assertEqual(s2["sync_type"], "Incremental Delta Sync")
        self.assertTrue(s2["change_detected"])
        self.assertEqual(s2["optimization_signal"], "CHANGES_DETECTED")
        
        page_data2 = {
            "title": "Modified Title",
            "description": "Original description.",
            "content": content2,
            "links": ["https://example.com/1", "https://example.com/3"]
        }
        
        delta = self.mgr.compute_delta(s2["old_entry"], page_data2)
        self.assertIn("title", delta)
        self.assertEqual(delta["title"]["old"], "Original Title")
        self.assertEqual(delta["title"]["new"], "Modified Title")
        
        self.assertNotIn("description", delta)
        
        self.assertIn("content", delta)
        self.assertEqual(delta["content"]["new"], "Modified text content.")
        
        self.assertIn("links", delta)
        self.assertEqual(delta["links"]["new"], ["https://example.com/1", "https://example.com/3"])

    def test_asset_caching_and_version_tracking(self):
        asset_url = "https://example.com/logo.png"
        asset_props = {
            "original_url": asset_url,
            "local_path": "storage/assets/logo.png",
            "mime_type": "image/png",
            "file_size": 500,
            "version": 1
        }
        
        self.mgr.save_page_record("https://example.com", "h1", "h2", {}, [asset_props])
        
        cached = self.mgr.get_cached_asset(asset_url)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["version"], 1)
        self.assertEqual(cached["local_path"], "storage/assets/logo.png")
        
        self.mgr.save_page_record("https://example.com", "h1", "h2", {}, [asset_props])
        cached2 = self.mgr.get_cached_asset(asset_url)
        self.assertEqual(cached2["version"], 2)

    def test_run_prototype_incremental_flow(self):
        from app.main import run_prototype
        
        async def mock_capture(*args, **kwargs):
            html = """
            <html>
                <head>
                    <title>Test Page</title>
                </head>
                <body>
                    <h1>Test Page</h1>
                    <p>Some standard content paragraph layout.</p>
                    <img src="https://example.com/image.png" alt="Healthy image" />
                </body>
            </html>
            """
            screenshots = []
            browser_logs = []
            metrics = {
                "dom_ready_time": 100.0,
                "load_duration": 200.0,
                "total_payload_bytes": 1024,
                "user_agent": "mock-ua",
                "proxy": None,
                "status_code": 200,
                "headers": {}
            }
            return html, screenshots, browser_logs, metrics

        with patch("app.history.HistoryManager.__init__", lambda obj, *args, **kwargs: setattr(obj, "history_path", self.test_history_path) or setattr(obj, "history", obj._load_history())), \
             patch("app.extractor.ContentExtractor.check_robots_allowed", return_value=True), \
             patch("app.browser.PlaywrightManager.capture_page", side_effect=mock_capture), \
             patch("app.downloader.AssetDownloader.download_asset", return_value={"original_url": "https://example.com/image.png", "local_path": "storage/assets/image.png", "mime_type": "image/png", "file_size": 100}):
            
            # First run: Full Sync
            r1 = asyncio.run(run_prototype("https://example.com/mock", max_pages=1))
            self.assertEqual(r1.status, "success")
            self.assertEqual(r1.metadata["sync_type"], "Full Sync")
            self.assertEqual(r1.images[0].version, 1)
            
            # Second run: identical content, Incremental Delta Sync (NO_CHANGE)
            r2 = asyncio.run(run_prototype("https://example.com/mock", max_pages=1))
            self.assertEqual(r2.status, "success")
            self.assertEqual(r2.metadata["sync_type"], "Incremental Delta Sync")
            self.assertEqual(r2.metadata["optimization_signal"], "NO_CHANGE")
            self.assertEqual(r2.images[0].version, 2)

class TestConcurrencyAndRetry(unittest.TestCase):
    def setUp(self):
        from app.queue_manager import ScrapeQueueCoordinator
        self.coordinator = ScrapeQueueCoordinator()
        self.coordinator.reset(concurrency_limit=2)

    def tearDown(self):
        self.coordinator.reset()

    @patch("app.main.run_prototype")
    def test_coordinator_concurrency(self, mock_run):
        async def mock_run_impl(url, **kwargs):
            await asyncio.sleep(0.05)
            return {"url": url, "status": "success"}
        mock_run.side_effect = mock_run_impl

        async def run_async_test():
            self.coordinator.reset(concurrency_limit=2)
            self.coordinator.start_workers(num_workers=2)
            
            f1 = await self.coordinator.add_task("https://url1.com", {})
            f2 = await self.coordinator.add_task("https://url2.com", {})
            f3 = await self.coordinator.add_task("https://url3.com", {})
            
            res1 = await f1
            res2 = await f2
            res3 = await f3
            
            self.assertEqual(res1["status"], "success")
            self.assertEqual(res2["status"], "success")
            self.assertEqual(res3["status"], "success")
            self.assertEqual(self.coordinator.processed_count, 3)
            
        asyncio.run(run_async_test())

    def test_idempotent_url_lock(self):
        from app.main import run_prototype
        
        event = asyncio.Event()
        first_call_started = asyncio.Event()
        
        async def mock_capture(*args, **kwargs):
            first_call_started.set()
            await event.wait()
            return "<html></html>", [], [], {
                "dom_ready_time": 1.0,
                "load_duration": 1.0,
                "total_payload_bytes": 10,
                "user_agent": "mock",
                "proxy": None,
                "status_code": 200,
                "headers": {}
            }

        async def run_concurrent():
            task1 = asyncio.create_task(run_prototype("https://locked-url.com"))
            await first_call_started.wait()
            res2 = await run_prototype("https://locked-url.com")
            event.set()
            res1 = await task1
            return res1, res2

        with patch("app.extractor.ContentExtractor.check_robots_allowed", return_value=True), \
             patch("app.failures.retry_on_antibot", side_effect=mock_capture):
            res1, res2 = asyncio.run(run_concurrent())
            
            self.assertEqual(res1.status, "success")
            self.assertEqual(res2.status, "failed")
            self.assertEqual(res2.failure_category, "ACCESS")
            self.assertIn("Idempotent Lock active", res2.failure_reason)
            self.assertEqual(res2.metadata["optimization_signal"], "SKIPPED_CONCURRENT_LOCK")

    def test_exponential_backoff_math(self):
        import random
        for attempt in [1, 2, 3]:
            backoff_sec = (2 ** attempt) + random.uniform(0.0, 1.0)
            self.assertGreaterEqual(backoff_sec, 2 ** attempt)
            self.assertLessEqual(backoff_sec, (2 ** attempt) + 1.0)

    def test_run_prototype_transient_retry_success(self):
        from app.main import run_prototype
        from app.failures import NetworkError
        
        attempts = []
        
        async def mock_capture(*args, **kwargs):
            attempts.append(len(attempts) + 1)
            if len(attempts) == 1:
                raise NetworkError("Transient DNS failure")
            return "<html></html>", [], [], {
                "dom_ready_time": 1.0,
                "load_duration": 1.0,
                "total_payload_bytes": 10,
                "user_agent": "mock",
                "proxy": None,
                "status_code": 200,
                "headers": {}
            }

        async def run_test():
            with patch("asyncio.sleep", return_value=None) as mock_sleep:
                res = await run_prototype("https://transient-retry.com")
                self.assertEqual(res.status, "success")
                self.assertEqual(len(attempts), 2)
                self.assertEqual(len(res.metadata["scale_diagnostics"]["retry_history"]), 1)
                
                retry_info = res.metadata["scale_diagnostics"]["retry_history"][0]
                self.assertEqual(retry_info["attempt"], 1)
                self.assertEqual(retry_info["category"], "NETWORK")
                self.assertIn("Transient DNS failure", retry_info["error"])
                self.assertIn("backoff_seconds", retry_info)
                
                mock_sleep.assert_called_once()
                called_backoff = mock_sleep.call_args[0][0]
                self.assertTrue(2.0 <= called_backoff <= 3.0)

        with patch("app.extractor.ContentExtractor.check_robots_allowed", return_value=True), \
             patch("app.failures.retry_on_antibot", side_effect=mock_capture):
            asyncio.run(run_test())

    def test_run_prototype_transient_retry_exhausted(self):
        from app.main import run_prototype
        from app.failures import NetworkError
        
        attempts = []
        
        async def mock_capture(*args, **kwargs):
            attempts.append(len(attempts) + 1)
            raise NetworkError(f"Persistent network failure {len(attempts)}")

        async def run_test():
            with patch("asyncio.sleep", return_value=None) as mock_sleep:
                res = await run_prototype("https://persistent-fail.com")
                self.assertEqual(res.status, "failed")
                self.assertEqual(res.failure_category, "NETWORK")
                self.assertEqual(len(attempts), 3)
                
                retry_history = res.metadata["scale_diagnostics"]["retry_history"]
                self.assertEqual(len(retry_history), 3)
                self.assertEqual(retry_history[0]["attempt"], 1)
                self.assertEqual(retry_history[1]["attempt"], 2)
                self.assertEqual(retry_history[2]["attempt"], 3)
                
                self.assertEqual(mock_sleep.call_count, 2)

        with patch("app.extractor.ContentExtractor.check_robots_allowed", return_value=True), \
             patch("app.failures.retry_on_antibot", side_effect=mock_capture):
            asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
