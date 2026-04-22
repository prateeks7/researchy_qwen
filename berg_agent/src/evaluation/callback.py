import asyncio
import json
from typing import Any
from langchain_core.callbacks import BaseCallbackHandler

# Tools whose outputs count as "retrieved context" for RAGAS
RAG_TOOLS = {"search_internal_knowledge", "search_paper_details"}
EXTERNAL_SEARCH_TOOLS = {"search_arxiv_papers", "search_semantic_scholar", "search_pubmed"}
DOWNLOAD_TOOLS = {"download_and_parse_arxiv_paper", "download_and_parse_semantic_scholar_paper", "download_pubmed_paper"}
_DIVIDER = "─" * 60


class ContextCaptureCallback(BaseCallbackHandler):
    """
    Plugs into a LangChain AgentExecutor to record:
    - retrieved_contexts : text chunks from RAG tool calls (fed to RAGAS)
    - tool_trace         : ordered list of every tool call + output preview
    - used_tools         : flat list of tool names called
    """

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.retrieved_contexts: list[str] = []
        self.tool_trace: list[dict] = []
        self.used_tools: list[str] = []

    # LangChain calls this after every tool finishes
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        name: str = kwargs.get("name", "unknown")
        output_str = str(output)

        self.used_tools.append(name)
        self.tool_trace.append({
            "tool": name,
            "output_preview": output_str[:400],
        })

        if name in RAG_TOOLS:
            # Split on the divider line we use in _format_results()
            chunks = [
                c.strip() for c in output_str.split(_DIVIDER)
                if c.strip() and len(c.strip()) > 40
            ]
            self.retrieved_contexts.extend(chunks)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def rag_was_used(self) -> bool:
        """True if at least one RAG tool was called."""
        return bool(self.retrieved_contexts)

    @property
    def external_search_used(self) -> bool:
        """True if the agent called an external search (arxiv / SS / pubmed)."""
        return bool(EXTERNAL_SEARCH_TOOLS.intersection(self.used_tools))

    @property
    def download_used(self) -> bool:
        """True if the agent downloaded at least one full paper."""
        return bool(DOWNLOAD_TOOLS.intersection(self.used_tools))

    @property
    def answered_from_memory(self) -> bool:
        """
        True when the agent produced a Final Answer without calling ANY tool.
        This is the hallucination proxy from the audit — flag these for review.
        """
        return len(self.used_tools) == 0

    def summary(self) -> dict:
        return {
            "tools_called": self.used_tools,
            "rag_used": self.rag_was_used,
            "external_search_used": self.external_search_used,
            "download_used": self.download_used,
            "answered_from_memory": self.answered_from_memory,
            "num_contexts_captured": len(self.retrieved_contexts),
        }


class StreamingCallback(BaseCallbackHandler):
    """Emits tool-start/tool-done events into an asyncio.Queue for SSE streaming."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._queue = queue
        self._loop = loop

    def _emit(self, event: dict) -> None:
        self._loop.call_soon_threadsafe(self._queue.put_nowait, json.dumps(event))

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        self._emit({"type": "tool", "name": serialized.get("name", "tool")})

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        self._emit({"type": "tool_done"})
