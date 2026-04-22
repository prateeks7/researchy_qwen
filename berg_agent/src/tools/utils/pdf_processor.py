import os
import json
import requests
import fitz
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from src.tools.llm_setup import get_llm
from src.db.mongo_client import insert_paper, get_paper_by_link

os.makedirs("papers", exist_ok=True)

SECTION_KEYS = ["abstract", "introduction", "related_work", "methodology", "datasets", "metrics", "results_and_evaluations", "conclusion", "limitations"]

def llm_parse_pdf(raw_text: str) -> dict:
    """Uses the 7B model to extract and structure PDF text into JSON, including keywords."""
    structuring_llm = get_llm(model_size="7b")

    truncated_text = raw_text[:30000]
    prompt = PromptTemplate.from_template(
        """You are a strict data extraction agent. Read the following raw text from an academic research paper.
        Extract the main sections and summarize them if they are too long.
        Also extract 5-10 keywords describing the paper's topics, methods, and contributions.
        You MUST respond ONLY with a valid JSON object using exactly these keys:
        "abstract", "introduction", "related_work", "methodology", "datasets", "metrics",
        "results_and_evaluations", "conclusion", "limitations", "keywords".
        The "keywords" value must be a JSON array of strings (e.g. ["transformer", "NLP", "BERT"]).
        Do not include any Markdown blocks, introduction, or explanations. Just the JSON.

        RAW TEXT:
        {text}

        JSON OUTPUT:"""
    )

    chain = prompt | structuring_llm

    print("🧠 Structuring Agent (7B) is analyzing the PDF...")
    try:
        response = chain.invoke({"text": truncated_text})
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]

        parsed_json = json.loads(cleaned_response.strip())

        for key in SECTION_KEYS:
            if key not in parsed_json:
                parsed_json[key] = "Content not explicitly found."

        if "keywords" not in parsed_json or not isinstance(parsed_json["keywords"], list):
            parsed_json["keywords"] = []

        return parsed_json

    except json.JSONDecodeError as e:
        print(f"⚠️ LLM failed to return a valid JSON: {e}")
        result = {k: "Failed to parse" for k in SECTION_KEYS}
        result["keywords"] = []
        return result


def generate_section_summaries(parsed_sections: dict) -> dict:
    """Uses 7B model to generate detailed 2-4 sentence summaries for all sections in one LLM call."""
    structuring_llm = get_llm(model_size="7b")

    sections_to_summarize = {
        k: v[:3000] for k, v in parsed_sections.items()
        if v not in ("Content not explicitly found.", "Failed to parse")
    }

    if not sections_to_summarize:
        return {k: "No content to summarize." for k in parsed_sections}

    prompt = PromptTemplate.from_template(
        """You are a research summarization agent. Below are sections from an academic paper.
        Write a detailed 2-4 sentence summary for each section that captures the key methods,
        findings, datasets, metrics, or contributions specific to that section.
        Return ONLY a valid JSON object with the exact same keys as the input. No markdown, no extra text.

        SECTIONS:
        {sections_json}

        SUMMARIES JSON:"""
    )

    chain = prompt | structuring_llm

    print("📝 Generating section summaries...")
    try:
        sections_str = json.dumps(sections_to_summarize, indent=2)
        if len(sections_str) > 20000:
            sections_str = sections_str[:20000]

        response = chain.invoke({"sections_json": sections_str})
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        summaries = json.loads(cleaned.strip())

        for key in parsed_sections:
            if key not in summaries:
                original = parsed_sections[key]
                summaries[key] = original[:300] if original not in ("Content not explicitly found.", "Failed to parse") else original

        return summaries
    except Exception as e:
        print(f"⚠️ Failed to generate summaries: {e}. Using truncated raw text as fallback.")
        return {
            k: v[:300] if v not in ("Content not explicitly found.", "Failed to parse") else v
            for k, v in parsed_sections.items()
        }


