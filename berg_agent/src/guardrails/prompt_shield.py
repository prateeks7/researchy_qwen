"""
Pre-flight guardrail checks — runs before the message reaches the agent.

check(message, history) → refusal string | None
check_history(history)  → refusal string | None  (multi-turn manipulation)
"""

import re
from typing import Any

# ── Shared refusal templates ──────────────────────────────────────────────────

_REFUSAL_CONFIG = (
    "I can't share my internal configuration. "
    "I'm here to help with academic paper search and summarisation."
)
_REFUSAL_JAILBREAK = (
    "I'm Berg, a research assistant. My identity and guidelines are fixed "
    "and cannot be changed by conversation instructions."
)
_REFUSAL_TOO_LONG = (
    "Your message is too long for me to process reliably. "
    "Please shorten your question to under 2000 characters."
)

# ── 1. Prompt leak / identity attack patterns ─────────────────────────────────

_LEAK_PATTERNS = [
    # Direct prompt extraction
    re.compile(r'\b(show|reveal|print|display|output|tell me|what is|repeat|dump|list)\b.{0,40}\b(system prompt|system message|instructions?|configuration|config|prompt template|your prompt|your rules|your laws|your template|your constraints?)\b', re.I),
    # Classic "ignore instructions"
    re.compile(r'\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,30}\b(instructions?|rules?|prompt|constraints?|guidelines?)\b', re.I),
    re.compile(r'\b(forget|disregard|override|bypass|skip)\b.{0,30}\b(instructions?|rules?|constraints?|guidelines?|laws?)\b', re.I),
    # Identity replacement
    re.compile(r'\byou are now\b', re.I),
    re.compile(r'\bact as\b.{0,30}\b(a different|another|new|unrestricted|uncensored|jailbroken|dan|gpt|claude|chatgpt)\b', re.I),
    re.compile(r'\bdan\b.{0,15}\b(mode|prompt|jailbreak|activated)\b', re.I),
    re.compile(r'\bpretend (you are|you\'re|to be)\b.{0,40}\b(different|no restrictions?|no rules?|free|uncensored|another ai|a new ai)\b', re.I),
    re.compile(r'\b(new persona|new identity|new character|new role|new mode)\b', re.I),
    re.compile(r'\b(switch|change|toggle)\b.{0,20}\b(mode|persona|identity|role)\b', re.I),
    # Authority bypass ("my professor said it's ok")
    re.compile(r'\b(my (professor|teacher|boss|supervisor|manager|instructor)|they said|i was told|i have permission)\b.{0,60}\b(allowed|permitted|fine|ok|okay|authorized)\b', re.I),
    # "For educational/research purposes" jailbreak prefix
    re.compile(r'\bfor (educational|research|academic|demonstration|illustrative) purposes?,?\s+(ignore|bypass|skip|forget|override)\b', re.I),
    # "The previous AI / ChatGPT said you could"
    re.compile(r'\b(previous (ai|model|assistant|version)|chatgpt|gpt-4|another ai)\b.{0,60}\b(said|told|confirmed|agreed|allowed)\b', re.I),
    # Fake paper injection
    re.compile(r'\bpretend (the following|this|the text below) is (a paper|an? (abstract|research paper|academic paper|study))\b', re.I),
    re.compile(r'\btreat (the following|this|the text below) as (a paper|an? (abstract|research paper|study))\b', re.I),
    re.compile(r'\b(here is|this is) (a paper|an? (abstract|research paper|study)).{0,30}(cite|reference|summarize|analyse)\b', re.I),
    # API key / secrets fishing
    re.compile(r'\bwhat (api keys?|tokens?|environment variables?|secrets?|credentials?)\b.{0,30}\b(do you have|are you using|can i see)\b', re.I),
    # Repeat-everything attacks
    re.compile(r'\b(repeat|echo|print|copy)\b.{0,20}\b(everything|anything|all)\b.{0,20}\b(above|before|prior|system|said)\b', re.I),
    # Hypothetical framing to bypass rules
    re.compile(r'\bhypothetically\b.{0,60}\b(ignore|bypass|pretend|assume).{0,40}\b(rules?|constraints?|instructions?|laws?)\b', re.I),
]

