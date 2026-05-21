"""
Synthesize findings — converts search results into actionable, direct answers.

Used when user asks "What X can I use for Y?" to extract specific models/datasets/
methods from papers and synthesize them into a list with context.
"""

from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.llm_setup import get_llm

_SYNTHESIZE_PROMPT = PromptTemplate.from_template("""You are an expert research synthesizer. You have retrieved papers on a topic and must synthesize them into a direct, actionable answer.

ORIGINAL QUESTION: {original_question}

RETRIEVED PAPERS/CONTEXT:
{papers_context}

TASK: Extract the answer and synthesize into a numbered list with context.

Guidelines:
- DO NOT just list papers or titles
- DO extract specific items (models, datasets, methods, metrics) mentioned in papers
- DO explain what each item is and why it's relevant
- DO cite which paper each item came from
- DO group by category if applicable
- Keep each item brief (1-2 sentences)

Format:
Based on [N] papers I reviewed, here are [items] you can use:

1. **[Item Name]** — [brief explanation]. (From: Paper Title, Year)
2. **[Item Name]** — [brief explanation]. (From: Paper Title, Year)
...

SYNTHESIZED ANSWER:"""
)

@tool
def synthesize_findings(
    original_question: str,
    papers_context: str,
) -> str:
    """
    Synthesize search results into a direct answer.

    Call this AFTER searching papers but BEFORE returning to user,
    when user asked "What X can I use for Y?" to convert paper results
    into actionable recommendations.

    Args:
        original_question: The user's original question
        papers_context: Paper titles, abstracts, or search results (context from tool observations)

    Returns:
        Synthesized answer with specific items extracted from papers
    """
    from src.tools.model_context import get_model
    print(f"🧩 Synthesizing findings for: {original_question[:80]}...")
    llm = get_llm(get_model() or "72b")
    chain = _SYNTHESIZE_PROMPT | llm | StrOutputParser()
    try:
        synthesis = chain.invoke({
            "original_question": original_question,
            "papers_context": papers_context[:4000],  # Cap context to avoid token overflow
        })
        print(f"   → Synthesis complete")
        return synthesis
    except Exception as e:
        print(f"   → Synthesis failed: {e}")
        return f"Could not synthesize findings. Raw context:\n{papers_context[:2000]}"
