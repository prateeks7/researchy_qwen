import re
import time
import arxiv
from langchain_core.tools import tool
from src.tools.utils.pdf_processor import download_and_parse_pdf

_MAX_QUERY_LEN = 200
_ARXIV_RETRIES = 2
_ARXIV_RETRY_DELAYS = [5, 15]

_STOP_WORDS = {'a', 'an', 'the', 'of', 'in', 'on', 'for', 'and', 'or', 'to', 'with', 'from', 'by', 'at', 'is', 'are', 'you', 'do', 'not', 'all', 'need'}

_ARXIV_ID_RE = re.compile(r'^\d{4}\.\d{4,5}(v\d+)?$')

# In-memory session cache: stores paper metadata from recent searches.
# Key: lowercased title. Avoids re-calling ArXiv API when user asks to
# download a paper that was already returned in a search.
_recent_papers: dict = {}


def _clean_query(query: str) -> str:
    q = query.strip().split("\n")[0].strip()
    return q[:_MAX_QUERY_LEN]


def _title_overlap(title: str, query: str) -> float:
    """Fraction of non-trivial query words that appear in the title."""
    t_words = set(title.lower().split()) - _STOP_WORDS
    q_words = set(query.lower().split()) - _STOP_WORDS
    if not q_words or not t_words:
        return 0.0
    return len(t_words & q_words) / len(q_words)


def _best_session_cache_match(query: str, threshold: float = 0.6):
    """Return the best-matching cached paper above threshold, or None."""
    best_meta, best_score = None, 0.0
    for title_key, meta in _recent_papers.items():
        score = _title_overlap(title_key, query)
        if score > best_score:
            best_score, best_meta = score, meta
    return best_meta if best_score >= threshold else None


def _arxiv_search(search: arxiv.Search, max_results: int) -> list:
    """Run an arXiv search with retry logic for rate-limit (429/503) errors."""
    client = arxiv.Client(delay_seconds=3, page_size=max_results, num_retries=1)
    for attempt in range(_ARXIV_RETRIES):
        try:
            return list(client.results(search))
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("429", "503", "rate", "too many")) and attempt < _ARXIV_RETRIES - 1:
                wait = _ARXIV_RETRY_DELAYS[attempt]
                print(f"⏳ arXiv rate-limited — retrying in {wait}s (attempt {attempt+1}/{_ARXIV_RETRIES})")
                time.sleep(wait)
            else:
                raise
    return []


@tool
def search_arxiv_papers(query: str) -> str:
    """
    Useful for SEARCHING for multiple papers related to a topic to recommend to the user.
    Input should be a search query (e.g., 'Physical AI humanoid').
    Returns a list of papers with their titles, arXiv IDs, and abstracts.
    Does NOT download or read the full paper content.
    """
    query = _clean_query(query)
    print(f"🤖 Agent called search_arxiv_papers with query: {query}")

    search = arxiv.Search(query=query, max_results=5, sort_by=arxiv.SortCriterion.Relevance)
    divider = "─" * 60
    try:
        papers = _arxiv_search(search, max_results=5)
        if not papers:
            return f"No papers found on arXiv for query: {query}"
        results = []
        for i, paper in enumerate(papers, 1):
            categories = ", ".join(paper.categories[:5])
            _recent_papers[paper.title.lower()] = {
                "arxiv_id": paper.get_short_id(),
                "pdf_url": paper.pdf_url,
                "title": paper.title,
                "published": paper.published.strftime("%Y-%m-%d"),
                "categories": paper.categories,
            }
            results.append(
                f"{divider}\n"
                f"[{i}] {paper.title}\n"
                f"    📅 {paper.published.strftime('%Y-%m-%d')}  |  🏷  {categories}\n"
                f"    🔑 arXiv ID: {paper.get_short_id()}  |  📚 SOURCE: arXiv\n"
                f"    🔗 {paper.pdf_url}\n"
                f"{divider}\n"
                f"{paper.summary[:500]}...\n"
            )
        return f"arXiv Search Results for: \"{query}\"\n\n" + "\n".join(results)
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"


@tool
def download_and_parse_arxiv_paper(query: str) -> str:
    """
    Downloads and deeply reads a single specific paper.
    Input: exact paper title OR arXiv ID (e.g. '1706.03762').
    Use when the user asks for a summary, methodology, or results of a specific paper.
    If you have the arXiv ID from a previous search, pass it directly — do not re-search.
    """
    query = _clean_query(query)
    print(f"🤖 Agent called download_and_parse_arxiv_paper with query: {query}")

    # Direct arXiv ID lookup — bypass text search entirely
    if _ARXIV_ID_RE.match(query):
        arxiv_id = query.split("v")[0]
        search = arxiv.Search(id_list=[arxiv_id])
        try:
            papers = _arxiv_search(search, max_results=1)
            if papers:
                paper = papers[0]
                return download_and_parse_pdf(
                    pdf_url=paper.pdf_url,
                    title=paper.title,
                    source_id=paper.get_short_id(),
                    date_published=paper.published.strftime("%Y-%m-%d"),
                    categories=paper.categories,
                )
        except Exception as e:
            return f"Error fetching arXiv ID {query}: {str(e)}"
        return f"No paper found for arXiv ID: {query}"

    # Session cache — use best match with high threshold (0.6) to avoid false hits
    cached_meta = _best_session_cache_match(query)
    if cached_meta:
        print(f"   💾 Session cache hit: '{cached_meta['title']}'")
        return download_and_parse_pdf(
            pdf_url=cached_meta["pdf_url"],
            title=cached_meta["title"],
            source_id=cached_meta["arxiv_id"],
            date_published=cached_meta["published"],
            categories=cached_meta["categories"],
        )

    # Text search fallback — use higher threshold (0.6) to avoid wrong-paper matches
    search = arxiv.Search(query=query, max_results=1, sort_by=arxiv.SortCriterion.Relevance)
    try:
        papers = _arxiv_search(search, max_results=1)
        if not papers:
            return f"No paper found on arXiv for: '{query}'"
        paper = papers[0]
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"

    if _title_overlap(paper.title, query) < 0.6:
        return (
            f"arXiv text search for '{query}' returned '{paper.title}', which doesn't look like the right paper. "
            f"Try calling search_arxiv_papers first to find the correct arXiv ID, then pass the ID directly."
        )

    return download_and_parse_pdf(
        pdf_url=paper.pdf_url,
        title=paper.title,
        source_id=paper.get_short_id(),
        date_published=paper.published.strftime("%Y-%m-%d"),
        categories=paper.categories,
    )