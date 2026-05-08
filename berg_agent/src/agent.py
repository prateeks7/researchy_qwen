from langchain_classic.agents import create_tool_calling_agent, AgentExecutor

from src.tools.llm_setup import get_llm
from src.prompt.builder import build_prompt

from src.tools.arxiv_api import search_arxiv_papers, download_and_parse_arxiv_paper
from src.tools.academic_api import (
    search_semantic_scholar, get_paper_citations,
    get_author_papers, download_and_parse_semantic_scholar_paper,
)
from src.tools.pubmed_api import search_pubmed, download_pubmed_paper
from src.tools.web_search import web_search_tool
from src.tools.rag_tool import search_internal_knowledge, search_paper_details
from src.tools.compare_tool import compare_papers

_TOOLS = [
    search_arxiv_papers,
    download_and_parse_arxiv_paper,
    search_semantic_scholar,
    get_paper_citations,
    get_author_papers,
    download_and_parse_semantic_scholar_paper,
    search_pubmed,
    download_pubmed_paper,
    web_search_tool,
    search_internal_knowledge,
    search_paper_details,
    compare_papers,  # section-by-section compare via ChromaDB, always 72B
]


def get_research_agent(model: str = "72b") -> AgentExecutor:
    """
    model: "72b" | "7b" | "gemini-flash"

    Uses function-calling agent (create_tool_calling_agent) instead of ReAct:
    - LLM emits structured tool-call JSON — no text parsing, no stop sequences
    - Cannot hallucinate Observation blocks
    - More reliable tool selection, fewer wasted iterations
    """
    llm = get_llm(model)
    prompt = build_prompt()
    agent = create_tool_calling_agent(llm, _TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=_TOOLS,
        verbose=True,
        max_iterations=8,
    )
