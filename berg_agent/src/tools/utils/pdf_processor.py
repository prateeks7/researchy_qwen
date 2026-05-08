import os
import json
import logging
import requests
import fitz
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.llm_setup import get_llm
from src.tools.model_context import get_model
from src.db.mongo_client import insert_paper, get_paper_by_link

logger = logging.getLogger(__name__)
os.makedirs("papers", exist_ok=True)

SECTION_KEYS = [
    "abstract", "introduction", "related_work", "methodology",
    "datasets", "metrics", "results_and_evaluations", "conclusion", "limitations",
]

_SKIP_VALUES = {"Content not explicitly found.", "Failed to parse", "No content to summarize."}

# ── Context window constants ───────────────────────────────────────────────────
# Qwen 72B: 32K token window. 1 token ≈ 4 chars.
# We parse at most 30K chars per LLM call; longer papers are chunked.
_PARSE_CHUNK_SIZE = 30_000   # chars per chunk sent to the parse LLM
_PARSE_OVERLAP    =  1_000   # char overlap between chunks to avoid section splits

_PARSE_PROMPT = PromptTemplate.from_template(
    """You are a strict data extraction agent. Read the following raw text from an academic research paper.

Your task is to produce ONE valid JSON object with these exact keys:
- Section keys (extract and clean the text for each):
  "abstract", "introduction", "related_work", "methodology", "datasets",
  "metrics", "results_and_evaluations", "conclusion", "limitations"
- "keywords": a JSON array of 5-10 strings describing topics, methods, and contributions
- "summaries": a nested object with the same section keys, each value being a 2-4 sentence
  summary capturing the key methods, findings, or contributions of that section

Rules:
- Output ONLY the JSON object. No markdown, no explanation, no extra text.
- If a section is not present in the paper, set its value to "Content not explicitly found."
- Keep section text concise — truncate to 2000 characters if very long.

RAW TEXT (first 30000 chars):
{text}

JSON OUTPUT:"""
)


def _parse_llm_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _merge_parsed_chunks(chunks: list[dict]) -> dict:
    """
    Merge section data from multiple parse chunks.
    First non-skip value for each key wins; keywords are union-ed.
    """
    merged: dict = {k: "Content not explicitly found." for k in SECTION_KEYS}
    merged["summaries"] = {k: "" for k in SECTION_KEYS}
    merged["keywords"] = []

    for chunk in chunks:
        for key in SECTION_KEYS:
            val = chunk.get(key, "")
            if val and val not in _SKIP_VALUES and merged[key] in ("Content not explicitly found.", ""):
                merged[key] = val
        for key in SECTION_KEYS:
            sum_val = chunk.get("summaries", {}).get(key, "")
            if sum_val and sum_val not in _SKIP_VALUES and not merged["summaries"].get(key):
                merged["summaries"][key] = sum_val
        kw = chunk.get("keywords", [])
        if isinstance(kw, list):
            merged["keywords"] = list(set(merged["keywords"]) | set(kw))

    return merged


def _parse_chunks_with_model(model: str, chunks_text: list[str]) -> list[dict]:
    """Try to parse each chunk with the given model. Returns successfully parsed chunks."""
    llm = get_llm(model)
    chain = _PARSE_PROMPT | llm | StrOutputParser()
    parsed: list[dict] = []
    for i, chunk in enumerate(chunks_text, 1):
        try:
            response = chain.invoke({"text": chunk})
            data = _parse_llm_json(response)
            parsed.append(data)
            print(f"   ✅ Chunk {i}/{len(chunks_text)} parsed ({model}).")
        except Exception as e:
            logger.warning("Chunk %d/%d failed with %s: %s", i, len(chunks_text), model, e)
            print(f"   ⚠️ Chunk {i}/{len(chunks_text)} failed ({model}): {e}")
    return parsed


def llm_parse_and_summarize_pdf(raw_text: str) -> tuple[dict, dict, list]:
    """
    Parses a PDF's raw text into structured sections + summaries.

    Context-window-aware:
    - If raw_text <= _PARSE_CHUNK_SIZE chars  → single LLM call (fast path)
    - If raw_text >  _PARSE_CHUNK_SIZE chars  → split into overlapping chunks,
      parse each, then merge results.

    Falls back to gemini-flash if the primary model times out or errors.
    Returns: (sections dict, summaries dict, keywords list)
    """
    primary_model = get_model()

    # ── Build chunks ───────────────────────────────────────────────────────────
    if len(raw_text) <= _PARSE_CHUNK_SIZE:
        chunks_text = [raw_text]
    else:
        chunks_text = []
        start = 0
        while start < len(raw_text):
            end = min(start + _PARSE_CHUNK_SIZE, len(raw_text))
            chunks_text.append(raw_text[start:end])
            start = end - _PARSE_OVERLAP
        logger.info(
            "PDF text (%d chars) split into %d chunks.", len(raw_text), len(chunks_text)
        )

    print(f"🧠 Parsing PDF with model: {primary_model} ({len(chunks_text)} chunk(s))")
    parsed_chunks = _parse_chunks_with_model(primary_model, chunks_text)

    # ── Fallback to gemini-flash if primary produced nothing ───────────────────
    if not parsed_chunks and primary_model != "gemini-flash":
        msg = f"PDF parse: {primary_model} produced no output — falling back to gemini-flash."
        logger.warning(msg)
        print(f"🔄 {msg}")
        try:
            parsed_chunks = _parse_chunks_with_model("gemini-flash", chunks_text)
            if parsed_chunks:
                logger.info("PDF parse: gemini-flash fallback succeeded.")
                print("✅ Gemini-flash fallback succeeded.")
        except Exception as e:
            logger.error("PDF parse: gemini-flash fallback also failed: %s", e)
            print(f"⚠️ Gemini fallback also failed: {e}")

    if not parsed_chunks:
        logger.error("PDF parse: all attempts failed — storing raw text abstract only.")
        print("⚠️ All parse attempts failed — using raw text fallback.")
        fallback_sections = {k: "Failed to parse" for k in SECTION_KEYS}
        fallback_sections["abstract"] = raw_text[:2000]
        fallback_summaries = {k: fallback_sections[k][:300] for k in SECTION_KEYS}
        return fallback_sections, fallback_summaries, []

    # ── Merge all chunk results ────────────────────────────────────────────────
    merged = _merge_parsed_chunks(parsed_chunks)

    sections: dict = {k: merged.get(k, "Content not explicitly found.") for k in SECTION_KEYS}
    raw_summaries: dict = merged.get("summaries", {})
    summaries: dict = {}
    for key in SECTION_KEYS:
        s = raw_summaries.get(key, "")
        summaries[key] = s if s and s not in _SKIP_VALUES else sections[key][:300]

    keywords = merged.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = []

    return sections, summaries, keywords


