# app/extractor.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class ContentExtractor:
    @staticmethod
    def extract(html_content: str, base_url: str) -> dict:
        """
        Parses raw HTML layout markup and converts it into a clean,
        structured dictionary of text elements and link pathways.
        """
        # Load the raw HTML into BeautifulSoup's scanning engine
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Harvest Page Metadata
        title = soup.title.string.strip() if soup.title else "No Title"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"].strip() if meta_desc else ""

        # 2. Harvest Semantic Layout Text Structure (Headings & Paragraphs)
        # We loop through h1, h2, h3 tags to capture section titles
        headings = [h.text.strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.text.strip()]
        # We collect all paragraph blocks containing text
        paragraphs = [p.text.strip() for p in soup.find_all("p") if p.text.strip()]
        
        # Combine everything into one readable string layout block
        combined_content = "\n".join(headings + paragraphs)

        # 3. Harvest Navigation Links safely
        links = []
        for a in soup.find_all("a", href=True):
            # Convert relative paths (like '/about') into absolute links (like 'https://site.com/about')
            absolute_url = urljoin(base_url, a["href"])
            links.append(absolute_url)

        # 4. Harvest Asset source URLs (Images and Document targets)
        image_urls = [urljoin(base_url, img["src"]) for img in soup.find_all("img", src=True)]
        doc_urls = [urljoin(base_url, a["href"]) for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]

        # Return data dictionary package to the main worker script
        return {
            "title": title,
            "description": description,
            "content": combined_content,
            "links": list(set(links)),       # list(set()) removes any duplicate elements
            "images": list(set(image_urls)),
            "documents": list(set(doc_urls))
        }