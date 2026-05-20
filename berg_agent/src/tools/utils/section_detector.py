import re
from typing import Optional

_NOT_FOUND = "Content not explicitly found."

# Section heading patterns ordered by priority.
# Each entry: (section_key, [list of regex patterns for the heading])
_SECTION_PATTERNS = [
    ("abstract", [
        r"(?:^|\n)\s*abstract\s*\n",
        r"(?:^|\n)\s*a\s*b\s*s\s*t\s*r\s*a\s*c\s*t\s*\n",
    ]),
    ("introduction", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?introduction\s*\n",
        r"(?:^|\n)\s*(?:i\.?\s+)?introduction\s*\n",
    ]),
    ("related_work", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?related\s+work\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?background\s+(?:and\s+)?related\s+work\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?literature\s+review\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?prior\s+work\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?background\s*\n",
    ]),
    ("methodology", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?methodology\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?method(?:s)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?approach\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?proposed\s+method\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?model\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?architecture\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?framework\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?system\s+design\s*\n",
    ]),
    ("datasets", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?datasets?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?data\s+collection\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?experimental\s+setup\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?data\s*\n",
    ]),
    ("metrics", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?evaluation\s+metrics?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?metrics?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?measures?\s*\n",
    ]),
    ("results_and_evaluations", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?(?:experimental\s+)?results?\s+(?:and\s+)?(?:evaluations?|analysis|discussion)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?experiments?\s+(?:and\s+)?(?:results?|analysis)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?evaluation(?:s)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?results?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?experiments?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?analysis\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?performance\s*\n",
    ]),
    ("conclusion", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?conclusion(?:s)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?concluding\s+remarks?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?summary\s+(?:and\s+)?(?:conclusion(?:s)?|future\s+work)?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?conclusion(?:s)?\s+and\s+future\s+work\s*\n",
    ]),
    ("limitations", [
        r"(?:^|\n)\s*(?:\d+\.?\s+)?limitations?\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?limitations?\s+and\s+future\s+work\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?limitations?\s+and\s+broader\s+impact\s*\n",
        r"(?:^|\n)\s*(?:\d+\.?\s+)?ethical\s+considerations?\s*\n",
    ]),
]


def _find_heading_position(text: str, patterns: list) -> Optional[int]:
    """Return the start position of the first matching heading, or None."""
    best = None
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def detect_sections(raw_text: str) -> dict:
    """
    Split raw paper text into sections using regex heading detection.

    Returns a dict with keys matching SECTION_KEYS in pdf_processor.py.
    Sections not found are set to _NOT_FOUND.
    Zero LLM cost, ~50ms.
    """
    sections = {key: _NOT_FOUND for key, _ in _SECTION_PATTERNS}

    # Find position of each section heading in the text
    positions = {}
    for section_key, patterns in _SECTION_PATTERNS:
        pos = _find_heading_position(raw_text, patterns)
        if pos is not None:
            positions[section_key] = pos

    if not positions:
        return sections

    # Sort sections by their position in the text
    ordered = sorted(positions.items(), key=lambda x: x[1])

    # Extract text between consecutive headings
    for i, (section_key, start_pos) in enumerate(ordered):
        # Find end of heading line
        heading_end = raw_text.find("\n", start_pos)
        if heading_end == -1:
            continue
        content_start = heading_end + 1

        # Content ends at next detected section heading
        if i + 1 < len(ordered):
            content_end = ordered[i + 1][1]
        else:
            content_end = len(raw_text)

        content = raw_text[content_start:content_end].strip()

        if content and len(content) > 20:
            sections[section_key] = content

    return sections


def clean_section_text(text: str, max_chars: int = 3000) -> str:
    """Remove excessive whitespace and cap length."""
    if text == _NOT_FOUND:
        return text
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text[:max_chars].strip()
