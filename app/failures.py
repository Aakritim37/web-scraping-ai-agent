# app/failures.py
import asyncio
import random
import re

class ScraperError(Exception):
    """Base exception class for all scraper errors."""
    pass

class NetworkError(ScraperError):
    """Raised on connection/DNS/timeout/SSL errors."""
    pass

class RobotsBlockedError(ScraperError):
    """Raised when crawling is blocked by robots.txt rules."""
    pass

class RobotsTxtError(RobotsBlockedError):
    """Raised when crawling is blocked by robots.txt rules."""
    pass

class DnsTimeoutError(NetworkError):
    """Raised when DNS resolution or connection times out."""
    pass

class SslHandshakeError(NetworkError):
    """Raised when SSL/TLS handshake fails."""
    pass

class PaywallDetectedError(ScraperError):
    """Raised when a paywall is detected."""
    pass

class AntiBotChallengeError(ScraperError):
    """Raised when blocked by an anti-bot system (e.g. Cloudflare, CAPTCHA)."""
    pass

class AkamaiBlockedError(AntiBotChallengeError):
    """Raised when blocked by Akamai bot mitigation."""
    pass

class DataDomeBlockedError(AntiBotChallengeError):
    """Raised when blocked by DataDome bot mitigation."""
    pass

class ScraperTimeoutError(NetworkError):
    """Raised when the scraping operation times out."""
    pass

class HttpStatusError(ScraperError):
    """Raised when server returns error HTTP status codes."""
    pass

class AccessError(ScraperError):
    """Raised when credentials or subscription login is required."""
    pass

class ContentError(ScraperError):
    """Raised when content is missing, blank, or extraction/schema validation fails."""
    pass

class ShadowDomTimeoutError(NetworkError):
    """Raised when shadow DOM navigation or rendering times out."""
    pass


