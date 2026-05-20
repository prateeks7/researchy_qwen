import os
import json
import logging
import threading
import requests
import pymupdf as fitz
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.llm_setup import get_llm
from src.tools.model_context import get_model
from src.db.mongo_client import insert_paper, get_paper_by_link

logger = logging.getLogger(__name__)
os.makedirs("papers", exist_ok=True)

# Per-URL locks — threads downloading the same paper block each other,
# threads downloading different papers run freely in parallel.
_url_locks: dict[str, threading.Lock] = {}
_url_locks_guard = threading.Lock()

def _url_lock(url: str) -> threading.Lock:
    with _url_locks_guard:
        if url not in _url_locks:
            _url_locks[url] = threading.Lock()
        return _url_locks[url]

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

_SUMMARIZE_PROMPT = PromptTemplate.from_template(
    """You are a research assistant. Below are sections extracted from an academic paper.

For each section that has content, write a 2-4 sentence summary capturing the key methods,
findings, or contributions. Also produce 5-10 keywords describing the paper's topics.

Output ONE valid JSON object with:
- "summaries": object with same section keys, each value a 2-4 sentence summary
- "keywords": JSON array of 5-10 keyword strings

Section keys: abstract, introduction, related_work, methodology, datasets, metrics,
results_and_evaluations, conclusion, limitations

Rules:
- Output ONLY the JSON. No markdown, no explanation.
- If a section has no content, set its summary to "Content not explicitly found."

SECTIONS:
{sections_text}

JSON OUTPUT:"""
)

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

    Uses the active model for the whole parse so tool work stays consistent with
    the selected chat pipeline.
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

    if not parsed_chunks:
        logger.error("PDF parse failed with %s — storing raw text abstract only.", primary_model)
        print("⚠️ Parse failed with selected model — using raw text fallback.")
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


def _llm_summarize_sections(sections: dict) -> tuple[dict, list]:
    """
    Takes already-detected sections dict, calls LLM once to summarize each section
    and extract keywords. Returns (summaries_dict, keywords_list).
    """
    model = get_model()
    llm = get_llm(model)
    chain = _SUMMARIZE_PROMPT | llm | StrOutputParser()

    # Build compact sections text (cap each section at 2000 chars to fit context)
    sections_text = "\n\n".join(
        f"[{k.upper()}]\n{v[:2000]}"
        for k, v in sections.items()
        if v not in _SKIP_VALUES
    )

    print(f"🧠 Summarizing sections with model: {model}")
    try:
        response = chain.invoke({"sections_text": sections_text})
        data = _parse_llm_json(response)
        summaries = data.get("summaries", {})
        keywords = data.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        # Fill missing section keys with fallback
        for k in SECTION_KEYS:
            if k not in summaries or not summaries[k] or summaries[k] in _SKIP_VALUES:
                summaries[k] = sections.get(k, "Content not explicitly found.")[:300]
        print(f"   ✅ Summaries generated, {len(keywords)} keywords")
        return summaries, keywords
    except Exception as e:
        logger.warning("LLM summarization failed: %s", e)
        print(f"   ⚠️ Summarization failed, using section text fallback")
        summaries = {k: (v[:300] if v not in _SKIP_VALUES else v) for k, v in sections.items()}
        return summaries, []


def _scrape_text(pdf_url: str, source_id: str):
    """Try HTML scraping based on URL. Returns text or None."""
    from src.tools.utils.html_scraper import scrape_arxiv_html, scrape_pubmed_html
    import re as _re
    if "arxiv.org" in pdf_url:
        # Extract arXiv ID from the URL (e.g. arxiv.org/pdf/1706.03762 or abs/1706.03762v1)
        m = _re.search(r'arxiv\.org/(?:pdf|abs)/([0-9]{4}\.[0-9]+)', pdf_url)
        arxiv_id = m.group(1) if m else source_id.split("v")[0]
        return scrape_arxiv_html(arxiv_id)
    if "ncbi.nlm.nih.gov/pmc" in pdf_url:
        m = _re.search(r'PMC(\d+)', pdf_url)
        if m:
            return scrape_pubmed_html(m.group(1))
    return None


def _download_pdf_text(pdf_url: str, source_id: str):
    """Download PDF and extract raw text. Returns (text, pdf_path)."""
    pdf_path = f"papers/{source_id}.pdf"
    try:
        response = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(response.content)
    except Exception as e:
        print(f"   ❌ PDF download failed: {e}")
        return None, None
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
        return text, pdf_path
    except Exception as e:
        print(f"   ❌ PDF text extraction failed: {e}")
        return None, pdf_path


def download_and_parse_pdf(
    pdf_url: str,
    title: str,
    source_id: str,
    date_published: str = None,
    categories: list = None,
) -> str:
    from src.tools.utils.section_detector import detect_sections, clean_section_text

    # 1. Fast cache check before acquiring any lock
    cached = get_paper_by_link(pdf_url)
    if cached:
        print(f"✅ Already indexed — loading from database: {cached['title']}")
        return _format_cached_paper(cached)

    # Per-URL lock — only threads fetching the same paper block each other
    with _url_lock(pdf_url):
        # Re-check inside lock — another thread may have finished while we waited
        cached = get_paper_by_link(pdf_url)
        if cached:
            print(f"✅ Already indexed (race-free) — loading from database: {cached['title']}")
            return _format_cached_paper(cached)

        print(f"📥 Not in database — processing new paper: {title}")

        # 2. Try HTML scraping first (~500ms, no download)
        raw_text = _scrape_text(pdf_url, source_id)

        # 3. Fallback: download PDF and extract text (~2s)
        pdf_path = None
        if not raw_text:
            print(f"   ⚠️ Scraping failed — falling back to PDF download")
            raw_text, pdf_path = _download_pdf_text(pdf_url, source_id)

        if not raw_text:
            return f"❌ Failed to retrieve paper: {title}"

        # 4. Section detection — pure regex, no LLM
        sections = detect_sections(raw_text)
        sections = {k: clean_section_text(v) for k, v in sections.items()}

    # 5. LLM summarization is outside the lock — doesn't block other papers
    summaries, llm_keywords = _llm_summarize_sections(sections)

    # 6. Keywords from LLM + categories
    all_keywords = list(set(llm_keywords + (categories or []))) or ["General Research"]

    # 7. Save to MongoDB
    pub_date = date_published or datetime.now().strftime("%Y-%m-%d")
    insert_paper({
        "link": pdf_url,
        "title": title,
        "date_published": pub_date,
        "text_content": sections,
        "section_summaries": summaries,
        "keywords": all_keywords,
    })

    # 8. Cleanup PDF if downloaded
    if pdf_path and os.path.exists(pdf_path):
        os.remove(pdf_path)

    _LABELS = {
        "abstract": "ABSTRACT", "introduction": "INTRODUCTION",
        "related_work": "RELATED WORK", "methodology": "METHODOLOGY",
        "datasets": "DATASETS", "metrics": "EVALUATION METRICS",
        "results_and_evaluations": "RESULTS & EVALUATIONS",
        "conclusion": "CONCLUSION", "limitations": "LIMITATIONS",
    }
    lines = [
        "✅ Paper processed and indexed.", "",
        f"TITLE: {title}", f"PUBLISHED: {pub_date}",
        f"KEYWORDS: {', '.join(all_keywords)}", f"SOURCE: {pdf_url}", "",
        "(Section previews shown — call search_paper_details for full text)", "",
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
        "🌍 Loaded from database (already indexed).", "",
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
