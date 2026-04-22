import os
import time
import logging
from typing import Any, Optional

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from pydantic import PrivateAttr

load_dotenv()
logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HF_TOKEN")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY", "")

_MAX_RETRIES = 3
_RETRY_DELAYS = [5, 15, 30]

_MAX_TOKENS_72B = 2500
_MAX_TOKENS_7B = 2048


class QwenLLM(LLM):
    """LangChain LLM wrapper around HuggingFace InferenceClient — unchanged from original."""
    model_name: str = "Qwen/Qwen2.5-72B-Instruct"
    max_new_tokens: int = _MAX_TOKENS_72B
    temperature: float = 0.1
    _timeout: int = PrivateAttr(default=180)

    _client: InferenceClient = PrivateAttr()

    def __init__(self, api_key: str, timeout: int = 180, **kwargs: Any):
        super().__init__(**kwargs)
        self._timeout = timeout
        self._client = InferenceClient(api_key=api_key, timeout=timeout)

    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_timeout = any(k in err_str for k in ("504", "502", "timeout", "timed out", "read operation"))
                if is_timeout and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_DELAYS[attempt]
                    logger.warning("HF timeout (attempt %d/%d) — retrying in %ds...", attempt + 1, _MAX_RETRIES, wait)
                    time.sleep(wait)
                else:
                    raise
        raise last_error

    @property
    def _llm_type(self) -> str:
        return "qwen_inference_llm"


class OpenRouterLLM(LLM):
    """Qwen 7B via OpenRouter OpenAI-compatible API."""
    model_name: str = "qwen/qwen-2.5-7b-instruct"
    max_new_tokens: int = _MAX_TOKENS_7B
    temperature: float = 0.1

    _client: Any = PrivateAttr()

    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__(**kwargs)
        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content

    @property
    def _llm_type(self) -> str:
        return "openrouter_llm"


class GeminiLLM(LLM):
    """Gemini via Google's OpenAI-compatible endpoint — avoids langchain-google-genai parsing bugs."""
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.1

    _client: Any = PrivateAttr()

    def __init__(self, api_key: str, **kwargs: Any):
        super().__init__(**kwargs)
        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def _call(
        self,
        prompt: str,
        stop: Optional[list] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=self.temperature,
        )
        return response.choices[0].message.content

    @property
    def _llm_type(self) -> str:
        return "gemini_llm"


def get_llm(model: str = "72b") -> LLM:
    """
    model: "72b" | "7b" | "gemini-flash"
    """
    if model == "7b":
        if not OPEN_ROUTER_API_KEY:
            raise ValueError("OPEN_ROUTER_API_KEY not set — required for Qwen 7B")
        print("🔌 LLM: Qwen/Qwen2.5-7B-Instruct via OpenRouter")
        return OpenRouterLLM(api_key=OPEN_ROUTER_API_KEY)
    elif model == "gemini-flash":
        if not GOOGLE_API_KEY or not GOOGLE_API_KEY.strip():
            raise ValueError("GOOGLE_API_KEY not set — required for Gemini Flash")
        print("🔌 LLM: gemini-2.5-flash via Google AI")
        return GeminiLLM(api_key=GOOGLE_API_KEY)
    else:
        if not HF_TOKEN:
            raise ValueError("HF_TOKEN not found in environment variables")
        print("🔌 LLM: Qwen/Qwen2.5-72B-Instruct via HuggingFace")
        return QwenLLM(api_key=HF_TOKEN, max_new_tokens=_MAX_TOKENS_72B, timeout=180)
