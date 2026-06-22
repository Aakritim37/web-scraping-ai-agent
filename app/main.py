# app/main.py
import asyncio
import json
import sys
import requests
from app.browser import PlaywrightManager
from app.extractor import ContentExtractor
from app.downloader import AssetDownloader
from app.schemas import ScrapeResultSchema
from app.failures import classify_failure, RobotsBlockedError
from app.queue_manager import ScrapeQueueCoordinator

def verify_link_status_sync(url: str) -> dict:
    """
    Performs a synchronous HEAD request with a GET fallback to check if a link is active.
    Returns a dict with {"url": url, "status_code": status_code, "status": "active"|"broken"}
    """
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    headers = {"User-Agent": user_agent}
    try:
        # First try HEAD
        resp = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        # Fallback to GET if HEAD fails or returns standard error codes
        if resp.status_code >= 400 or resp.status_code in (404, 405, 501):
            resp = requests.get(url, headers=headers, timeout=5, stream=True, allow_redirects=True)
        
        status_code = resp.status_code
        status_str = "active" if status_code < 400 else "broken"
        return {
            "url": url,
            "status_code": status_code,
            "status": status_str
        }
    except Exception as e:
        return {
            "url": url,
            "status_code": None,
            "status": "broken",
            "error": str(e)
        }

