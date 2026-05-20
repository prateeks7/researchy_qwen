from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.prompt.sections import (
    IDENTITY,
    ABSOLUTE_LAWS,
    GUARDRAILS,
    BATCHING_LIMITS,
    WORKFLOW,
    COMPLETENESS,
    FORMAT,
    IDENTITY_ANCHOR,
    CONTEXT_LIMITS,
)

# REACT_FORMAT intentionally excluded — function-calling agent handles tool
# routing natively via the API's tools parameter, not via prompt text.
_SYSTEM_SECTIONS = [
    IDENTITY,
    ABSOLUTE_LAWS,
    GUARDRAILS,
    BATCHING_LIMITS,
    CONTEXT_LIMITS,
    WORKFLOW,
    COMPLETENESS,
    FORMAT,
    IDENTITY_ANCHOR,
]


def build_prompt() -> ChatPromptTemplate:
    system = "\n\n".join(_SYSTEM_SECTIONS)
    return ChatPromptTemplate.from_messages([
        ("system", system),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
