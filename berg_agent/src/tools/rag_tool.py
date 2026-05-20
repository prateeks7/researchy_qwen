from langchain_core.tools import tool
from src.db.vector_store import search_vector_db, search_vector_db_raw

@tool
def search_internal_knowledge(query: str) -> str:
    """
    Searches your internal knowledge base using keyword relevance and section SUMMARIES.
    Use ONLY for explanation, factual, or comparison intents where you need details
    about a paper already discussed in this session. Do NOT call this for discovery
    queries (finding new papers) — go directly to search_arxiv_papers instead.
    Input: a specific question (e.g. 'What datasets were used in Paper X?').
    """
    print(f"🧠 Agent is searching internal knowledge (summaries) for: {query}")
    return search_vector_db(query, k=5)

@tool
def search_paper_details(query: str) -> str:
    """
    Deep search over the RAW full-text content of downloaded papers.
    Use this ONLY when search_internal_knowledge summaries are insufficient
    and you need precise numbers, exact quotes, or granular technical details.
    Input: a specific targeted question (e.g. 'Exact F1 score on CoNLL dataset in Paper X').
    """
    print(f"🔬 Agent is deep-searching raw paper content for: {query}")
    return search_vector_db_raw(query, k=3)