def classify_failure(exception: Exception = None, status_code: int = None, page_content: str = "", headers: dict = None) -> dict:
    """
    Analyzes an exception, HTTP status code, page content, and/or response headers
    to identify and categorize the scraper failure.
    
    Returns:
        dict: A dictionary containing:
            - 'category': One of 'NETWORK', 'HTTP_STATUS', 'ANTI_BOT', 'ACCESS', 'PAYWALLS', 'ROBOTS_TXT', 'CONTENT'
            - 'reason': A friendly descriptive string.
    """
    exc_str = str(exception).lower() if exception else ""
    content_lower = page_content.lower() if page_content else ""
    headers_lower = {}
    if headers:
        headers_lower = {str(k).lower(): str(v).lower() for k, v in headers.items()}

    # 1. Pre-flight Robots.txt policy validation / Robots Blocked Check
    if isinstance(exception, (RobotsBlockedError, RobotsTxtError)) or "robots.txt" in exc_str:
        return {
            "category": "ROBOTS_TXT",
            "reason": "Crawling is disallowed by target site's robots.txt policy."
        }

    # 2. Paywall Check (signatures & status codes & exceptions)
    paywall_patterns = [
        "premium-content", "subscription-wall", "subscribe-to-read", "subscribe to read",
        "please log in to continue", "register to read the full article", "premium content",
        "subscribers only", "paywall", "subscription required", "purchase a subscription",
        "membership required"
    ]
    has_paywall_header = any(k in headers_lower for k in ["x-subscription-required", "x-paywall", "x-premium-content"])
    if (
        isinstance(exception, PaywallDetectedError) or
        status_code == 402 or
        has_paywall_header or
        any(p in exc_str for p in paywall_patterns) or
        any(p in content_lower for p in paywall_patterns)
    ):
        return {
            "category": "PAYWALLS",
            "reason": "Access restricted by subscription paywall or login requirement."
        }

    # 2.5 Akamai and DataDome Checks
    akamai_patterns = ["akamai.net", "an activity identifier", "reference id:"]
    datadome_patterns = ["datadome", "captcha-delivery.com", "dd="]
    
    if (
        isinstance(exception, AkamaiBlockedError) or
        any(p in exc_str for p in akamai_patterns) or
        any(p in content_lower for p in akamai_patterns)
    ):
        return {
            "category": "ANTI_BOT",
            "reason": "Access blocked by Akamai Bot Mitigation challenge screen."
        }
        
    if (
        isinstance(exception, DataDomeBlockedError) or
        any(p in exc_str for p in datadome_patterns) or
        any(p in content_lower for p in datadome_patterns)
    ):
        return {
            "category": "ANTI_BOT",
            "reason": "Access blocked by DataDome Bot Protection challenge screen."
        }

    # 3. Anti-bot / CAPTCHA Check (including Cloudflare, CAPTCHAs, Turnstile, Amazon block screens)
    antibot_patterns = [
        "cloudflare", "captcha", "distil networks", "please enable javascript and cookies",
        "access denied", "checking your browser", "ddos protection", "human verification",
        "attention required", "security challenge", "recaptcha", "hcaptcha", "perimeterx",
        "bot detection", "automated requests", "amazon.com/gp/errors/validatecaptcha",
        "enter the characters you see below", "to discuss automated access to amazon data",
        "api-services@amazon.com", "solve this captcha", "g-recaptcha", "robot check",
        "cf-challenge", "cf-turnstile", "turnstile", "recaptcha-token"
    ]
    has_cf_header = (
        any(k in headers_lower for k in ["cf-ray", "cf-request-id", "cf-cache-status", "__cf_bm", "cf-cookie"]) or
        any("cloudflare" in str(v) for v in headers_lower.values()) or
        any("perimeterx" in str(v) for v in headers_lower.values()) or
        any("distil" in str(v) for v in headers_lower.values())
    )
    if (
        isinstance(exception, AntiBotChallengeError) or
        status_code in (403, 503) and (any(p in content_lower for p in antibot_patterns) or has_cf_header) or
        has_cf_header or
        any(p in exc_str for p in antibot_patterns) or
        any(p in content_lower for p in antibot_patterns)
    ):
        for pattern in antibot_patterns:
            if pattern in exc_str or pattern in content_lower:
                return {
                    "category": "ANTI_BOT",
                    "reason": f"Access blocked by anti-bot challenge wall or protection system ({pattern})."
                }
        return {
            "category": "ANTI_BOT",
            "reason": "Access blocked by anti-bot challenge wall or protection system."
        }

    # 4. Shadow DOM Navigation/Rendering Timeouts Check
    is_shadow_timeout = isinstance(exception, ShadowDomTimeoutError) or (
        any(p in exc_str for p in ["shadow", "shadowroot", "shadow-root"]) and
        any(p in exc_str for p in ["timeout", "timed out", "navigation", "waiting for selector"])
    )
    if is_shadow_timeout:
        return {
            "category": "NETWORK",
            "reason": f"Shadow DOM navigation or rendering timed out: {exception or 'Shadow DOM Timeout'}"
        }

    # 5. DNS & Connection Timeout & SSL/TLS Error Check
    network_patterns = [
        "timeout", "timed out", "net::err_name_not_resolved", "net::err_connection_timed_out",
        "err_connection_refused", "name_not_resolved", "connection refused", "connection timed out",
        "ssl_protocol_error", "err_cert_", "ssl handshake", "ssl certificate", 
        "certificate verify failed", "tls handshake", "untrusted certificate"
    ]
    if (
        isinstance(exception, (DnsTimeoutError, SslHandshakeError, ScraperTimeoutError, NetworkError)) or 
        any(p in exc_str for p in network_patterns)
    ):
        if "name_not_resolved" in exc_str or "dns" in exc_str:
            return {
                "category": "NETWORK",
                "reason": "DNS resolution failed. The domain name may not exist or is unreachable."
            }
        if any(p in exc_str for p in ["ssl", "cert", "handshake"]):
            return {
                "category": "NETWORK",
                "reason": f"SSL/TLS secure handshake failed: {exception or 'Invalid certificate'}"
            }
        return {
            "category": "NETWORK",
            "reason": f"Network connection timed out: {exception or 'Connection timed out'}"
        }

    # 6. Access Control Check (e.g. HTTP 401, 403 Forbidden without anti-bot signals)
    if (
        isinstance(exception, AccessError) or
        status_code == 401 or
        status_code == 403 or
        any(p in exc_str for p in ["unauthorized", "login required", "authentication required", "access denied", "forbidden"])
    ):
        return {
            "category": "ACCESS",
            "reason": f"Access denied. Credentials or subscription login required (HTTP {status_code or 403})."
        }

    # 7. Content & Extraction Failures Check
    content_patterns = ["content-extraction-error", "invalid-schema", "empty-body"]
    if (
        isinstance(exception, ContentError) or
        not page_content or
        page_content.strip() == "" or
        len(page_content.strip()) < 10 or
        any(p in content_lower for p in content_patterns) or
        any(p in exc_str for p in ["empty html", "extraction failed", "missing content", "invalid json", "schema mismatch", "empty content"])
    ):
        return {
            "category": "CONTENT",
            "reason": "Page content is empty, missing, or failed extraction validation checks."
        }

    # 8. HTTP status code failure (other 4xx/5xx code)
    if isinstance(exception, HttpStatusError) or (status_code and status_code >= 400):
        return {
            "category": "HTTP_STATUS",
            "reason": f"Server returned error HTTP status code {status_code}."
        }

    # 9. Generic Scraper / Unhandled Exception
    if not exception and (status_code is None or status_code < 400):
        return {
            "category": "SUCCESS",
            "reason": "Scraping completed successfully."
        }
        
    return {
        "category": "CONTENT",
        "reason": f"Scraping execution error: {str(exception)}" if exception else "An unknown execution failure occurred."
    }


async def retry_on_antibot(async_func, *args, max_retries=3, **kwargs):
    """
    Executes an async function (such as capture_page) and retries it if an 
    AntiBotChallengeError is raised, rotating session settings or introducing backoff.
    
    Args:
        async_func: Async function to execute.
        *args: Positional arguments for async_func.
        max_retries (int): Maximum attempts.
        **kwargs: Keyword arguments for async_func.
        
    Returns:
        The result of async_func.
        
    Raises:
        AntiBotChallengeError: If all attempts failed due to blocks.
        Exception: Any other unhandled error.
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] Scraper execution attempt {attempt}/{max_retries}...")
            return await async_func(*args, **kwargs)
        except AntiBotChallengeError as e:
            print(f"[!] Scraper block / CAPTCHA detected on attempt {attempt}: {str(e)}")
            if attempt < max_retries:
                backoff = random.uniform(3.0, 6.0)
                print(f"[*] Backing off for {backoff:.2f} seconds before retrying...")
                await asyncio.sleep(backoff)
            else:
                print("[-] Bypassing failed. Retries exhausted.")
                raise e
        except Exception as e:
            # Check if this exception can be classified as anti-bot block (e.g. from page response properties)
            err_info = classify_failure(exception=e)
            if err_info["category"].upper() == "ANTI_BOT":
                print(f"[!] General error classified as anti-bot block: {str(e)}")
                if attempt < max_retries:
                    backoff = random.uniform(3.0, 6.0)
                    print(f"[*] Backing off for {backoff:.2f} seconds before retrying...")
                    await asyncio.sleep(backoff)
                    continue
            raise e
