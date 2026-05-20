from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

ddg_search = DuckDuckGoSearchRun()

@tool
def web_search_tool(query: str) -> str:
    """
    LAST RESORT ONLY. Use this ONLY when ALL of the following are true:
    1. search_arxiv_papers returned no relevant results, AND
    2. search_semantic_scholar returned no relevant results, AND
    3. search_pubmed returned no relevant results (if domain-appropriate).
    Do NOT call this if any academic source already returned relevant papers.
    Web results are unstructured webpage snippets — they cannot be cited as papers
    and should only be used to find leads when academic databases are exhausted.
    Input should be a specific search query.
    """
    print(f"🤖 Agent called web_search_tool with query: {query}")
    try:
        return ddg_search.run(query)
    except Exception as e:
        return f"Error performing web search: {str(e)}"