"""
compare_papers.py — Section-by-section paper comparison tool.

Strategy:
  1. For each comparison dimension (methodology, results, datasets, …) query
     ChromaDB for *only the relevant sections* of the requested papers.
  2. Issue one focused 72B LLM call per dimension — each call stays well
     under the model context budget.
  3. Stitch partial comparisons into a final structured answer and return it.

Uses the same model as the outer agent so each pipeline stays consistent.
"""

import logging
from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.db.vector_store import get_vector_store, _format_results
from src.tools.llm_setup import get_llm
from src.tools.model_context import get_model

logger = logging.getLogger(__name__)

MAX_COMPARE_PAPERS = 5

# ── Constants ──────────────────────────────────────────────────────────────────

# Comparison dimensions and the ChromaDB section names they map to.
# Each dimension drives one targeted retrieval + one LLM sub-call.
_DIMENSIONS: list[tuple[str, list[str]]] = [
    ("Problem & Motivation",   ["abstract", "introduction"]),
    ("Methodology & Design",   ["methodology", "related_work"]),
    ("Datasets & Metrics",     ["datasets", "metrics"]),
    ("Results & Evaluations",  ["results_and_evaluations"]),
    ("Limitations & Outlook",  ["limitations", "conclusion"]),
]

# Approximate token budget per dimension call.
# 32K window − ~2K system prompt − ~1K question overhead = ~29K usable.
# We keep each sub-call well under that so history can accumulate safely.
_MAX_CONTEXT_CHARS_PER_DIMENSION = 12_000  # ≈ 3K tokens, comfortable margin

_DIMENSION_PROMPT = PromptTemplate.from_template(
    """You are Berg, an expert academic paper analyst. Compare the following papers
on ONE specific dimension only: **{dimension}**.

RETRIEVED CONTEXT (from the papers' relevant sections):
{context}

INSTRUCTIONS:
- Focus exclusively on {dimension}.
- Use a Markdown table for any quantitative differences.
- Be factual — only use information from the context above.
- If a paper has no relevant information for this dimension, explicitly state that.
- Keep your answer under 400 words.

QUESTION: {question}

COMPARISON ({dimension}):"""
)

_SYNTHESIS_PROMPT = PromptTemplate.from_template(
    """You are Berg. You have just completed a section-by-section comparison of
academic papers. Below are the partial comparisons, one per dimension.

PARTIAL COMPARISONS:
{partial_comparisons}

ORIGINAL USER QUESTION: {question}

Write a cohesive final comparison report. Use:
- A brief intro paragraph naming the papers
- One ### heading per dimension with the partial result
- A final "## Overall Assessment" paragraph
- A Markdown table summarising key differences across all dimensions

[FOLLOW_UP] Would you like me to dive deeper into any specific dimension, or find papers that cite both of these?"""
)


# ── Helper: targeted ChromaDB retrieval ───────────────────────────────────────

def _retrieve_for_papers_and_sections(
    paper_titles: list[str],
    sections: list[str],
    query: str,
    k_per_paper: int = 2,
) -> str:
    """
    Query ChromaDB for specific sections of specific papers.

    For each (paper_title, section) pair, retrieve the top-k matching chunks.
    Returns a formatted context string capped at _MAX_CONTEXT_CHARS_PER_DIMENSION.
    """
    vector_store = get_vector_store()
    all_results = []

    for title in paper_titles:
        for section in sections:
            # Targeted semantic search — combine query with section name
            targeted_query = f"{query} {section.replace('_', ' ')}"
            try:
                results = vector_store.similarity_search(
                    targeted_query,
                    k=k_per_paper,
                    filter={
                        "$and": [
                            {"title": {"$eq": title}},
                            {"section": {"$eq": section}},
                        ]
                    },
                )
                all_results.extend(results)
            except Exception:
                # Chroma filter syntax may vary — fallback to unfiltered search
                results = vector_store.similarity_search(
                    f"{title} {targeted_query}",
                    k=k_per_paper,
                )
                # Post-filter: keep only docs where title contains any word from the paper title
                title_words = set(title.lower().split())
                filtered = [
                    r for r in results
                    if title_words & set(r.metadata.get("title", "").lower().split())
                ]
                all_results.extend(filtered)

    if not all_results:
        return "No relevant sections found in the local knowledge base for this dimension."

    context = _format_results(all_results)
    # Hard cap to keep the dimension call under budget
    return context[:_MAX_CONTEXT_CHARS_PER_DIMENSION]


