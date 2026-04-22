"""
Exclusion constraint enforcement with synonym expansion.

Shared by server.py (runtime guard) and evaluator.py (scoring).
"""

import re

# ── Regex patterns for extracting exclusion phrases from a question ───────────

_EXCL_PATTERNS = [
    re.compile(r'\bexclu(?:ding|de)\b\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
    re.compile(r'\bexcept\b\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
    re.compile(r'\bnot\s+including\b\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
    re.compile(r'\bwithout\b\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
    re.compile(r'\bno\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
    re.compile(r'\bavoid(?:ing)?\b\s+([\w\s,/\-]+?)(?:\.|,|$|\n)', re.I),
]
_SPLIT = re.compile(r',|\s+and\s+|\s+or\s+', re.I)

# ── Synonym map ───────────────────────────────────────────────────────────────
# Maps a canonical term → all surface forms that count as violations.
# Keys are lowercase. Values are checked as whole-word or substring matches.

SYNONYM_MAP: dict[str, list[str]] = {
    # Reinforcement learning
    "reinforcement learning": [
        "reinforcement learning", "rl", "deep rl", "deep reinforcement",
        "policy gradient", "policy optimization", "q-learning", "deep q",
        "dqn", "ppo", "proximal policy", "a3c", "actor-critic", "td learning",
        "temporal difference", "reward shaping", "markov decision", "mdp",
        "rlhf", "reinforcement learning from human feedback",
    ],
    # Imitation learning
    "imitation learning": [
        "imitation learning", "il", "behavioral cloning", "bc",
        "inverse reinforcement", "inverse rl", "irl", "dagger",
        "learning from demonstration", "lfd", "learning from demos",
    ],
    # VLA / vision-language-action models
    "vla": [
        "vla", "vision-language-action", "vision language action",
        "rt-2", "rt2", "openvla", "octo",
    ],
    # Large language models
    "large language models": [
        "large language model", "llm", "llms", "gpt", "chatgpt",
        "claude", "gemini", "palm", "llama", "mistral", "falcon",
        "language model", "language models", "foundation model",
    ],
    # Transformers
    "transformers": [
        "transformer", "transformers", "attention mechanism",
        "self-attention", "multi-head attention", "bert", "gpt",
        "encoder-decoder",
    ],
    # Neural networks
    "neural networks": [
        "neural network", "neural networks", "deep learning", "deep neural",
        "cnn", "convolutional neural", "rnn", "recurrent neural",
        "lstm", "gru", "mlp", "multilayer perceptron",
    ],
    # Diffusion models
    "diffusion models": [
        "diffusion model", "diffusion models", "score matching",
        "ddpm", "denoising diffusion", "stable diffusion", "latent diffusion",
    ],
    # GANs
    "gans": [
        "gan", "gans", "generative adversarial", "discriminator",
        "generator network",
    ],
    # Supervised learning
    "supervised learning": [
        "supervised learning", "supervised", "labelled data", "labeled data",
        "classification", "regression",
    ],
    # Computer vision
    "computer vision": [
        "computer vision", "cv", "image recognition", "object detection",
        "image segmentation", "visual recognition",
    ],
    # NLP
    "nlp": [
        "nlp", "natural language processing", "natural language",
        "text classification", "sentiment analysis", "named entity",
    ],
}


def _expand_term(term: str) -> list[str]:
    """Returns all surface forms for a term (itself + any known synonyms)."""
    t = term.strip().lower()
    # Direct key match
    if t in SYNONYM_MAP:
        return SYNONYM_MAP[t]
    # Check if term is a synonym value of any key
    for canonical, variants in SYNONYM_MAP.items():
        if t in variants:
            return variants
    # No synonym entry — return the term as-is
    return [t]


def extract_exclusions(message: str) -> list[str]:
    """
    Parses exclusion phrases from a question and expands each to all synonyms.
    Returns a flat deduplicated list of all terms to block.
    """
    raw_terms: list[str] = []
    for pat in _EXCL_PATTERNS:
        for m in pat.finditer(message):
            for part in _SPLIT.split(m.group(1)):
                t = part.strip().lower()
                if t and len(t) > 1:
                    raw_terms.append(t)

    expanded: list[str] = []
    for term in set(raw_terms):
        expanded.extend(_expand_term(term))

    return list(set(expanded))


def check_exclusion_violations(question: str, answer: str) -> list[str]:
    """
    Returns all exclusion terms (including synonyms) found in the answer.
    Uses whole-word matching to avoid false positives (e.g. 'rl' in 'early').
    """
    answer_lower = answer.lower()
    violations = []
    for term in extract_exclusions(question):
        # Whole-word boundary match for short terms, substring for longer ones
        if len(term) <= 4:
            pattern = rf'\b{re.escape(term)}\b'
            if re.search(pattern, answer_lower):
                violations.append(term)
        else:
            if term in answer_lower:
                violations.append(term)
    return list(set(violations))
