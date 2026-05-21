"""
Query classifier — detects intent and routes to appropriate workflow.

Intent categories:
- discovery: Find papers on a topic
- recommendation: What X can I use for Y (models, datasets, metrics, methods)
- explanation: Explain this paper / what are the conclusions
- comparison: Compare two or more papers
- factual: What did this paper use/find (requires extraction from paper)
- extraction: Get tables / figures / sections / equations from a specific paper
- citation_lookup: Find papers that cite this / by this author
- web_search: User explicitly asks to search the web / internet
- hybrid: Multiple intents in one query (e.g., find AND compare)
- unknown: Doesn't fit standard categories
"""

from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from src.tools.llm_setup import get_llm

_CLASSIFIER_PROMPT = PromptTemplate.from_template("""
Classify this user query into ONE of these intent categories:

INTENT CATEGORIES:
- discovery: "Find papers on X", "Show me papers about X", "Papers related to X"
- recommendation: "What X can I use for Y", "Recommend X for Y", "Suggest X for Y"
  where X = models, datasets, metrics, methods, frameworks
- explanation: "Explain this paper", "Summarize this paper", "What are the conclusions"
- comparison: "Compare X and Y", "Which is better", "Difference between X and Y"
- factual: "What datasets did this paper use", "What results did they get", "What methods"
- extraction: "Get tables from paper X", "Show figures in paper X", "Extract section 3",
  "Get equations from", "Show me the results table", "List all tables/figures"
- citation_lookup: "Papers that cite this", "Papers by this author", "Who cited this"
- web_search: Query starts with "Search Web" / "search the web" / "search the internet",
  or explicitly asks to look something up online (e.g. journal reviews, model docs,
  GitHub repos, conference pages)
- hybrid: Multiple intents (e.g., find papers AND compare them AND summarize)
- unknown: Doesn't fit above categories

User Query: {query}

Respond with ONLY the category name, nothing else. One word only.""")

@tool
def classify_query(query: str) -> str:
    """
    Classify user query intent to route to appropriate workflow.

    Returns one of: discovery, recommendation, explanation, comparison, factual,
    extraction, citation_lookup, web_search, hybrid, unknown
    """
    from src.tools.model_context import get_model
    print(f"🏷️ Classifying query: {query[:80]}...")
    active = get_model() or "7b"
    # Use 7b for HF-based models (cheaper/faster); use active model for Gemini/local
    classifier_model = "7b" if active in ("72b", "7b") else active
    llm = get_llm(classifier_model)
    chain = _CLASSIFIER_PROMPT | llm
    try:
        result = chain.invoke({"query": query})
        intent = result.strip().lower()
        print(f"   → Detected intent: {intent}")
        return intent
    except Exception as e:
        print(f"   → Classification failed, defaulting to 'unknown': {e}")
        return "unknown"