# ── Main tool ──────────────────────────────────────────────────────────────────

@tool
def compare_papers(query: str) -> str:
    """
    Compare two or more academic papers that are already in the local knowledge base.

    Input format:
        "<free-form question> | papers: Paper Title A, Paper Title B"

    Example:
        "Compare the training methods and results | papers: Attention Is All You Need, BERT: Pre-training of Deep Bidirectional Transformers"

    This tool:
    - Uses targeted ChromaDB retrieval per comparison dimension (not full text)
    - Runs one focused LLM call per dimension to stay under the 32K context window
    - Uses the same model as the outer agent for consistency
    - Returns a structured multi-section comparison report

    Use this instead of downloading both papers and comparing manually.
    Papers MUST have been previously downloaded (use download_and_parse_arxiv_paper first if needed).
    """
    print(f"🔬 compare_papers called: {query[:120]}")

    # ── Parse input ────────────────────────────────────────────────────────────
    if "| papers:" in query:
        question_part, papers_part = query.split("| papers:", 1)
        question = question_part.strip()
        paper_titles = [t.strip() for t in papers_part.split(",") if t.strip()]
    else:
        # Fallback: treat the whole query as the question, no titles extracted
        question = query.strip()
        paper_titles = []

    if len(paper_titles) < 2:
        return (
            "compare_papers requires at least 2 paper titles after '| papers:'.\n"
            "Example: 'Compare training methods | papers: Paper A, Paper B'\n"
            "Make sure both papers are already downloaded before calling this tool."
        )

    if len(paper_titles) > MAX_COMPARE_PAPERS:
        return (
            f"compare_papers can handle up to {MAX_COMPARE_PAPERS} papers in one request. "
            f"You provided {len(paper_titles)}. Please split this into smaller batches."
        )

    logger.info("Comparing papers: %s", paper_titles)
    logger.info("Question: %s", question)

    # Keep tool-internal comparison calls on the same model as the outer agent.
    llm = get_llm(get_model())
    dim_chain    = _DIMENSION_PROMPT    | llm | StrOutputParser()
    synth_chain  = _SYNTHESIS_PROMPT    | llm | StrOutputParser()

    # ── Section-by-section comparison ─────────────────────────────────────────
    partial_comparisons: list[str] = []
    papers_label = " vs. ".join(paper_titles)

    for dim_name, sections in _DIMENSIONS:
        print(f"  📐 Comparing dimension: {dim_name}")

        context = _retrieve_for_papers_and_sections(
            paper_titles=paper_titles,
            sections=sections,
            query=question,
        )

        try:
            dim_result = dim_chain.invoke({
                "dimension": dim_name,
                "context": context,
                "question": f"{question} (Papers: {papers_label})",
            })
            partial_comparisons.append(f"### {dim_name}\n\n{dim_result.strip()}")
        except Exception as e:
            logger.warning("Dimension call failed for %s: %s", dim_name, e)
            partial_comparisons.append(
                f"### {dim_name}\n\n⚠️ Could not complete this dimension: {e}"
            )

    # ── Final synthesis ────────────────────────────────────────────────────────
    print("  🧩 Synthesising final report …")
    partial_text = "\n\n---\n\n".join(partial_comparisons)

    try:
        final_report = synth_chain.invoke({
            "partial_comparisons": partial_text[:20_000],  # keep synthesis call safe
            "question": question,
        })
    except Exception as e:
        # Synthesis failed — return the partial comparisons directly
        logger.error("Synthesis call failed: %s", e)
        final_report = (
            f"## Comparison: {papers_label}\n\n"
            + partial_text
            + "\n\n[FOLLOW_UP] Would you like me to dive deeper into any specific dimension?"
        )

    return final_report
