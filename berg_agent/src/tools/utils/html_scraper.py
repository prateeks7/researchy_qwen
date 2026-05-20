import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def scrape_arxiv_html(arxiv_id: str) -> Optional[str]:
    """
    Scrape full paper text from ar5iv.org (HTML rendering of ArXiv papers).
    Falls back to abstract-only from arxiv.org/abs if ar5iv unavailable.
    Returns raw text or None if both fail.
    """
    from bs4 import BeautifulSoup

    arxiv_id = arxiv_id.split("v")[0]

    # Tier 1: ar5iv.org — full paper as HTML (~100K+ chars)
    try:
        url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
        print(f"   🌐 Scraping full paper: {url}")
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            if text and len(text) > 2000:
                print(f"   ✅ Full paper scraped: {len(text)} chars")
                return text
    except Exception as e:
        logger.warning("ar5iv scrape failed for %s: %s", arxiv_id, e)

    # Tier 2: arxiv.org/abs — abstract only (~1.5K chars)
    try:
        url = f"https://arxiv.org/abs/{arxiv_id}"
        print(f"   🌐 Falling back to abstract: {url}")
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        parts = []
        title_elem = soup.find("h1", class_="title")
        if title_elem:
            parts.append(title_elem.get_text(strip=True).replace("Title:", "").strip())
        abstract_elem = soup.find("blockquote", class_="abstract")
        if abstract_elem:
            parts.append(abstract_elem.get_text(strip=True).replace("Abstract:", "").strip())

        if len(parts) >= 2:
            text = "\n\n".join(parts)
            print(f"   ✅ Abstract scraped: {len(text)} chars")
            return text
    except Exception as e:
        logger.warning("ArXiv abs scrape failed for %s: %s", arxiv_id, e)

    print(f"   ❌ All ArXiv scrape attempts failed for {arxiv_id}")
    return None


def scrape_pubmed_html(pmc_id: str) -> Optional[str]:
    """
    Scrape full article text from PubMed Central.
    Returns raw text or None if fails.
    """
    try:
        from bs4 import BeautifulSoup

        pmc_id = pmc_id.replace("PMC", "").strip()
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/"
        print(f"   🌐 Scraping PubMed: {url}")

        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        # Try article body first, fall back to full page
        body = soup.select_one("#article-body, .article-body, article")
        text = (body or soup).get_text(separator="\n", strip=True)

        if text and len(text) > 200:
            print(f"   ✅ PubMed scraped: {len(text)} chars")
            return text

        return None

    except Exception as e:
        logger.warning("PubMed scrape failed for PMC%s: %s", pmc_id, e)
        print(f"   ❌ PubMed scrape failed: {e}")
        return None


def scrape_generic_url(url: str) -> Optional[str]:
    """
    Generic HTML scraper for any paper URL (Semantic Scholar, etc).
    Returns raw text or None if fails.
    """
    try:
        from bs4 import BeautifulSoup

        print(f"   🌐 Scraping URL: {url}")
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        if text and len(text) > 200:
            print(f"   ✅ Generic scrape: {len(text)} chars")
            return text

        return None

    except Exception as e:
        logger.warning("Generic scrape failed for %s: %s", url, e)
        print(f"   ❌ Generic scrape failed: {e}")
        return None
