"""
Query validator — ensures queries are research-related and safe.

Protects against:
1. Off-topic queries (general chatbot misuse)
2. Suspicious patterns (prompt injection, abuse)
3. Dangerous research (dual-use, bioweapons, etc.)
4. Query length attacks

Runs BEFORE classify_query to short-circuit early.
"""

from langchain_core.tools import tool
import re

# ── Thresholds ────────────────────────────────────────────────────────────────

MAX_QUERY_LENGTH = 2000  # Prevent length-based attacks
MIN_QUERY_LENGTH = 5     # "what?" or "ok" are not queries

# Dangerous research patterns (dual-use concerns)
DANGEROUS_PATTERNS = [
    r"bioweapon",
    r"chemical weapon",
    r"nuclear.*bomb",
    r"create.*virus",
    r"synthesize.*pathogen",
    r"exploit.*vulnerability.*for.*harm",
    r"hack.*system",
    r"bypass.*security",
    r"ransomware",
    r"malware.*creation",
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore.*previous.*instruction",
    r"new.*system.*prompt",
    r"override.*rule",
    r"you.*are.*now",
    r"forget.*everything",
    r"system.*prompt",
    r"instruction.*override",
]

# General chatbot misuse patterns
CHATBOT_MISUSE = [
    r"^(hello|hi|hey|what's up|how are you)",
    r"^(tell me a joke|write a poem|cook a recipe)",
    r"^(who are you|what is your name)",
    r"debug.*code",
    r"write.*code.*for",
    r"fix.*bug",
    r"homework.*help",
    r"assignment",
    r"exam.*question",
]


# ── Validators ────────────────────────────────────────────────────────────────

def _check_length(query: str) -> tuple[bool, str]:
    """Check if query length is valid."""
    if len(query) < MIN_QUERY_LENGTH:
        return False, "❌ Query too short. Provide a research question (e.g., 'Find papers on X')."
    if len(query) > MAX_QUERY_LENGTH:
        return False, f"❌ Query too long (>{MAX_QUERY_LENGTH} chars). Please shorten it."
    return True, ""


def _check_prompt_injection(query: str) -> tuple[bool, str]:
    """Detect prompt injection attempts."""
    query_lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return False, "❌ Suspicious query pattern detected. Continuing with your research request instead."
    return True, ""


def _check_dangerous_research(query: str) -> tuple[bool, str]:
    """Detect dual-use / dangerous research requests."""
    query_lower = query.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return False, (
                "⚠️ This query appears to request help with potentially harmful research. "
                "I can only assist with academic research that follows ethical guidelines. "
                "Please rephrase your question."
            )
    return True, ""


def _check_chatbot_misuse(query: str) -> tuple[bool, str]:
    """Detect explicit general chatbot misuse — NOT topic filtering."""
    query_lower = query.lower()
    for pattern in CHATBOT_MISUSE:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return False, (
                "❌ I'm a research assistant, not a general chatbot. "
                "I help with: finding papers, explaining research, comparing studies, extracting datasets. "
                "Try: 'Find papers on [topic]' or 'Explain [paper title]'."
            )
    return True, ""


# ── Main Validator ────────────────────────────────────────────────────────────

@tool
def validate_query(query: str) -> str:
    """
    Validate that query is research-related and safe.

    Returns: "" (empty string) if valid, or an error message if invalid.

    Call this BEFORE classify_query to short-circuit early.
    """
    print(f"🛡️ Validating query safety...")

    # Check 1: Length
    valid, msg = _check_length(query)
    if not valid:
        print(f"   ✗ Length check failed")
        return msg

    # Check 2: Prompt injection
    valid, msg = _check_prompt_injection(query)
    if not valid:
        print(f"   ✗ Injection pattern detected")
        return msg

    # Check 3: Dangerous research
    valid, msg = _check_dangerous_research(query)
    if not valid:
        print(f"   ✗ Dangerous research pattern detected")
        return msg

    # Check 4: Chatbot misuse
    valid, msg = _check_chatbot_misuse(query)
    if not valid:
        print(f"   ✗ Off-topic / misuse pattern detected")
        return msg

    print(f"   ✅ Query validated")
    return ""  # Empty string = valid


def should_reject_response(response: str, original_query: str) -> tuple[bool, str]:
    """
    Post-execution check: ensure agent didn't accidentally go off-scope.

    Returns: (should_reject, error_message)
    """
    # Check if agent is answering non-research questions
    rejection_phrases = [
        "i can tell you a joke",
        "here's a recipe",
        "i'm not able to",
        "i can't help with that",
    ]

    response_lower = response.lower()
    for phrase in rejection_phrases:
        if phrase in response_lower:
            # Good — agent correctly rejected
            return False, ""

    # If response is suspiciously short and off-topic, flag it
    if len(response) < 50 and "research" not in response_lower:
        return True, "⚠️ Response appears off-topic. Please rephrase your research question."

    return False, ""
