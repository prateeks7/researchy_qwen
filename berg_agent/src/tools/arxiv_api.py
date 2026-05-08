import time
import arxiv
from langchain_core.tools import tool
from src.tools.utils.pdf_processor import download_and_parse_pdf

_MAX_QUERY_LEN = 200
_ARXIV_RETRIES = 3
_ARXIV_RETRY_DELAYS = [5, 15, 30]

_STOP_WORDS = {'a', 'an', 'the', 'of', 'in', 'on', 'for', 'and', 'or', 'to', 'with', 'from', 'by', 'at'}


def _clean_query(query: str) -> str:
    """Trim whitespace, strip anything after a newline, cap length."""
    q = query.strip().split("\n")[0].strip()
    return q[:_MAX_QUERY_LEN]


def _title_matches(returned_title: str, query: str, threshold: float = 0.25) -> bool:
    """Check that the returned paper title shares enough words with the query."""
    t_words = set(returned_title.lower().split()) - _STOP_WORDS
    q_words = set(query.lower().split()) - _STOP_WORDS
    if not q_words or not t_words:
        return True
    overlap = len(t_words & q_words) / len(q_words)
    return overlap >= threshold


def _arxiv_search(search: arxiv.Search, max_results: int) -> list:
    """Run an arXiv search with retry logic for rate-limit (429/503) errors."""
    client = arxiv.Client(delay_seconds=3)
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
            results.append(
                f"{divider}\n"
                f"[{i}] {paper.title}\n"
                f"    📅 {paper.published.strftime('%Y-%m-%d')}  |  🏷  {categories}\n"
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
    Useful for DOWNLOADING and DEEP READING a single, specific paper.
    Input should be an exact title or ArXiv ID (e.g. '2301.07041').
    Use this when the user asks for a summary, metrics, or comparisons of a specific paper.
    """
    query = _clean_query(query)
    print(f"🤖 Agent called download_and_parse_arxiv_paper with query: {query}")

    search = arxiv.Search(query=query, max_results=1, sort_by=arxiv.SortCriterion.Relevance)
    try:
        papers = _arxiv_search(search, max_results=1)
        if not papers:
            return f"No paper found on arXiv for query: {query}"
        paper = papers[0]
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"

    if not _title_matches(paper.title, query):
        return (
            f"arXiv did not find a matching paper for '{query}'. "
            f"The closest result was '{paper.title}', which does not appear to be the right paper. "
            f"This paper may not be on arXiv, or try a different search query. "
            f"Consider using search_arxiv_papers or web_search_tool to locate it first."
        )

    return download_and_parse_pdf(
        pdf_url=paper.pdf_url,
        title=paper.title,
        source_id=paper.get_short_id(),
        date_published=paper.published.strftime("%Y-%m-%d"),
        categories=paper.categories
    )