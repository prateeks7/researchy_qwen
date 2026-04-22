import requests
from langchain_core.tools import tool
from src.tools.utils.pdf_processor import download_and_parse_pdf

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_EMAIL = "research-agent@example.com"  # required by NCBI TOS


def _ncbi_get(endpoint: str, params: dict) -> requests.Response:
    params.setdefault("email", NCBI_EMAIL)
    return requests.get(f"{NCBI_BASE}/{endpoint}", params=params, timeout=15)


@tool
def search_pubmed(query: str) -> str:
    """
    Searches PubMed for biomedical, clinical, and life-science papers.
    Immediately downloads full text for any paper available on PubMed Central (PMC).
    Input: a biomedical or life-science search query (e.g. 'CRISPR gene editing cancer').
    Returns paper titles, PMIDs, authors, and download status.
    """
    print(f"🤖 Agent called search_pubmed with query: {query}")

    try:
        # Step 1: Get PMIDs
        search_resp = _ncbi_get("esearch.fcgi", {
            "db": "pubmed", "term": query, "retmax": 5, "retmode": "json"
        })
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return "No papers found on PubMed for this query."

        # Step 2: Fetch structured metadata (title, authors, dates, article IDs)
        summary_resp = _ncbi_get("esummary.fcgi", {
            "db": "pubmed", "id": ",".join(pmids), "retmode": "json"
        })
        summary_resp.raise_for_status()
        summary_data = summary_resp.json().get("result", {})

        # Step 3: Fetch plain-text abstracts for context
        abstract_resp = _ncbi_get("efetch.fcgi", {
            "db": "pubmed", "id": ",".join(pmids),
            "rettype": "abstract", "retmode": "text"
        })
        abstracts_text = abstract_resp.text[:3000]

        divider = "─" * 60
        results = []
        for i, pmid in enumerate(pmids, 1):
            doc = summary_data.get(pmid, {})
            title = doc.get("title", "Unknown Title")
            pub_date = doc.get("pubdate", "")
            authors_list = doc.get("authors", [])
            authors = ", ".join(a.get("name", "") for a in authors_list[:3])
            if len(authors_list) > 3:
                authors += f" +{len(authors_list) - 3} more"

            pmc_id = None
            for aid in doc.get("articleids", []):
                if aid.get("idtype") == "pmc":
                    pmc_id = aid.get("value", "").replace("PMC", "")
                    break

            download_status = "⬜ No free full text on PMC — use download_pubmed_paper if needed."
            if pmc_id:
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                try:
                    print(f"📥 Auto-downloading PMC{pmc_id}: {title}")
                    download_and_parse_pdf(
                        pdf_url=pdf_url,
                        title=title,
                        source_id=f"pubmed_{pmid}",
                        date_published=pub_date[:10] if pub_date else None,
                        categories=["PubMed", "Biomedical"]
                    )
                    download_status = f"✅ Full paper downloaded and indexed (PMC{pmc_id})."
                except Exception as e:
                    download_status = f"⚠️ PMC download failed: {str(e)[:100]}"

            results.append(
                f"{divider}\n"
                f"[{i}] {title}\n"
                f"    📅 {pub_date}  |  PMID: {pmid}\n"
                f"    👤 {authors}\n"
                f"    {download_status}\n"
                f"{divider}\n"
            )

        return (
            f"PubMed Results for: \"{query}\"\n\n"
            + "\n".join(results)
            + f"\nAbstracts (preview):\n{abstracts_text}"
        )

    except Exception as e:
        return f"Error searching PubMed: {str(e)}"


@tool
def download_pubmed_paper(pmid: str) -> str:
    """
    Downloads and deep-reads a specific PubMed paper by its PMID.
    Tries PMC for the full PDF. Use this when search_pubmed found a paper but couldn't auto-download it,
    or when you need full section-level content from a PubMed paper.
    Input: the PMID string (e.g. '34567890').
    """
    print(f"🤖 Agent called download_pubmed_paper for PMID: {pmid}")

    try:
        # Fetch article metadata to get PMC ID and title
        summary_resp = _ncbi_get("esummary.fcgi", {
            "db": "pubmed", "id": pmid, "retmode": "json"
        })
        summary_resp.raise_for_status()
        doc = summary_resp.json().get("result", {}).get(pmid, {})

        title = doc.get("title", f"PubMed PMID {pmid}")
        pub_date = doc.get("pubdate", "")

        pmc_id = None
        for aid in doc.get("articleids", []):
            if aid.get("idtype") == "pmc":
                pmc_id = aid.get("value", "").replace("PMC", "")
                break

        if not pmc_id:
            return (
                f"❌ No free full-text PDF found for PMID {pmid}. "
                "This paper may not be open-access on PubMed Central."
            )

        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
        return download_and_parse_pdf(
            pdf_url=pdf_url,
            title=title,
            source_id=f"pubmed_{pmid}",
            date_published=pub_date[:10] if pub_date else None,
            categories=["PubMed", "Biomedical"]
        )

    except Exception as e:
        return f"Error downloading PubMed paper {pmid}: {str(e)}"
