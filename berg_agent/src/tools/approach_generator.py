"""
Approach generator — for novel/hybrid/unknown queries, LLM suggests the strategy.

When a query doesn't fit predefined workflows, this tool generates a step-by-step
approach that the agent should follow.
"""

from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.llm_setup import get_llm

_APPROACH_PROMPT = PromptTemplate.from_template("""You are a research strategy advisor. The user asked something that doesn't fit standard workflows.

User Query: {query}

TASK: Suggest the APPROACH the agent should take. Be specific about:
1. Which tools to use (search_arxiv_papers, download, compare_papers, synthesize_findings, etc.)
2. In what order
3. Any special handling needed
4. Whether final answer should be synthesized/extracted

Use this template:

APPROACH:
Step 1: [Tool] — [reason]
Step 2: [Tool] — [reason]
Step 3: [Tool] — [reason]
Step 4: [Final action — synthesize/list/compare]

Available tools:
- search_arxiv_papers: Find papers on a topic
- search_semantic_scholar: Academic search
- search_pubmed: Biomedical papers
- download_and_parse_arxiv_paper: Get full paper content
- get_paper_citations: Find papers citing a paper
- get_author_papers: Find papers by an author
- synthesize_findings: Turn search results into actionable answer
- compare_papers: Compare 2+ papers
- web_search_tool: Search the web for recent/non-academic info
- search_internal_knowledge: Search local knowledge base

Be concise. Generate ONLY the APPROACH, no preamble.""")

@tool
def generate_approach(query: str) -> str:
    """
    For novel/hybrid/unknown queries: LLM generates suggested workflow.

    Returns a step-by-step strategy the agent should follow.
    """
    print(f"🔄 Generating custom approach for: {query[:80]}...")
    llm = get_llm("72b")  # Full model for reasoning
    chain = _APPROACH_PROMPT | llm | StrOutputParser()
    try:
        approach = chain.invoke({"query": query})
        print(f"   → Custom approach generated")
        return approach
    except Exception as e:
        print(f"   → Approach generation failed: {e}")
        return (
            "APPROACH:\n"
            "Step 1: search_arxiv_papers — Initial search on topic\n"
            "Step 2: download_and_parse_arxiv_paper — Get paper details\n"
            "Step 3: synthesize_findings — Extract actionable insights\n"
        )
