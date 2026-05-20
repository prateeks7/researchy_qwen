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
from src.tools.query_classifier import classify_query
from src.tools.approach_generator import generate_approach
from src.tools.synthesize_tool import synthesize_findings
from src.tools.query_validator import validate_query

_TOOLS = [
    # Security (STEP -1: runs before everything)
    validate_query,  # Check query is research-related and safe

    # Routing & strategy (STEP 0)
    classify_query,  # Intent detection — run after validation
    generate_approach,  # Custom strategy for unknown intents

    # Search tools
    search_arxiv_papers,
    search_semantic_scholar,
    search_pubmed,

    # Download & parse
    download_and_parse_arxiv_paper,
    download_and_parse_semantic_scholar_paper,
    download_pubmed_paper,

    # Specialized lookups
    get_paper_citations,
    get_author_papers,

    # Local knowledge base
    search_internal_knowledge,
    search_paper_details,

    # Synthesis & comparison
    synthesize_findings,  # Convert search results to actionable answer
    compare_papers,  # Section-by-section compare via ChromaDB, always 72B

    # Fallback
    web_search_tool,
]


def get_research_agent(model: str = "72b", hf_token: str | None = None, gemini_token: str | None = None) -> AgentExecutor:
    """
    model: "72b" | "7b" | "gemini-flash" | "local72b"

    Uses function-calling agent (create_tool_calling_agent) instead of ReAct:
    - LLM emits structured tool-call JSON — no text parsing, no stop sequences
    - Cannot hallucinate Observation blocks
    - More reliable tool selection, fewer wasted iterations
    """
    llm = get_llm(model, hf_token=hf_token, gemini_token=gemini_token)
    prompt = build_prompt()
    agent = create_tool_calling_agent(llm, _TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=_TOOLS,
        verbose=True,
        max_iterations=12,
    )