def download_and_parse_pdf(
    pdf_url: str,
    title: str,
    source_id: str,
    date_published: str = None,
    categories: list = None,
) -> str:
    # 1. Cache check
    cached = get_paper_by_link(pdf_url)
    if cached:
        print(f"⚡ CACHE HIT: {cached['title']}")
        return _format_cached_paper(cached)

    print(f"📥 CACHE MISS: Downloading PDF from {pdf_url}")

    # 2. Download
    pdf_path = f"papers/{source_id}.pdf"
    try:
        response = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(response.content)
    except Exception as e:
        return f"❌ Failed to download PDF: {e}"

    # 3. Extract text
    try:
        doc = fitz.open(pdf_path)
        raw_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
    except Exception as e:
        return f"❌ Failed to read PDF: {e}"

    # 4. Single LLM call — parse + summarize
    sections, summaries, llm_keywords = llm_parse_and_summarize_pdf(raw_text)

    # 5. Merge keywords
    all_keywords = list(set(llm_keywords + (categories or []))) or ["General Research"]

    # 6. Save to MongoDB
    pub_date = date_published or datetime.now().strftime("%Y-%m-%d")
    insert_paper({
        "link": pdf_url,
        "title": title,
        "date_published": pub_date,
        "text_content": sections,
        "section_summaries": summaries,
        "keywords": all_keywords,
    })

    # 7. Cleanup
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    _LABELS = {
        "abstract": "ABSTRACT", "introduction": "INTRODUCTION",
        "related_work": "RELATED WORK", "methodology": "METHODOLOGY",
        "datasets": "DATASETS", "metrics": "EVALUATION METRICS",
        "results_and_evaluations": "RESULTS & EVALUATIONS",
        "conclusion": "CONCLUSION", "limitations": "LIMITATIONS",
    }
    # Return SUMMARIES (not full text) so two-paper compare calls stay
    # comfortably within the 32K context window. The agent can always call
    # search_paper_details for raw section text when it needs more depth.
    lines = [
        "✅ Paper downloaded and indexed successfully.", "",
        f"TITLE: {title}", f"PUBLISHED: {pub_date}",
        f"KEYWORDS: {', '.join(all_keywords)}", f"SOURCE: {pdf_url}", "",
        "(Section summaries shown — call search_paper_details for full text)", "",
    ]
    for key, label in _LABELS.items():
        text = summaries.get(key) or sections.get(key, "")
        if text and text not in _SKIP_VALUES:
            lines += [f"=== {label} ===", text.strip(), ""]
    return "\n".join(lines)


def _format_cached_paper(paper: dict) -> str:
    title = paper.get("title", "Unknown")
    pub_date = paper.get("date_published", "")
    keywords = ", ".join(paper.get("keywords", []))
    sections = paper.get("text_content", {})
    summaries = paper.get("section_summaries", {})
    _LABELS = {
        "abstract": "ABSTRACT", "introduction": "INTRODUCTION",
        "related_work": "RELATED WORK", "methodology": "METHODOLOGY",
        "datasets": "DATASETS", "metrics": "EVALUATION METRICS",
        "results_and_evaluations": "RESULTS & EVALUATIONS",
        "conclusion": "CONCLUSION", "limitations": "LIMITATIONS",
    }
    lines = [
        "⚡ Loaded from cache.", "",
        f"TITLE: {title}", f"PUBLISHED: {pub_date}", f"KEYWORDS: {keywords}", "",
    ]
    for key, label in _LABELS.items():
        text = summaries.get(key) or sections.get(key, "")
        if text and text not in _SKIP_VALUES:
            lines += [f"=== {label} ===", text.strip(), ""]
    return "\n".join(lines)


def process_multiple_pdfs(pdf_list: list[dict]) -> str:
    results = []
    for item in pdf_list:
        res = download_and_parse_pdf(
            pdf_url=item["url"],
            title=item.get("title", "Unknown Title"),
            source_id=item.get("id", "unknown_id"),
        )
        results.append(res)
    return "\n\n---\n\n".join(results)
