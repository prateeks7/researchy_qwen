import requests
from langchain_core.tools import tool

_MAX_QUERY_LEN = 200

def _clean_query(query: str) -> str:
    q = query.strip().split("\n")[0].strip()
    return q[:_MAX_QUERY_LEN]

@tool
def search_semantic_scholar(query: str) -> str:
    """
    Searches Semantic Scholar for papers by topic. Returns metadata (title, abstract, IDs, PDF URL).
    Use this for discovery. To get full text of a specific paper, call download_and_parse_semantic_scholar_paper afterwards.
    Input should be a search topic (e.g., 'Physical AI humanoid' or 'water quality datasets').
    """
    query = _clean_query(query)
    print(f"🤖 Agent called search_semantic_scholar with query: {query}")

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": 5,
        "fields": "title,authors,abstract,url,year,externalIds,openAccessPdf"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data or not data["data"]:
            return "No papers found for this topic on Semantic Scholar."

        divider = "─" * 60
        results = []
        for i, item in enumerate(data["data"], 1):
            paper_id = item.get("paperId", "Unknown ID")
            title = item.get("title", "No Title")
            year = str(item.get("year", "N/A"))

            pdf_url = None
            if item.get("openAccessPdf") and item["openAccessPdf"].get("url"):
                pdf_url = item["openAccessPdf"]["url"]
            elif item.get("externalIds") and item["externalIds"].get("ArXiv"):
                arxiv_id = item["externalIds"]["ArXiv"]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            pdf_note = f"📄 PDF: {pdf_url}" if pdf_url else "⬜ No open-access PDF available."

            abstract = (item.get("abstract") or "No abstract available.")[:500]
            results.append(
                f"{divider}\n"
                f"[{i}] {title}\n"
                f"    📅 {year}  |  🔑 ID: {paper_id}\n"
                f"    🔗 {item.get('url', 'No URL')}\n"
                f"    {pdf_note}\n"
                f"{divider}\n"
                f"{abstract}...\n"
            )
        return f"Semantic Scholar Results for: \"{query}\"\n\n" + "\n".join(results)
    except Exception as e:
        return f"Error fetching from Semantic Scholar: {str(e)}"

@tool
def get_paper_citations(paper_id: str) -> str:
    """
    Useful for finding all papers citing a specific paper.
    Input should be a Semantic Scholar Paper ID.
    """
    print(f"🤖 Agent called get_paper_citations for: {paper_id}")
    formatted_id = f"ARXIV:{paper_id}" if "arxiv" not in paper_id.lower() and len(paper_id) < 20 else paper_id
    url = f"https://api.semanticscholar.org/graph/v1/paper/{formatted_id}/citations"
    
    params = {"limit": 5, "fields": "title,authors,year,paperId"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return "Could not fetch citations. Check if the paper ID is correct."
            
        data = response.json()
        if "data" not in data or not data["data"]:
            return "No citations found for this paper."
            
        results = [f"- {item['citingPaper'].get('title')} ({item['citingPaper'].get('year')}) | ID: {item['citingPaper'].get('paperId')}" for item in data["data"]]
        return "Papers citing this work:\n" + "\n".join(results)
    except Exception as e:
        return f"Error fetching citations: {str(e)}"

@tool
def get_author_papers(author_name: str) -> str:
    """
    Useful for finding other papers written by a specific author.
    Input should be the exact name of the author.
    """
    print(f"🤖 Agent called get_author_papers for: {author_name}")
    url = "https://api.semanticscholar.org/graph/v1/author/search"
    params = {"query": author_name, "limit": 1, "fields": "name,papers.title,papers.year,papers.paperId"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if "data" not in data or not data["data"]:
            return "Author not found."
            
        author_data = data["data"][0]
        papers = author_data.get("papers", [])[:5]
        
        results = [f"- {p.get('title')} ({p.get('year')}) | ID: {p.get('paperId')}" for p in papers]
        return f"Other papers by {author_data['name']}:\n" + "\n".join(results)
    except Exception as e:
        return f"Error fetching author data: {str(e)}"

@tool
def download_and_parse_semantic_scholar_paper(paper_id: str) -> str:
    """
    Useful for DOWNLOADING and DEEP READING a specific paper found via Semantic Scholar.
    Input should be the exact Semantic Scholar Paper ID.
    """
    print(f"🤖 Agent called download_and_parse_semantic_scholar_paper for ID: {paper_id}")
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    params = {"fields": "title,openAccessPdf,externalIds,year"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pdf_url = None
        
        if data.get("openAccessPdf") and data["openAccessPdf"].get("url"):
            pdf_url = data["openAccessPdf"]["url"]
            
        elif data.get("externalIds") and data["externalIds"].get("ArXiv"):
            arxiv_id = data["externalIds"]["ArXiv"]
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
        if not pdf_url:
            return "❌ No direct open-access PDF link found for this paper. Try searching Web instead."
            
        title = data.get("title", "Unknown Title")
        year = str(data.get("year", ""))
        
        # Pass the extracted URL and metadata to the shared utility
        return download_and_parse_pdf(
            pdf_url=pdf_url,
            title=title,
            source_id=paper_id,
            date_published=f"{year}-01-01" if year else None
        )
    except Exception as e:
        return f"Error fetching paper details from Semantic Scholar: {str(e)}"