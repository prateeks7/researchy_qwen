"""
Request-size guardrails for multi-paper workflows.

These run before the message reaches the agent so we can enforce predictable
latency and token budgets for deep-dive and comparison requests.
"""

from __future__ import annotations

import re

MAX_DEEP_DIVE_PAPERS = 5
MAX_COMPARE_PAPERS = 5

_COMPARE_WORDS = re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.I)
_DEEP_DIVE_WORDS = re.compile(
    r"\b(explain|summari[sz]e|analy[sz]e|review|discuss|walk me through|in depth|deep dive)\b",
    re.I,
)
_COUNT_PAPERS = re.compile(r"\b(\d{1,4})\s+papers?\b", re.I)
_PAPERS_CLAUSE = re.compile(r"\|\s*papers\s*:\s*(.+)$", re.I)


def _count_explicit_paper_titles(message: str) -> int | None:
    """
    Count explicit paper titles in compare_papers style requests:
      "<question> | papers: Title A, Title B, Title C"
    """
    match = _PAPERS_CLAUSE.search(message)
    if not match:
        return None
    titles = [title.strip() for title in match.group(1).split(",") if title.strip()]
    return len(titles)


def _count_requested_papers(message: str) -> int | None:
    explicit_titles = _count_explicit_paper_titles(message)
    if explicit_titles is not None:
        return explicit_titles

    counts = [int(m.group(1)) for m in _COUNT_PAPERS.finditer(message)]
    return max(counts) if counts else None


def check(message: str) -> str | None:
    """
    Returns a refusal / shaping message if the multi-paper request exceeds the
    supported batch size, else None.
    """
    requested = _count_requested_papers(message)
    if not requested:
        return None

    is_compare = bool(_COMPARE_WORDS.search(message))
    is_deep_dive = bool(_DEEP_DIVE_WORDS.search(message))

    if is_compare and requested > MAX_COMPARE_PAPERS:
        return (
            f"I can compare up to {MAX_COMPARE_PAPERS} papers in one request with a reliable table and discussion. "
            f"You asked for {requested}. Please split this into batches of {MAX_COMPARE_PAPERS} or fewer papers."
        )

    if is_deep_dive and requested > MAX_DEEP_DIVE_PAPERS:
        return (
            f"I can do in-depth summaries for up to {MAX_DEEP_DIVE_PAPERS} papers in one request. "
            f"You asked for {requested}. Please split this into batches of {MAX_DEEP_DIVE_PAPERS} or fewer papers."
        )

    return None
