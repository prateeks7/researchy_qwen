import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from src.db.mongo_client import papers_collection

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
persist_directory = "./chroma_db"

SKIP_VALUES = {"Content not explicitly found.", "Failed to parse", "No content to summarize."}


def get_vector_store():
    """Initializes and returns the ChromaDB connection."""
    return Chroma(
        collection_name="academic_papers",
        embedding_function=embeddings,
        persist_directory=persist_directory
    )


def sync_mongo_to_chroma():
    """
    Pulls all papers from MongoDB and embeds two document layers per section:
    - <link>_<section>_summary : detailed section summary (for fast overview search)
    - <link>_<section>_raw     : full raw section text (for deep content search)
    Keywords are embedded in the page_content and stored in metadata.
    """
    print("🔄 Syncing MongoDB papers to Vector Database...")
    vector_store = get_vector_store()

    existing_data = vector_store.get()
    existing_ids = set(existing_data["ids"]) if existing_data else set()

    all_papers = list(papers_collection.find({}))
    new_docs = []

    for paper in all_papers:
        title = paper.get("title", "Unknown")
        link = paper.get("link", "Unknown")
        keywords = paper.get("keywords", [])
        keywords_str = ", ".join(keywords) if keywords else "General Research"
        raw_sections = paper.get("text_content", {})
        summaries = paper.get("section_summaries", {})

        for section_name, raw_text in raw_sections.items():
            if raw_text in SKIP_VALUES:
                continue

            summary_text = summaries.get(section_name, "")
            if not summary_text or summary_text in SKIP_VALUES:
                summary_text = raw_text[:400]

            # --- Summary layer ---
            summary_id = f"{link}_{section_name}_summary"
            if summary_id not in existing_ids:
                new_docs.append(Document(
                    page_content=(
                        f"Paper: {title}\n"
                        f"Keywords: {keywords_str}\n"
                        f"Section: {section_name}\n"
                        f"Summary: {summary_text}"
                    ),
                    metadata={
                        "title": title,
                        "link": link,
                        "section": section_name,
                        "keywords": keywords_str,
                        "doc_type": "summary",
                        "source": "mongodb"
                    },
                    id=summary_id
                ))

            # --- Raw text layer ---
            raw_id = f"{link}_{section_name}_raw"
            if raw_id not in existing_ids:
                new_docs.append(Document(
                    page_content=(
                        f"Paper: {title}\n"
                        f"Keywords: {keywords_str}\n"
                        f"Section: {section_name}\n"
                        f"Content: {raw_text}"
                    ),
                    metadata={
                        "title": title,
                        "link": link,
                        "section": section_name,
                        "keywords": keywords_str,
                        "doc_type": "raw",
                        "source": "mongodb"
                    },
                    id=raw_id
                ))

    if new_docs:
        doc_ids = [doc.id for doc in new_docs]
        vector_store.add_documents(documents=new_docs, ids=doc_ids)
        print(f"✅ Added {len(new_docs)} new section documents to the Vector Database.")
    else:
        print("⚡ Vector Database is already up to date with MongoDB.")


def _format_results(results: list) -> str:
    if not results:
        return "No relevant information found in the internal database."
    divider = "─" * 60
    parts = []
    for i, res in enumerate(results, 1):
        meta = res.metadata
        title = meta.get("title", "Unknown")
        section = meta.get("section", "").replace("_", " ").title()
        keywords = meta.get("keywords", "")
        doc_type = meta.get("doc_type", "")
        type_label = "[SUMMARY]" if doc_type == "summary" else "[FULL TEXT]" if doc_type == "raw" else ""

        # Strip the redundant header lines that are already in metadata
        content = res.page_content
        for prefix in (f"Paper: {title}\n", f"Keywords: {keywords}\n",
                       f"Section: {meta.get('section', '')}\n"):
            content = content.replace(prefix, "")
        content = content.replace("Summary: ", "").replace("Content: ", "").strip()

        parts.append(
            f"{divider}\n"
            f"[{i}] {title} {type_label}\n"
            f"    Section: {section}  |  Keywords: {keywords}\n"
            f"{divider}\n"
            f"{content}\n"
        )
    return "\n".join(parts)


def search_vector_db(query: str, k: int = 5) -> str:
    """
    Keyword-aware semantic search over section SUMMARIES.
    Use this for a fast, broad overview of relevant paper sections.
    """
    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, k=k, filter={"doc_type": "summary"})
    if not results:
        # Fallback: search without doc_type filter (handles old-format docs)
        results = vector_store.similarity_search(query, k=k)
    return _format_results(results)


def search_vector_db_raw(query: str, k: int = 3) -> str:
    """
    Deep search over RAW section text for detailed content retrieval.
    Use this when summaries are insufficient and full section content is needed.
    """
    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, k=k, filter={"doc_type": "raw"})
    if not results:
        results = vector_store.similarity_search(query, k=k)
    return _format_results(results)