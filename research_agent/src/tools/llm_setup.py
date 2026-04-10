import os
from langchain_huggingface import HuggingFaceEndpoint
from dotenv import load_dotenv

load_dotenv()

HUGGINGFACE_TOKEN = os.getenv("HF_TOKEN")

def get_llm(model_size="7b"):
    repo_id = "Qwen/Qwen2.5-7B-Instruct" if model_size == "7b" else "Qwen/Qwen2.5-14B-Instruct"
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN not found in environment variables")
    llm = HuggingFaceEndpoint(
        repo_id=repo_id,
        task="text-generation",
        huggingfacehub_api_token=HF_TOKEN,
        max_new_tokens=4000,
        temperature=0.1,
        repetition_penalty=1.1,
        return_full_text=False,
    )
    return llm