def download_and_parse_pdf(pdf_url: str, title: str, source_id: str, date_published: str = None, categories: list = None) -> str:
    """
    Common helper: downloads a PDF, parses it into sections, generates section summaries,
    extracts keywords, and caches everything in MongoDB.
    """
    # 1. Check Cache
    cached_paper = get_paper_by_link(pdf_url)
    if cached_paper:
        print(f"⚡ CACHE HIT: Paper already exists in database: {cached_paper['title']}")
        return _format_cached_paper(cached_paper)

    print(f"📥 CACHE MISS: Downloading PDF from {pdf_url}...")

    # 2. Download PDF
    pdf_path = f"papers/{source_id}.pdf"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(pdf_url, headers=headers, timeout=20)
        response.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(response.content)
    except Exception as e:
        return f"❌ Failed to download PDF from {pdf_url}. Error: {e}"

    # 3. Extract raw text
    try:
        doc = fitz.open(pdf_path)
        raw_text = "\n".join([page.get_text("text") for page in doc])
        doc.close()
    except Exception as e:
        return f"❌ Failed to read PDF file. Error: {e}"

    # 4. Parse sections + extract keywords with LLM
    parsed_result = llm_parse_pdf(raw_text)
    extracted_keywords = parsed_result.pop("keywords", [])
    parsed_sections = parsed_result  # only the 9 section keys remain

    # 5. Generate detailed section summaries
    section_summaries = generate_section_summaries(parsed_sections)

    # 6. Merge keywords: LLM-extracted + provided categories
    all_keywords = list(set(extracted_keywords + (categories or [])))
    if not all_keywords:
        all_keywords = ["General Research"]

    # 7. Save to MongoDB
    pub_date = date_published if date_published else datetime.now().strftime("%Y-%m-%d")
    paper_document = {
        "link": pdf_url,
        "title": title,
        "date_published": pub_date,
        "text_content": parsed_sections,
        "section_summaries": section_summaries,
        "keywords": all_keywords
    }
    insert_paper(paper_document)

    # 8. Cleanup PDF
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    lines = [
        "✅ Paper downloaded and indexed successfully.",
        "",
        f"TITLE: {title}",
        f"PUBLISHED: {pub_date}",
        f"KEYWORDS: {', '.join(all_keywords)}",
        f"SOURCE: {pdf_url}",
        "",
    ]
    section_labels = {
        "abstract": "ABSTRACT",
        "introduction": "INTRODUCTION",
        "related_work": "RELATED WORK",
        "methodology": "METHODOLOGY",
        "datasets": "DATASETS",
        "metrics": "EVALUATION METRICS",
        "results_and_evaluations": "RESULTS & EVALUATIONS",
        "conclusion": "CONCLUSION",
        "limitations": "LIMITATIONS",
    }
    for key, label in section_labels.items():
        text = parsed_sections.get(key, "")
        if text and text not in ("Content not explicitly found.", "Failed to parse"):
            lines.append(f"=== {label} ===")
            lines.append(text.strip())
            lines.append("")
    return "\n".join(lines)


def _format_cached_paper(paper: dict) -> str:
    title = paper.get("title", "Unknown")
    pub_date = paper.get("date_published", "")
    keywords = ", ".join(paper.get("keywords", []))
    sections = paper.get("text_content", {})
    summaries = paper.get("section_summaries", {})
    section_labels = {
        "abstract": "ABSTRACT",
        "introduction": "INTRODUCTION",
        "related_work": "RELATED WORK",
        "methodology": "METHODOLOGY",
        "datasets": "DATASETS",
        "metrics": "EVALUATION METRICS",
        "results_and_evaluations": "RESULTS & EVALUATIONS",
        "conclusion": "CONCLUSION",
        "limitations": "LIMITATIONS",
    }
    lines = [
        "⚡ Loaded from cache.",
        "",
        f"TITLE: {title}",
        f"PUBLISHED: {pub_date}",
        f"KEYWORDS: {keywords}",
        "",
    ]
    for key, label in section_labels.items():
        # Prefer summary for overview; raw text is in the vector DB for deep search
        text = summaries.get(key) or sections.get(key, "")
        if text and text not in ("Content not explicitly found.", "Failed to parse", "No content to summarize."):
            lines.append(f"=== {label} ===")
            lines.append(text.strip())
            lines.append("")
    return "\n".join(lines)


def process_multiple_pdfs(pdf_list: list[dict]) -> str:
    """
    Helper to process a list of PDFs in a batch.
    Expects a list of dicts: [{'url': '...', 'title': '...', 'id': '...'}, ...]
    """
    results = []
    for item in pdf_list:
        res = download_and_parse_pdf(
            pdf_url=item['url'], 
            title=item.get('title', 'Unknown Title'), 
            source_id=item.get('id', 'unknown_id')
        )
        results.append(res)
    return "\n\n---\n\n".join(results)