# app/extractor.py
import json
import re
import urllib.robotparser
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class ContentExtractor:
    @staticmethod
    def check_robots_allowed(url: str, user_agent: str = "*") -> bool:
        """
        Fetches and reads the target site's robots.txt rules to verify if crawling is allowed.
        
        Args:
            url (str): The target URL to check.
            user_agent (str): The crawling agent name. Defaults to '*'.
            
        Returns:
            bool: True if crawling is allowed, False otherwise.
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            # Request robots.txt with a brief 5-second timeout
            response = requests.get(robots_url, timeout=5)
            
            if response.status_code == 404:
                return True
            elif response.status_code in (401, 403):
                return False
                
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(response.text.splitlines())
            return rp.can_fetch(user_agent, url)
        except Exception:
            # In case of network errors fetching robots.txt, we default to allowed
            return True

    @staticmethod
    def get_clean_text(element) -> str:
        """
        Recursively extracts text from BeautifulSoup elements, including TemplateString
        nodes nested inside <template> shadow roots, while ignoring comments.
        """
        if not element:
            return ""
        if isinstance(element, str):
            if type(element).__name__ in ('Comment', 'Declaration', 'Doctype', 'ProcessingInstruction'):
                return ""
            return str(element)
        
        texts = []
        for child in element.children:
            if isinstance(child, str):
                if type(child).__name__ in ('Comment', 'Declaration', 'Doctype', 'ProcessingInstruction'):
                    continue
                texts.append(str(child))
            else:
                texts.append(ContentExtractor.get_clean_text(child))
        return "".join(texts).strip()

    @staticmethod
    def get_element_base_url(element, default_base_url: str) -> str:
        """
        Recursively traverses parents of the element to determine the correct base URL
        when nested inside same-origin <iframe-content> nodes.
        """
        curr = element.parent
        while curr:
            if curr.name == "iframe-content" and curr.get("src"):
                iframe_src = curr["src"].strip()
                if iframe_src:
                    parent_base = ContentExtractor.get_element_base_url(curr, default_base_url)
                    return urljoin(parent_base, iframe_src)
            curr = curr.parent
        return default_base_url

    @staticmethod
    def deduplicate_text(title: str, content: str) -> tuple:
        """
        Deduplicates paragraphs/lines in the content and cross-references with the title
        to remove repetitive entries.
        
        Returns:
            tuple: (deduplicated_content_str, raw_paragraphs_count, dedup_paragraphs_count)
        """
        if not content:
            return "", 0, 0
        
        normalized_title = title.strip().lower()
        seen = set()
        unique_paragraphs = []
        raw_paragraphs_count = 0
        
        # Split by newline
        for line in content.split("\n"):
            cleaned_line = line.strip()
            if not cleaned_line:
                continue
            
            raw_paragraphs_count += 1
            norm_line = cleaned_line.lower()
            
            # Cross-reference with title (ignore if it's the page title itself repeated in content)
            if norm_line == normalized_title:
                continue
                
            if norm_line not in seen:
                seen.add(norm_line)
                unique_paragraphs.append(cleaned_line)
                
        return "\n".join(unique_paragraphs), raw_paragraphs_count, len(unique_paragraphs)

    @staticmethod
    def check_image_health(img_url: str, alt_text: str = "") -> dict:
        """
        Scans an image URL and alt text to identify if it is healthy or has issues
        (broken, missing src, or placeholder).
        
        Returns:
            dict: {"healthy": bool, "issue": str or None}
        """
        if not img_url:
            return {"healthy": False, "issue": "missing_src"}
            
        img_url_lower = img_url.lower().strip()
        alt_lower = alt_text.lower().strip() if alt_text else ""
        
        # Check base64 data URIs - they are embedded inline, usually placeholder/transparents
        if img_url_lower.startswith("data:image/"):
            return {"healthy": False, "issue": "inline_base64_placeholder"}
            
        # Parse URL
        parsed = urlparse(img_url)
        
        # Check relative URL fallback check (should have been resolved by extractor)
        if img_url_lower.startswith(("/", "./", "../")):
            return {"healthy": False, "issue": "unresolved_relative_path"}
            
        # Check if URL is broken (e.g. missing scheme/netloc, containing curly braces, invalid format)
        if not parsed.scheme or not parsed.netloc or "{" in img_url_lower or "}" in img_url_lower:
            return {"healthy": False, "issue": "broken_url"}
            
        # Check placeholder references in URL or Alt Text
        placeholder_keywords = [
            "placeholder", "spacer", "pixel", "blank", "spinner", "loading",
            "dummy", "temp", "holder.js", "lorem", "ipsum"
        ]
        
        for kw in placeholder_keywords:
            if kw in img_url_lower or kw in alt_lower:
                return {"healthy": False, "issue": "layout_placeholder"}
                
        return {"healthy": True, "issue": None}

    @staticmethod
    def extract(html_content: str, base_url: str) -> dict:
        """
        Parses raw HTML layout markup and converts it into a structured
        dictionary containing metadata, headings (H1-H6), body text, links, 
        media assets, lists, tables, social tags, JSON-LD data, and technical/SEO fields.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        base_netloc = urlparse(base_url).netloc
        
        # 1. Harvest Page Metadata
        title = soup.title.string.strip() if soup.title else "No Title"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"].strip() if meta_desc else ""

        # 2. Harvest headings (H1 to H6)
        headings = [ContentExtractor.get_clean_text(h) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]) if ContentExtractor.get_clean_text(h)]
        paragraphs = [ContentExtractor.get_clean_text(p) for p in soup.find_all("p") if ContentExtractor.get_clean_text(p)]
        combined_content = "\n".join(headings + paragraphs)
        raw_content_len = len(combined_content)
        
        # Run text deduplication
        dedup_content, raw_p_count, dedup_p_count = ContentExtractor.deduplicate_text(title, combined_content)

        # 3. Harvest & Classify Navigation Links safely
        links = []
        internal_links = []
        external_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # Skip empty, javascript, mailto, tel, or anchor links
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            elem_base = ContentExtractor.get_element_base_url(a, base_url)
            absolute_url = urljoin(elem_base, href)
            links.append(absolute_url)
            
            # Domain-level classification
            link_netloc = urlparse(absolute_url).netloc
            if not link_netloc or link_netloc == base_netloc or link_netloc.endswith("." + base_netloc) or base_netloc.endswith("." + link_netloc):
                internal_links.append(absolute_url)
            else:
                external_links.append(absolute_url)

        links = list(set(links))
        internal_links = list(set(internal_links))
        external_links = list(set(external_links))

        # Helper to parse dimensions
        def parse_dimension(val):
            if not val:
                return None
            match = re.search(r"(\d+)", str(val))
            return int(match.group(1)) if match else None

        # 4. Harvest Asset details (Images with alt-text, width, height) and run health checks
        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                elem_base = ContentExtractor.get_element_base_url(img, base_url)
                abs_src = urljoin(elem_base, src)
                alt = img.get("alt", "").strip() or None
                w_val = parse_dimension(img.get("width"))
                h_val = parse_dimension(img.get("height"))
                
                # Check image health status
                health = ContentExtractor.check_image_health(abs_src, alt if alt else "")
                images.append({
                    "url": abs_src,
                    "alt": alt,
                    "width": w_val,
                    "height": h_val,
                    "healthy": health["healthy"],
                    "issue": health["issue"]
                })
                
        doc_urls = [urljoin(ContentExtractor.get_element_base_url(a, base_url), a["href"]) for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")]

        # 4.2 Logo detection
        logos = []
        # Link icons
        for link in soup.find_all("link", rel=True):
            rel = [r.lower() for r in link["rel"]]
            if any(r in rel for r in ["icon", "shortcut icon", "apple-touch-icon", "mask-icon"]):
                href = link.get("href")
                if href:
                    elem_base = ContentExtractor.get_element_base_url(link, base_url)
                    logos.append(urljoin(elem_base, href))
        # Image logos
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                img_id = img.get("id", "")
                img_class = " ".join(img.get("class", [])) if isinstance(img.get("class"), list) else img.get("class", "") or ""
                img_alt = img.get("alt", "") or ""
                
                is_logo = (
                    "logo" in src.lower() or "brand" in src.lower() or
                    "logo" in img_id.lower() or "brand" in img_id.lower() or
                    "logo" in img_class.lower() or "brand" in img_class.lower() or
                    "logo" in img_alt.lower() or "brand" in img_alt.lower()
                )
                if is_logo:
                    elem_base = ContentExtractor.get_element_base_url(img, base_url)
                    logos.append(urljoin(elem_base, src))
        
        seen_logos = set()
        unique_logos = []
        for logo in logos:
            if logo not in seen_logos:
                seen_logos.add(logo)
                unique_logos.append(logo)

        # 4.3 Inline SVG extraction
        svgs = [str(svg).strip() for svg in soup.find_all("svg")[:10]]

        # 4.4 Attached Video URL extraction
        videos = []
        for video in soup.find_all("video"):
            src = video.get("src")
            if src:
                elem_base = ContentExtractor.get_element_base_url(video, base_url)
                videos.append(urljoin(elem_base, src))
        for source in soup.find_all("source"):
            src = source.get("src")
            if src:
                parent_name = source.parent.name if source.parent else ""
                mime_type = source.get("type", "")
                if parent_name == "video" or mime_type.startswith("video/"):
                    elem_base = ContentExtractor.get_element_base_url(source, base_url)
                    videos.append(urljoin(elem_base, src))
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src")
            if src:
                if any(domain in src.lower() for domain in ["youtube.com", "youtu.be", "vimeo.com", "player.vimeo"]):
                    elem_base = ContentExtractor.get_element_base_url(iframe, base_url)
                    videos.append(urljoin(elem_base, src))
        video_extensions = (".mp4", ".webm", ".mov", ".ogg", ".avi", ".mkv")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if any(href.lower().endswith(ext) for ext in video_extensions):
                elem_base = ContentExtractor.get_element_base_url(a, base_url)
                videos.append(urljoin(elem_base, href))

        seen_videos = set()
        unique_videos = []
        for video in videos:
            if video not in seen_videos:
                seen_videos.add(video)
                unique_videos.append(video)

        # 4.1 Download Link Detection
        download_extensions = (
            ".zip", ".tar.gz", ".tgz", ".tar", ".rar", ".7z",
            ".exe", ".dmg", ".msi", ".bin",
            ".pdf", ".csv", ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx",
            ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv"
        )
        download_links = [link for link in links if any(link.lower().endswith(ext) for ext in download_extensions)]

        # 5. Extract Ordered / Unordered Lists
        lists = []
        for lst in soup.find_all(["ul", "ol"]):
            items = [ContentExtractor.get_clean_text(li) for li in lst.find_all("li") if ContentExtractor.get_clean_text(li)]
            if items:
                lists.append({
                    "type": lst.name,
                    "items": items
                })

        # 6. Extract Table Elements (Robust Parsing)
        tables = []
        for tbl in soup.find_all("table"):
            # Extract header cell text
            th_elements = tbl.find_all("th")
            headers = [ContentExtractor.get_clean_text(th) for th in th_elements if ContentExtractor.get_clean_text(th)]
            
            rows = []
            for tr in tbl.find_all("tr"):
                # Collect cells containing text
                row_cells = [ContentExtractor.get_clean_text(td) for td in tr.find_all(["td", "th"])]
                if not row_cells:
                    continue
                # Skip if this row merely repeats header values
                if headers and row_cells == headers:
                    continue
                rows.append(row_cells)
                
            if headers or rows:
                tables.append({
                    "headers": headers,
                    "rows": rows
                })

        # 7. Parse JSON-LD Blocks
        json_ld = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    data = json.loads(script.string.strip())
                    if isinstance(data, (dict, list)):
                        json_ld.append(data)
                except Exception:
                    pass

        # 8. Parse OpenGraph and Twitter Social Metadata
        social_metadata = {}
        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            content = meta.get("content")
            if prop and content:
                if prop.startswith("og:") or prop.startswith("twitter:"):
                    social_metadata[prop] = content.strip()

        # 9. Technical & SEO Metadata Extraction
        # 9.1 Canonical URL
        canonical_link = soup.find("link", rel="canonical")
        canonical_url = None
        if canonical_link and canonical_link.get("href"):
            canonical_url = urljoin(base_url, canonical_link["href"].strip())

        # 9.2 Keywords list
        keywords_meta = soup.find("meta", attrs={"name": "keywords"})
        keywords = []
        if keywords_meta and keywords_meta.get("content"):
            keywords = [k.strip() for k in keywords_meta["content"].split(",") if k.strip()]

        # 9.3 Charset Detection
        charset = None
        meta_charset = soup.find("meta", charset=True)
        if meta_charset:
            charset = meta_charset["charset"].strip()
        else:
            meta_content_type = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "content-type"})
            if meta_content_type and meta_content_type.get("content"):
                match = re.search(r"charset=([^\s;]+)", meta_content_type["content"], re.IGNORECASE)
                if match:
                    charset = match.group(1).strip()

        return {
            "title": title,
            "description": description,
            "content": dedup_content,
            "raw_content_length": raw_content_len,
            "raw_paragraphs_count": raw_p_count,
            "dedup_paragraphs_count": dedup_p_count,
            "links": links,
            "internal_links": internal_links,
            "external_links": external_links,
            "download_links": download_links,
            "images": images,
            "documents": list(set(doc_urls)),
            "lists": lists,
            "tables": tables,
            "json_ld": json_ld,
            "social_metadata": social_metadata,
            "headings_list": headings,
            "canonical_url": canonical_url,
            "keywords": keywords,
            "charset": charset,
            "logos": unique_logos,
            "svgs": svgs,
            "videos": unique_videos
        }