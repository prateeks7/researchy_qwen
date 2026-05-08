import os
import logging
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HF_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY", "")


def get_llm(model: str = "72b") -> ChatOpenAI:
    """
    Returns a ChatOpenAI-compatible LLM for the given model key.
    All three providers expose an OpenAI-compatible API, so one class handles all.

    model: "72b" | "7b" | "gemini-flash"
    """
    if model == "7b":
        if not OPEN_ROUTER_API_KEY:
            raise ValueError("OPEN_ROUTER_API_KEY not set — required for Qwen 7B")
        logger.info("LLM: Qwen 7B via OpenRouter")
        return ChatOpenAI(
            model="qwen/qwen-2.5-7b-instruct",
            base_url="https://openrouter.ai/api/v1",
            api_key=OPEN_ROUTER_API_KEY,
            max_tokens=2048,
            temperature=0.1,
            max_retries=2,
        )

    elif model == "gemini-flash":
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set — required for Gemini Flash")
        logger.info("LLM: Gemini 2.5 Flash via Google AI")
        return ChatOpenAI(
            model="gemini-2.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=GOOGLE_API_KEY,
            max_tokens=2048,
            temperature=0.1,
            max_retries=2,
        )

    else:  # 72b
        if not HF_TOKEN:
            raise ValueError("HF_TOKEN not set — required for Qwen 72B")
        logger.info("LLM: Qwen 72B via HuggingFace")
        return ChatOpenAI(
            model="Qwen/Qwen2.5-72B-Instruct",
            base_url="https://router.huggingface.co/v1",
            api_key=HF_TOKEN,
            max_tokens=2500,
            temperature=0.1,
            max_retries=1,       # was 3 — 3×180s = 9 min silent hang; fail fast instead
            request_timeout=90,  # was 180 — gemini-flash fallback kicks in after this
        )