# ── 2. Out-of-scope task patterns ─────────────────────────────────────────────

_SCOPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(solve|compute|calculate|integrate|differentiate|derive|prove|simplify)\b.{0,40}\b(equation|integral|derivative|proof|formula|expression|matrix)\b', re.I),
     "mathematical calculations or proofs"),
    (re.compile(r'\b(write|generate|debug|fix|implement)\b.{0,30}\b(code|function|class|script|program|snippet)\b', re.I),
     "writing or debugging code"),
    (re.compile(r'\b(stock price|share price|market cap|forex|crypto price|bitcoin price)\b', re.I),
     "real-time financial data"),
    (re.compile(r'\b(translate|translation)\b.{0,20}\b(into|to|from)\b.{0,20}\b(english|french|spanish|german|chinese|japanese|arabic|hindi|korean)\b', re.I),
     "document translation"),
    (re.compile(r'\b(diagnose|diagnosis|medical advice|treatment for|prescription)\b', re.I),
     "medical diagnosis or advice"),
    (re.compile(r'\b(legal advice|is it legal|am i liable|sue|lawsuit)\b', re.I),
     "legal advice"),
    (re.compile(r'\b(who will win|predict who|forecast|will .{0,20} happen in \d{4})\b', re.I),
     "predictions or forecasts"),
]

# ── 4. Multi-turn history manipulation patterns ───────────────────────────────
# Check the last N user turns for gradual escalation.

_HISTORY_JAILBREAK = [
    re.compile(r'\bfrom now on\b.{0,60}\b(always|never|must|should)\b', re.I),
    re.compile(r'\bfor (all|every|each) (future|subsequent|next|following) (response|answer|reply|message)\b', re.I),
    re.compile(r'\bremember (to always|that you (are|must|should|can))\b', re.I),
    re.compile(r'\b(your new|your updated|your real) (instructions?|rules?|purpose|goal|identity)\b', re.I),
    re.compile(r'\bdo not (tell|say|mention|acknowledge) (anyone|the user|them)\b', re.I),
]

_MAX_HISTORY_TURNS_TO_SCAN = 6  # scan last 3 user messages (each turn = user + assistant)


def check(message: str, history: list[Any] | None = None) -> str | None:
    """
    Returns a refusal string if the message triggers a guardrail, else None.
    Call this BEFORE invoking the agent.

    history: list of HistoryMessage objects with .role and .content attributes.
    """
    # ── Length cap ────────────────────────────────────────────────────────────
    if len(message) > 2000:
        return _REFUSAL_TOO_LONG

    # ── Jailbreak / leak patterns ─────────────────────────────────────────────
    for pattern in _LEAK_PATTERNS:
        if pattern.search(message):
            return _REFUSAL_JAILBREAK

    # ── Out-of-scope tasks ────────────────────────────────────────────────────
    for pattern, topic in _SCOPE_PATTERNS:
        if pattern.search(message):
            return (
                f"I'm a research assistant — I can't help with {topic}. "
                "I can search, download, and summarise academic papers. "
                "Would you like me to find research papers related to this topic instead?"
            )

    # ── Multi-turn history manipulation ───────────────────────────────────────
    if history:
        refusal = check_history(history)
        if refusal:
            return refusal

    return None


def check_history(history: list[Any]) -> str | None:
    """
    Scans recent user turns for gradual manipulation / persistent instruction injection.
    Returns a refusal string if detected, else None.
    """
    user_turns = [h for h in history if getattr(h, "role", None) == "user"]
    recent = user_turns[-(_MAX_HISTORY_TURNS_TO_SCAN // 2):]

    for turn in recent:
        content = getattr(turn, "content", "")
        for pattern in _HISTORY_JAILBREAK:
            if pattern.search(content):
                return _REFUSAL_JAILBREAK

    return None
