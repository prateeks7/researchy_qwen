"""
Assembles the Berg agent prompt from named section constants.

To add, remove, or reorder a section: edit SECTIONS_ORDER below.
To edit a section's content: edit sections.py.
"""

from langchain_core.prompts import PromptTemplate

from src.prompt.sections import (
    IDENTITY,
    ABSOLUTE_LAWS,
    GUARDRAILS,
    WORKFLOW,
    COMPLETENESS,
    FORMAT,
    IDENTITY_ANCHOR,
    REACT_FORMAT,
)

SECTIONS_ORDER = [
    IDENTITY,          # 1. Who Berg is + hard scope boundaries
    ABSOLUTE_LAWS,     # 2. LAW 1-4 (no fabrication, tools first, exclusions, verification)
    GUARDRAILS,        # 3. Injection defense, scope rejection, scale limits
    WORKFLOW,          # 4. Research procedure
    COMPLETENESS,      # 5. N-item coverage rule
    FORMAT,            # 6. Output formatting rules
    IDENTITY_ANCHOR,   # 7. Identity re-assertion — last thing before the question
    REACT_FORMAT,      # 8. ReAct variables — always last
]


def build_prompt() -> PromptTemplate:
    template = "\n\n".join(SECTIONS_ORDER)
    return PromptTemplate.from_template(template)
