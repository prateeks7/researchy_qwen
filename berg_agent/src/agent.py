from langchain_classic.agents import AgentExecutor, create_react_agent
from src.tools.llm_setup import get_llm
from src.prompt.builder import build_prompt

from src.tools.arxiv_api import search_arxiv_papers, download_and_parse_arxiv_paper
from src.tools.academic_api import search_semantic_scholar, get_paper_citations, get_author_papers, download_and_parse_semantic_scholar_paper
from src.tools.pubmed_api import search_pubmed, download_pubmed_paper
from src.tools.web_search import web_search_tool
from src.tools.rag_tool import search_internal_knowledge, search_paper_details

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
]


def get_research_agent(model: str = "72b") -> AgentExecutor:
    """
    model: "72b" | "7b" | "gemini-flash"
    """
    llm = get_llm(model)
    prompt = build_prompt()
    agent = create_react_agent(llm, _TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=_TOOLS,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=12,
    )