async def verify_link_status(url: str) -> dict:
    """
    Runs verify_link_status_sync in a non-blocking way using run_in_executor.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_link_status_sync, url)


def merge_tables(all_tables_list: list) -> list:
    """
    Merges tables across pages.
    If two tables have identical headers (ignoring whitespace and case), we merge their rows.
    """
    merged_tables = []
    for page_tables in all_tables_list:
        for tbl in page_tables:
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            
            # Find if we already have a table in merged_tables with the same headers
            matched = False
            norm_headers = [h.strip().lower() for h in headers]
            for m_tbl in merged_tables:
                m_headers = m_tbl.get("headers", [])
                norm_m_headers = [h.strip().lower() for h in m_headers]
                if norm_headers == norm_m_headers:
                    # Append rows, avoiding duplicate rows if they are exactly the same
                    for r in rows:
                        if r not in m_tbl["rows"]:
                            m_tbl["rows"].append(r)
                    matched = True
                    break
            if not matched:
                merged_tables.append({
                    "headers": headers,
                    "rows": list(rows)
                })
    return merged_tables

def merge_scraped_pages(parsed_pages: list, base_url: str) -> dict:
    if not parsed_pages:
        return {}
    
    first = parsed_pages[0]
    merged = {
        "title": first.get("title", "No Title"),
        "description": first.get("description", ""),
        "content": "",
        "links": [],
        "internal_links": [],
        "external_links": [],
        "download_links": [],
        "images": [],
        "documents": [],
        "lists": [],
        "tables": [],
        "json_ld": [],
        "social_metadata": {},
        "headings_list": [],
        "canonical_url": first.get("canonical_url"),
        "keywords": [],
        "charset": first.get("charset"),
        "logos": [],
        "svgs": [],
        "videos": []
    }
    
    seen_links = set()
    seen_internal = set()
    seen_external = set()
    seen_downloads = set()
    seen_images = set()
    seen_docs = set()
    seen_logos = set()
    seen_svgs = set()
    seen_videos = set()
    seen_keywords = set()
    
    all_contents = []
    all_headings = []
    all_json_ld = []
    all_tables_list = []
    
    for page in parsed_pages:
        content_str = page.get("content", "")
        if content_str:
            all_contents.append(content_str)
            
        headings = page.get("headings_list", [])
        for h in headings:
            if h not in all_headings:
                all_headings.append(h)
                
        for l in page.get("links", []):
            if l not in seen_links:
                seen_links.add(l)
                merged["links"].append(l)
                
        for l in page.get("internal_links", []):
            if l not in seen_internal:
                seen_internal.add(l)
                merged["internal_links"].append(l)
                
        for l in page.get("external_links", []):
            if l not in seen_external:
                seen_external.add(l)
                merged["external_links"].append(l)
                
        for l in page.get("download_links", []):
            if l not in seen_downloads:
                seen_downloads.add(l)
                merged["download_links"].append(l)
                
        for img in page.get("images", []):
            img_url = img.get("url")
            if img_url and img_url not in seen_images:
                seen_images.add(img_url)
                merged["images"].append(img)
                
        for doc in page.get("documents", []):
            if doc not in seen_docs:
                seen_docs.add(doc)
                merged["documents"].append(doc)
                
        merged["lists"].extend(page.get("lists", []))
        all_tables_list.append(page.get("tables", []))
        
        for jd in page.get("json_ld", []):
            if jd not in all_json_ld:
                all_json_ld.append(jd)
                
        merged["social_metadata"].update(page.get("social_metadata", {}))
        
        for kw in page.get("keywords", []):
            if kw not in seen_keywords:
                seen_keywords.add(kw)
                merged["keywords"].append(kw)
                
        for logo in page.get("logos", []):
            if logo not in seen_logos:
                seen_logos.add(logo)
                merged["logos"].append(logo)
                
        for svg in page.get("svgs", []):
            if svg not in seen_svgs:
                seen_svgs.add(svg)
                merged["svgs"].append(svg)
                
        for video in page.get("videos", []):
            if video not in seen_videos:
                seen_videos.add(video)
                merged["videos"].append(video)

    merged_content = "\n".join(all_contents)
    dedup_merged, raw_p_count, dedup_p_count = ContentExtractor.deduplicate_text(merged["title"], merged_content)
    merged["content"] = dedup_merged
    merged["raw_content_length"] = len(merged_content)
    merged["raw_paragraphs_count"] = sum(p.get("raw_paragraphs_count", 0) for p in parsed_pages)
    merged["dedup_paragraphs_count"] = dedup_p_count
    
    merged["headings_list"] = all_headings
    merged["json_ld"] = all_json_ld
    merged["tables"] = merge_tables(all_tables_list)
    
    return merged

ACTIVE_SCRAPE_URLS = set()

async def run_prototype(
    url: str,
    form_actions: list = None,
    next_page_selector: str = None,
    max_pages: int = 1,
    session_persistence: bool = True,
    cookie_bypass: bool = True,
    proxy_server: str = None,
    network_throttling: str = "Fastest",
    **kwargs
):
    global ACTIVE_SCRAPE_URLS
    if "ACTIVE_SCRAPE_URLS" not in globals():
        ACTIVE_SCRAPE_URLS = set()
        
    coordinator = ScrapeQueueCoordinator()
        
    if url in ACTIVE_SCRAPE_URLS:
        warning_msg = f"Idempotent Lock active: URL {url} is currently being processed."
        print(f"[!] {warning_msg}")
        
        final_output = ScrapeResultSchema(
            status="failed",
            failure_category="ACCESS",
            failure_reason=warning_msg,
            url=url,
            metadata={
                "error_details": warning_msg,
                "optimization_signal": "SKIPPED_CONCURRENT_LOCK",
                "scale_diagnostics": {
                    "active_concurrency_slots": coordinator.active_slots,
                    "task_backlog": coordinator.queue.qsize(),
                    "total_processed_tasks": coordinator.processed_count,
                    "retry_history": []
                }
            },
            quality_score=0.0
        )
        
        output_filename = "prototype_output.json"
        with open(output_filename, "w") as f:
            json.dump(final_output.model_dump(), f, indent=4)
        return final_output
        
    ACTIVE_SCRAPE_URLS.add(url)
    
    retry_history = []
    
    try:
        print(f"[*] Initializing universal agent target thread: {url}")
        
        # Pre-flight Robots.txt policy validation
        print("[*] Running pre-flight robots.txt check...")
        if not ContentExtractor.check_robots_allowed(url, user_agent="*"):
            error_msg = f"Crawling is disallowed for {url} by the site's robots.txt rules."
            print(f"[-] {error_msg}")
            
            final_output = ScrapeResultSchema(
                status="failed",
                failure_category="ROBOTS_TXT",
                failure_reason=error_msg,
                url=url,
                metadata={
                    "error_details": "Robots.txt crawl check failed.",
                    "failure_metadata": {
                        "category": "ROBOTS_TXT",
                        "reason": error_msg,
                        "exception_class": "RobotsTxtError"
                    },
                    "scale_diagnostics": {
                        "active_concurrency_slots": coordinator.active_slots,
                        "task_backlog": coordinator.queue.qsize(),
                        "total_processed_tasks": coordinator.processed_count,
                        "retry_history": retry_history
                    }
                },
                quality_score=0.0
            )
            
            output_filename = "prototype_output.json"
            with open(output_filename, "w") as f:
                json.dump(final_output.model_dump(), f, indent=4)
            print(f"[✓] Failure log written to '{output_filename}'.")
            return final_output

        # Initialize PlaywrightManager with the proxy if provided
        proxy_list = [proxy_server] if proxy_server else None
        browser_agent = PlaywrightManager(proxy_list=proxy_list)
        downloader = AssetDownloader()

        for attempt in range(1, 4):
            try:
                # Step 1: Capture page using the automated retry logic from failures.py
                from app.failures import retry_on_antibot
                html_data, screenshots, browser_logs, metrics = await retry_on_antibot(
                    browser_agent.capture_page,
                    url,
                    form_actions=form_actions,
                    next_page_selector=next_page_selector,
                    max_pages=max_pages,
                    session_persistence=session_persistence,
                    cookie_bypass=cookie_bypass,
                    network_throttling=network_throttling
                )
                
                # Step 2: Deep parsing of page layout components using upgraded BeautifulSoup engine
                if isinstance(html_data, list):
                    parsed_pages = []
                    for p_html in html_data:
                        parsed_pages.append(ContentExtractor.extract(p_html, url))
                    parsed_data = merge_scraped_pages(parsed_pages, url)
                else:
                    parsed_data = ContentExtractor.extract(html_data, url)

                # ─── INCREMENTAL CRAWLING AND CHANGE DETECTION ───
                from app.history import HistoryManager
                history_mgr = HistoryManager()
                
                joined_html = "".join(html_data) if isinstance(html_data, list) else html_data
                sync_info = history_mgr.get_sync_status(url, parsed_data.get("content", ""), joined_html)
                
                sync_type = sync_info["sync_type"]
                change_detected = sync_info["change_detected"]
                content_hash = sync_info["content_hash"]
                dom_hash = sync_info["dom_hash"]
                optimization_signal = sync_info["optimization_signal"]
                
                old_entry = sync_info["old_entry"]
                delta = {}
                
                downloaded_images = []
                verified_results = []
                
                if optimization_signal == "NO_CHANGE" and old_entry:
                    # Skip checking links and downloading images.
                    # Retrieve previously saved assets and increment version tracker
                    old_assets = old_entry.get("assets", {})
                    for asset_url, cached_asset in old_assets.items():
                        updated_asset = dict(cached_asset)
                        updated_asset["version"] = cached_asset.get("version", 1) + 1
                        downloaded_images.append(updated_asset)
                        
                    # Copy verified links
                    old_full = old_entry.get("full_scrape_result", {})
                    verified_results = old_full.get("verified_links", [])
                    
                    # Save page record to persist updated version counters in history
                    parsed_data["verified_links"] = verified_results
                    history_mgr.save_page_record(url, content_hash, dom_hash, parsed_data, downloaded_images)
                else:
                    if sync_type == "Incremental Delta Sync" and old_entry:
                        delta = history_mgr.compute_delta(old_entry, parsed_data)
                        optimization_signal = "CHANGES_DETECTED"
                    else:
                        optimization_signal = "FULL_SYNC"
                        
                    # Step 3: Loop and download/cache layout images
                    for img_info in parsed_data["images"][:2]: 
                        img_url = img_info["url"]
                        if img_url.startswith("http") and not img_url.endswith(".gif"):
                            cached_asset = history_mgr.get_cached_asset(img_url)
                            if cached_asset:
                                print(f"[+] Reusing cached layout asset: {img_url}")
                                asset_info = dict(cached_asset)
                                asset_info["version"] = cached_asset.get("version", 1) + 1
                                asset_info["healthy"] = img_info.get("healthy", True)
                                asset_info["issue"] = img_info.get("issue")
                                downloaded_images.append(asset_info)
                            else:
                                print(f"[+] Downloading layout asset: {img_url}")
                                asset_info = downloader.download_asset(
                                    img_url,
                                    alt_text=img_info.get("alt"),
                                    width=img_info.get("width"),
                                    height=img_info.get("height")
                                )
                                if asset_info:
                                    asset_info["version"] = 1
                                    asset_info["healthy"] = img_info.get("healthy", True)
                                    asset_info["issue"] = img_info.get("issue")
                                    downloaded_images.append(asset_info)
                    
                    # Step 3.5: Run concurrent non-blocking broken link verification on first 10 links
                    links_to_verify = parsed_data["links"][:10]
                    if links_to_verify:
                        print(f"[*] Verifying status of {len(links_to_verify)} discovered links...")
                        verified_results = await asyncio.gather(*[verify_link_status(link) for link in links_to_verify])
                        
                    # Save the new/updated page record and cache the assets
                    parsed_data["verified_links"] = verified_results
                    history_mgr.save_page_record(url, content_hash, dom_hash, parsed_data, downloaded_images)

                # Step 4: Compute Multidimensional Verification Scores
                # 4.1 Completeness Score calculation
                has_title = 1.0 if parsed_data.get("title") and parsed_data["title"] != "No Title" else 0.0
                clean_text = parsed_data.get("content", "")
                has_content = 1.0 if len(clean_text) >= 100 else (len(clean_text) / 100.0)
                has_images = 1.0 if parsed_data.get("images") else 0.0
                has_links = 1.0 if parsed_data.get("links") else 0.0
                completeness_score = round(0.30 * has_title + 0.40 * has_content + 0.15 * has_images + 0.15 * has_links, 2)

                # 4.2 Confidence Score calculation
                confidence_score = 1.0
                console_errors = sum(1 for log in browser_logs if log.get("type") == "error")
                confidence_score -= min(console_errors * 0.05, 0.20)
                redirect_hops = len(metrics.get("redirect_chain", []))
                confidence_score -= min(redirect_hops * 0.05, 0.20)
                
                # Scan browser execution logs for fallbacks
                had_fallback_click = any(
                    "warning: bounding box not found" in str(log.get("text", "")).lower() or
                    "humanized bezier click failed" in str(log.get("text", "")).lower()
                    for log in browser_logs
                )
                if had_fallback_click:
                    confidence_score -= 0.10
                    
                had_soft_timeout = any("soft timeout: network did not quiet down" in str(log.get("text", "")).lower() for log in browser_logs)
                if had_soft_timeout:
                    confidence_score -= 0.10
                    
                confidence_score = max(round(confidence_score, 2), 0.0)

                # 4.3 Integrated Quality Score Heuristic
                content_len = len(clean_text)
                content_length_factor = min(content_len / 1000.0, 1.0)
                
                raw_p_count = parsed_data.get("raw_paragraphs_count", 0)
                dedup_p_count = parsed_data.get("dedup_paragraphs_count", 0)
                dedup_factor = dedup_p_count / raw_p_count if raw_p_count > 0 else 1.0
                
                total_imgs = len(parsed_data.get("images", []))
                healthy_imgs = sum(1 for img in parsed_data.get("images", []) if img.get("healthy", True))
                healthy_img_rate = healthy_imgs / total_imgs if total_imgs > 0 else 1.0
                
                quality_score = round(0.40 * content_length_factor + 0.30 * dedup_factor + 0.30 * healthy_img_rate, 2)

                # Scale & Concurrency Telemetry
                scale_diagnostics = {
                    "active_concurrency_slots": coordinator.active_slots,
                    "task_backlog": coordinator.queue.qsize(),
                    "total_processed_tasks": coordinator.processed_count,
                    "retry_history": retry_history
                }

                # Step 5: Bind details to ScrapeResultSchema
                final_output = ScrapeResultSchema(
                    status="success",
                    url=url,
                    title=parsed_data["title"],
                    content=parsed_data["content"][:400] + "..." if len(parsed_data["content"]) > 400 else parsed_data["content"],
                    images=downloaded_images,
                    links=parsed_data["links"][:5],  # preview top 5 links
                    metadata={
                        "description": parsed_data["description"],
                        "headings": parsed_data["headings_list"],
                        "lists": parsed_data["lists"],
                        "tables": parsed_data["tables"],
                        "json_ld": parsed_data["json_ld"],
                        "social_metadata": parsed_data["social_metadata"],
                        "performance": {
                            "dom_ready_time_ms": metrics["dom_ready_time"],
                            "load_duration_ms": metrics["load_duration"],
                            "total_payload_bytes": metrics["total_payload_bytes"],
                            "user_agent": metrics["user_agent"],
                            "proxy": metrics["proxy"],
                            "status_code": metrics["status_code"]
                        },
                        "completeness_score": completeness_score,
                        "confidence_score": confidence_score,
                        "quality_score": quality_score,
                        "data_quality_metrics": {
                            "raw_content_length": parsed_data.get("raw_content_length", 0),
                            "raw_paragraphs_count": raw_p_count,
                            "dedup_paragraphs_count": dedup_p_count,
                            "dedup_rate": round(dedup_factor, 2),
                            "total_images": total_imgs,
                            "healthy_images": healthy_imgs,
                            "broken_images": total_imgs - healthy_imgs,
                            "healthy_image_rate": round(healthy_img_rate, 2),
                            "had_fallback_click": had_fallback_click,
                            "had_soft_timeout": had_soft_timeout
                        },
                        "telemetry": metrics.get("telemetry", {}),
                        "sync_type": sync_type,
                        "change_detected": change_detected,
                        "delta": delta,
                        "content_hash": content_hash,
                        "dom_hash": dom_hash,
                        "optimization_signal": optimization_signal,
                        "scale_diagnostics": scale_diagnostics
                    },
                    telemetry=metrics.get("telemetry", {}),
                    screenshots=screenshots,
                    logs=browser_logs,
                    quality_score=quality_score,
                    canonical_url=parsed_data["canonical_url"],
                    keywords=parsed_data["keywords"],
                    charset=parsed_data["charset"],
                    status_code=metrics["status_code"],
                    response_headers=metrics["headers"],
                    tables=parsed_data["tables"],
                    internal_links=parsed_data["internal_links"],
                    external_links=parsed_data["external_links"],
                    redirect_chain=metrics.get("redirect_chain", []),
                    verified_links=verified_results,
                    download_links=parsed_data["download_links"],
                    logos=parsed_data.get("logos", []),
                    svgs=parsed_data.get("svgs", []),
                    videos=parsed_data.get("videos", []),
                    desktop_above_fold=metrics.get("desktop_above_fold"),
                    mobile_view=metrics.get("mobile_view"),
                    tablet_view=metrics.get("tablet_view")
                )

                # Step 6: Convert model data to JSON and save to disk
                output_filename = "prototype_output.json"
                with open(output_filename, "w") as f:
                    json.dump(final_output.model_dump(), f, indent=4)
                    
                print(f"\n[✓] Scraping loop completed successfully! File '{output_filename}' generated.")
                return final_output

            except Exception as e:
                err_info = classify_failure(exception=e)
                category = err_info["category"]
                reason = err_info["reason"]
                
                if category in ("NETWORK", "HTTP_STATUS", "CONTENT") and attempt < 3:
                    import random
                    backoff_sec = (2 ** attempt) + random.uniform(0.0, 1.0)
                    retry_log = {
                        "attempt": attempt,
                        "error": str(e),
                        "category": category,
                        "reason": reason,
                        "backoff_seconds": backoff_sec
                    }
                    retry_history.append(retry_log)
                    print(f"[!] Transient error ({category}) on attempt {attempt}: {e}. Retrying in {backoff_sec:.2f} seconds...")
                    await asyncio.sleep(backoff_sec)
                    continue
                else:
                    retry_log = {
                        "attempt": attempt,
                        "error": str(e),
                        "category": category,
                        "reason": reason
                    }
                    retry_history.append(retry_log)
                    raise e

    except Exception as e:
        print(f"[-] Execution error caught: {str(e)}")
        err_info = classify_failure(exception=e)
        
        scale_diagnostics = {
            "active_concurrency_slots": coordinator.active_slots,
            "task_backlog": coordinator.queue.qsize(),
            "total_processed_tasks": coordinator.processed_count,
            "retry_history": retry_history
        }

        final_output = ScrapeResultSchema(
            status="failed",
            failure_category=err_info["category"],
            failure_reason=err_info["reason"],
            url=url,
            metadata={
                "error_details": str(e),
                "failure_metadata": {
                    "category": err_info["category"],
                    "reason": err_info["reason"],
                    "exception_class": e.__class__.__name__
                },
                "scale_diagnostics": scale_diagnostics
            },
            quality_score=0.0
        )
        
        output_filename = "prototype_output.json"
        with open(output_filename, "w") as f:
            json.dump(final_output.model_dump(), f, indent=4)
        print(f"[✓] Failure log written to '{output_filename}'.")
        return final_output
        
    finally:
        ACTIVE_SCRAPE_URLS.discard(url)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_site = sys.argv[1]
    else:
        target_site = "https://quotes.toscrape.com/js/" 
        
    asyncio.run(run_prototype(target_site))