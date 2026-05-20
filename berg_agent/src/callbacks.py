import asyncio
import json
from typing import Any
from langchain_core.callbacks import BaseCallbackHandler

RAG_TOOLS      = {"search_internal_knowledge", "search_paper_details"}
EXTERNAL_TOOLS = {"search_arxiv_papers", "search_semantic_scholar", "search_pubmed"}
DOWNLOAD_TOOLS = {"download_and_parse_arxiv_paper", "download_and_parse_semantic_scholar_paper", "download_pubmed_paper"}
_DIVIDER       = "─" * 60


class ContextCaptureCallback(BaseCallbackHandler):
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.retrieved_contexts: list[str] = []
        self.tool_trace: list[dict] = []
        self.used_tools: list[str] = []

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        name = kwargs.get("name", "unknown")
        output_str = str(output)
        self.used_tools.append(name)
        self.tool_trace.append({"tool": name, "output_preview": output_str[:400]})

        if name in RAG_TOOLS:
            chunks = [c.strip() for c in output_str.split(_DIVIDER) if c.strip() and len(c.strip()) > 40]
            self.retrieved_contexts.extend(chunks)
        elif name in DOWNLOAD_TOOLS and len(output_str) > 200:
            step = 2000
            for i in range(0, min(len(output_str), 12000), step):
                chunk = output_str[i:i + step].strip()
                if chunk:
                    self.retrieved_contexts.append(chunk)
        elif name in EXTERNAL_TOOLS and len(output_str) > 100:
            self.retrieved_contexts.append(output_str[:3000])

    @property
    def answered_from_memory(self) -> bool:
        return len(self.used_tools) == 0

    def summary(self) -> dict:
        return {
            "tools_called": self.used_tools,
            "num_contexts_captured": len(self.retrieved_contexts),
            "answered_from_memory": self.answered_from_memory,
        }


class StreamingCallback(BaseCallbackHandler):
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._queue = queue
        self._loop  = loop

    def _emit(self, event: dict) -> None:
        self._loop.call_soon_threadsafe(self._queue.put_nowait, json.dumps(event))

    def emit_cache_check_start(self) -> None:
        self._emit({"type": "tool", "name": "cache_check"})

    def emit_cache_check_done(self, hit: bool) -> None:
        self._emit({"type": "tool_done", "name": "cache_check",
                    "display_name": "cache_hit" if hit else "cache_miss", "cache_hit": hit})

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        name = serialized.get("name") or kwargs.get("name", "tool")
        self._emit({"type": "tool", "name": name})

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        output_str = str(output)
        is_db_hit = output_str.startswith("🌍 Loaded from database")
        self._emit({"type": "tool_done", "name": kwargs.get("name", "tool"),
                    "display_name": "cache_hit" if is_db_hit else None,
                    "cache_hit": is_db_hit})
