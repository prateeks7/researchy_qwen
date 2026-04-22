from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

ddg_search = DuckDuckGoSearchRun()

@tool
def web_search_tool(query: str) -> str:
    """
    Useful for searching the live web for recent research news, documentation, or datasets.
    Input should be a specific search query.
    """
    print(f"🤖 Agent called web_search_tool with query: {query}")
    try:
        return ddg_search.run(query)
    except Exception as e:
        return f"Error performing web search: {str(e)}"