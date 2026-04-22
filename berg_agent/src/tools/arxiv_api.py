import arxiv
from langchain_core.tools import tool
from src.tools.utils.pdf_processor import download_and_parse_pdf

@tool
def search_arxiv_papers(query: str) -> str:
    """
    Useful for SEARCHING for multiple papers related to a topic to recommend to the user.
    Input should be a search query (e.g., 'Physical AI humanoid').
    Returns a list of papers with their titles, arXiv IDs, and abstracts.
    Does NOT download or read the full paper content.
    """
    print(f"🤖 Agent called search_arxiv_papers with query: {query}")

    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=5, sort_by=arxiv.SortCriterion.Relevance)
    
    divider = "─" * 60
    results = []
    try:
        for i, paper in enumerate(client.results(search), 1):
            categories = ", ".join(paper.categories[:5])
            results.append(
                f"{divider}\n"
                f"[{i}] {paper.title}\n"
                f"    📅 {paper.published.strftime('%Y-%m-%d')}  |  🏷  {categories}\n"
                f"    🔗 {paper.pdf_url}\n"
                f"{divider}\n"
                f"{paper.summary[:500]}...\n"
            )
        if not results:
            return f"No papers found on arXiv for query: {query}"
        return f"arXiv Search Results for: \"{query}\"\n\n" + "\n".join(results)
    except Exception as e:
        return f"Error searching arXiv: {str(e)}"

@tool
def download_and_parse_arxiv_paper(query: str) -> str:
    """
    Useful for DOWNLOADING and DEEP READING a single, specific paper.
    Input should be an exact title or ArXiv ID.
    Use this when the user asks for a summary, metrics, or comparisons of a specific paper.
    """
    print(f"🤖 Agent called download_and_parse_arxiv_paper with query: {query}")

    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=1, sort_by=arxiv.SortCriterion.Relevance)
    
    try:
        paper = next(client.results(search))
    except StopIteration:
        return f"No paper found on Arxiv for query: {query}"
    
    # Pass the heavy lifting to the shared utility
    return download_and_parse_pdf(
        pdf_url=paper.pdf_url,
        title=paper.title,
        source_id=paper.get_short_id(),
        date_published=paper.published.strftime("%Y-%m-%d"),
        categories=paper.categories
    )