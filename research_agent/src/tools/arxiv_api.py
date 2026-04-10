import os
import arxiv
import fitz
from datetime import datetime
from src.db.mongo_client import insert_paper, get_paper_by_link
from src.tools.llm_setup import get_llm

os.makedirs("papers",exist_ok=True)

def llm_parse_pdf(raw_text: str) -> dict:
    structuring_llm = get_llm(model_size="7b")
    
    truncated_text = raw_text[:30000]
    prompt = PromptTemplate.from_template(
        """You are a strict data extraction agent. Read the following raw text from an academic research paper.
        Extract the main sections and summarize them if they are too long. 
        You MUST respond ONLY with a valid JSON object using exactly these four keys: "abstract", "introduction", "related_work", "methodology", "datasets","metrics","results_and_evaluations","conclusion", "limitations".
        Do not include any Markdown blocks, introduction, or explanations. Just the JSON.

        RAW TEXT:
        {text}
        
        JSON OUTPUT:"""
    )

    chain = prompt | structuring_llm

    print("Structuring Agent (7B) is analysing the PDF...")
    try: 
        response = chain.invoke({"text":truncated_text})
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
            
        parsed_json = json.loads(cleaned_response.strip())

        return parsed_json
    except json.JSONDecodeError as e:
        print(f"LLM failed to return a valid JSON: {e}")
        print(f"Raw response: {response}")
        return {"abstract": "Failed to parse abstract", "introduction": "Failed to parse introduction", "methodology": "Failed to parse methodology", "conclusion": "Failed to parse conclusion"}

@tool
def fetch_arxiv_paper(query:str) -> str:
    print(f"Agent caled fetch_arxiv_paper with query: {query}")

    client = arxiv.Client()
    search = arxiv.Search(query=query,max_results=1,sort_by=arxiv.SortCriterion.Relevance)
    try:
        paper = next(client.results(search))
    except StopIteration:
        return f"No paper found on Arxiv for query: {query}"
    
    paper_url = paper.pdf_url
    cached_paper = get_paper_by_link(paper_url)
    if cached_paper:
        print(f"Paper already exists in database: {cached_paper['title']}")
        return     
    print(f"Downloading paper: {paper.title}")
    paper.download_pdf(dirpath="papers",filename=f"{paper.get_short_id()}.pdf")
    pdf_path = f"papers/{paper.get_short_id()}.pdf"
    