import os
import logging
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HF_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


def _api_key_for(base_url: str, configured_key: str, required_name: str) -> str:
    if configured_key:
        return configured_key
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return "local-not-needed"
    raise ValueError(f"{required_name} not set")


def get_llm(model: str = "72b", hf_token: str | None = None, gemini_token: str | None = None) -> ChatOpenAI:
    """
    Returns a ChatOpenAI-compatible LLM for the given model key.
    model: "72b" | "7b" | "gemini-flash" | "local72b"
    """
    if model == "7b":
        from src.tools.model_context import get_hf_token
        base_url = os.getenv("QWEN_7B_BASE_URL", "https://router.huggingface.co/v1")
        resolved_token = hf_token or get_hf_token() or os.getenv("QWEN_7B_API_KEY", HF_TOKEN)
        api_key = _api_key_for(base_url, resolved_token, "QWEN_7B_API_KEY or HF_TOKEN")
        model_name = os.getenv("QWEN_7B_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        logger.info("LLM: Qwen 7B via HuggingFace (%s)", model_name)
        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            max_tokens=2048,
            temperature=0.1,
            max_retries=2,
            request_timeout=90,
        )

    elif model == "gemini-flash":
        from src.tools.model_context import get_gemini_token
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
        resolved_gemini = gemini_token or get_gemini_token() or os.getenv("GEMINI_API_KEY", GOOGLE_API_KEY)
        api_key = _api_key_for(base_url, resolved_gemini, "GEMINI_API_KEY or GOOGLE_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        logger.info("LLM: Gemini Flash via %s (%s)", base_url, model_name)
        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            max_tokens=2048,
            temperature=0.1,
            max_retries=2,
        )

    elif model == "local72b":
        base_url = os.getenv("LOCAL_72B_BASE_URL", "http://localhost:8002/v1")
        model_name = os.getenv("LOCAL_72B_MODEL", "Qwen/Qwen2.5-72B-Instruct")
        logger.info("LLM: Local Qwen 72B via %s (%s)", base_url, model_name)
        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key="local-not-needed",
            max_tokens=2500,
            temperature=0.1,
            max_retries=1,
            request_timeout=120,
        )

    else:  # 72b (HuggingFace)
        from src.tools.model_context import get_hf_token
        base_url = os.getenv("QWEN_72B_BASE_URL", "https://router.huggingface.co/v1")
        resolved_token = hf_token or get_hf_token() or os.getenv("QWEN_72B_API_KEY", HF_TOKEN)
        api_key = _api_key_for(base_url, resolved_token, "QWEN_72B_API_KEY or HF_TOKEN")
        model_name = os.getenv("QWEN_72B_MODEL", "Qwen/Qwen2.5-72B-Instruct")
        logger.info("LLM: Qwen 72B via HuggingFace (%s)", model_name)
        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            max_tokens=2500,
            temperature=0.1,
            max_retries=1,
            request_timeout=90,
        )
