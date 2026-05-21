import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List

from langchain_core.messages import HumanMessage, AIMessage

import json as _json
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from src.auth.jwt_utils import create_token, get_current_user
from src.auth.oauth import (
    FRONTEND_URL,
    github_auth_url, github_get_user,
    google_auth_url, google_get_user,
)
from src.db.mongo_client import (
    get_or_create_oauth_user,
    create_user, get_user_by_email,
    create_session, get_sessions_by_user, get_session,
    append_message, update_session_title, delete_session,
    create_compare_session, get_compare_sessions_by_user, get_compare_session,
    append_compare_turn, update_compare_session_title, delete_compare_session,
)
from src.guardrails.exclusions import check_exclusion_violations
from src.guardrails.prompt_shield import check as shield_check
from src.guardrails.request_limits import check as request_limit_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_PAPER_QUERY = re.compile(
    r'\b(paper|papers|research|study|studies|find|search|recent|published|tell me about)\b', re.I
)
_FRESH_DISCOVERY_QUERY = re.compile(
    r'\b(latest|recent|new|newest|search for|find|recommend|discover|get me|give me|show me|list|fetch|look up|look for|can you get|any papers)\b'
    r'.*\b(paper|papers|research|study|studies|article|articles|publication|publications|work)\b'
    r'|\b(paper|papers|research|study|studies)\b.*\b(latest|recent|new|newest|on|about|regarding|related to)\b'
    r'|\b(papers?|research|studies)\b\s+(on|about|regarding|related to|for)\b',
    re.I,
)
_SPECIFIC_DETAIL_QUERY = re.compile(
    r'\b(exact|specific|details?|detail|dataset|datasets|metric|metrics|result|results|methodology|limitations|raw text|quote|quotes)\b',
    re.I,
)
# Only strip Thought blocks when a Final Answer line actually follows — avoids wiping
# responses from models (e.g. Gemini) that don't always emit a Final Answer header.
_THOUGHT_BLOCK = re.compile(r"^\s*Thought:.*?(?=^\s*Final Answer:)", re.I | re.S | re.M)
_FINAL_ANSWER_PREFIX = re.compile(r"^\s*Final Answer:\s*", re.I)
_INLINE_FINAL_ANSWER = re.compile(r"\bFinal Answer:\s*", re.I)
_LEADING_SCRATCHPAD = re.compile(
    r"^\s*(Thought|Observation|Action|Action Input)\s*:\s*.*$",
    re.I | re.M,
)

# ── Agent singletons ──────────────────────────────────────────────────────────

MODEL_KEY_TO_NAME = {
    "qwen7b": "7b",
    "qwen72b": "72b",
    "local72b": "local72b",
    "gemini": "gemini-flash",
}
MODEL_NAME_TO_KEY = {v: k for k, v in MODEL_KEY_TO_NAME.items()}

_agent = None        # Qwen 72B (lazy, kept for existing compare code paths)
_agent_7b = None     # Qwen 7B  (lazy)
_agent_gemini = None # Gemini   (lazy)
_agents: dict[str, object] = {}
_agent_init_lock = asyncio.Lock()
_startup_ready = False

_executor = ThreadPoolExecutor(max_workers=4)
_AGENT_TIMEOUT_SECONDS = 600
_COMPARE_TIMEOUT_SECONDS = 600


def _resolve_model(model_key: str | None) -> str:
    return MODEL_KEY_TO_NAME.get(model_key or "qwen72b", "72b")


def _validate_model_key(model_key: str | None) -> str:
    key = model_key or "qwen72b"
    if key not in MODEL_KEY_TO_NAME:
        raise HTTPException(status_code=400, detail="Unknown model key.")
    return key


def _init_vector_store():
    from src.db.vector_store import sync_mongo_to_chroma
    logger.info("Syncing MongoDB → ChromaDB …")
    sync_mongo_to_chroma()


def _build_agent(model: str):
    from src.agent import get_research_agent
    logger.info("Loading agent for model: %s", model)
    return get_research_agent(model)


async def _get_agent_for_request(
    model_name: str,
    user_hf_token: str | None,
    user_gemini_token: str | None,
):
    """
    Always build a fresh agent when the user supplied any API token via the UI.
    Fall back to the cached agent only when no user tokens are present (relies on .env).
    This ensures the user's UI-entered keys are always used instead of env vars.
    """
    if user_hf_token or user_gemini_token:
        def _build():
            # Set thread-local on this worker thread so any get_llm() call during
            # agent construction (or any code path the build accidentally triggers)
            # finds the user's tokens. Without this, a build-time get_llm() with
            # no explicit token args would fall back to env vars and fail.
            from src.tools.model_context import apply_thread_context
            apply_thread_context(model_name, user_hf_token, user_gemini_token)
            from src.agent import get_research_agent
            return get_research_agent(
                model_name,
                hf_token=user_hf_token,
                gemini_token=user_gemini_token,
            )
        return await asyncio.get_event_loop().run_in_executor(_executor, _build)
    return await _ensure_agent(model_name)


def _remember_agent(model: str, agent_exec):
    global _agent, _agent_7b, _agent_gemini
    _agents[model] = agent_exec
    if model == "72b":
        _agent = agent_exec
    elif model == "7b":
        _agent_7b = agent_exec
    elif model == "gemini-flash":
        _agent_gemini = agent_exec


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_ready
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _init_vector_store)
    _startup_ready = True
    logger.info("✅ Berg Agent ready.")
    yield
    _executor.shutdown(wait=False)


async def _ensure_agent(model: str):
    """Lazy-initialize the requested model agent and return it."""
    if model in _agents:
        return _agents[model]
    async with _agent_init_lock:
        if model in _agents:
            return _agents[model]
        loop = asyncio.get_event_loop()
        agent_exec = await loop.run_in_executor(_executor, _build_agent, model)
        _remember_agent(model, agent_exec)
        logger.info("✅ Agent ready for model: %s", model)
        return agent_exec


async def _ensure_compare_agents():
    """Lazy-initialize all three compare agents."""
    await asyncio.gather(
        _ensure_agent("7b"),
        _ensure_agent("72b"),
        _ensure_agent("gemini-flash"),
    )
    logger.info("✅ Compare agents ready (7B + 72B + Gemini).")


app = FastAPI(title="Berg Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    user_id: str
    email: str

class SessionCreate(BaseModel):
    title: str = "New conversation"

class SessionMeta(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str

class SessionMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class SessionDetail(SessionMeta):
    messages: List[SessionMessage]

class ChatRequest(BaseModel):
    message: str
    session_id: str
    model_key: str = "qwen72b"
    hf_token: str | None = None
    gemini_token: str | None = None

class ChatResponse(BaseModel):
    response: str

class CompareSessionCreate(BaseModel):
    title: str = "New comparison"

class CompareSessionMeta(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str

class CompareTurnResponse(BaseModel):
    user_message: str
    responses: dict   # {qwen7b, qwen72b, gemini}
    timings: dict     # {qwen7b, qwen72b, gemini} in seconds
    timestamp: str

class CompareSessionDetail(CompareSessionMeta):
    turns: List[CompareTurnResponse]

class CompareRequest(BaseModel):
    message: str
    session_id: str

class CompareResponse(BaseModel):
    responses: dict   # {qwen7b, qwen72b, gemini}
    timings: dict     # {qwen7b, qwen72b, gemini}

class CompareStreamRequest(BaseModel):
    message: str
    session_id: str
    hf_token: str | None = None
    gemini_token: str | None = None

class CompareTurnSave(BaseModel):
    user_message: str
    responses: dict
    timings: dict


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_history(messages: list) -> list:
    result = []
    for msg in messages:
        if msg["role"] == "user":
            result.append(HumanMessage(content=msg["content"]))
        else:
            result.append(AIMessage(content=msg["content"]))
    return result


def _normalize_agent_output(text: str) -> str:
    """Strip leaked scratchpad markers like `Thought:` and `Final Answer:`."""
    original = (text or "").strip()
    if not original:
        return ""
    cleaned = _THOUGHT_BLOCK.sub("", original).strip()
    cleaned = _LEADING_SCRATCHPAD.sub("", cleaned).strip()
    cleaned = _FINAL_ANSWER_PREFIX.sub("", cleaned).strip()
    cleaned = _INLINE_FINAL_ANSWER.sub("", cleaned, count=1).strip()
    # Safety: if normalization wiped everything, return original rather than empty
    return cleaned if cleaned else original


_EXPLICIT_WEB_SEARCH = re.compile(
    r'^\s*(search web|search the web|search the internet|search online|look up online)',
    re.I,
)

def _preflight_kb(message: str) -> str | None:
    """Check if relevant papers are already in the vector DB. Returns context or None."""
    if _EXPLICIT_WEB_SEARCH.search(message):
        logger.info("❌ ChromaDB cache preflight skipped — user requested explicit web search.")
        return None
    if _FRESH_DISCOVERY_QUERY.search(message) and not _SPECIFIC_DETAIL_QUERY.search(message):
        logger.info("❌ ChromaDB cache preflight skipped for freshness-sensitive discovery query.")
        return None

    from src.db.vector_store import search_vector_db
    try:
        result = search_vector_db(message, k=3)
        if not result or "No relevant" in result or "no relevant" in result:
            logger.info("❌ ChromaDB cache preflight miss.")
            return None
        logger.info("🌍 ChromaDB cache preflight hit.")
        return result
    except Exception:
        logger.exception("❌ ChromaDB cache preflight failed.")
        return None


def _run_agent(
    agent_executor,
    message: str,
    history_messages: list,
    model: str = "72b",
    hf_token: str | None = None,
    gemini_token: str | None = None,
) -> str:
    from src.callbacks import ContextCaptureCallback
    from src.tools.model_context import apply_thread_context

    # Apply user tokens + model to thread-local so tools (classify_query,
    # synthesize_findings, pdf_processor, compare_papers) can resolve tokens
    # via get_hf_token()/get_gemini_token() at runtime.
    apply_thread_context(model, hf_token, gemini_token)

    chat_history = _format_history(history_messages)
    callback = ContextCaptureCallback()

    kb_context = _preflight_kb(message)
    if _EXPLICIT_WEB_SEARCH.search(message):
        # Hard-wire web search — do not inject KB context, do not let agent reroute
        clean_query = _EXPLICIT_WEB_SEARCH.sub("", message).lstrip(" -–—:").strip()
        agent_input = (
            "[MANDATORY — WEB SEARCH ONLY]\n"
            "The user has explicitly requested a web search. You MUST:\n"
            "  1. Call web_search_tool with the query below.\n"
            "  2. Do NOT call search_arxiv_papers, search_semantic_scholar, search_pubmed, "
            "search_internal_knowledge, or any download tool.\n"
            "  3. Present the web results directly.\n\n"
            f"Web search query: {clean_query}"
        )
    else:
        agent_input = (
            f"[KNOWLEDGE BASE CONTEXT — papers already indexed locally:]\n{kb_context}\n\n{message}"
            if kb_context else message
        )

    result = agent_executor.invoke(
        {"input": agent_input, "chat_history": chat_history},
        config={"callbacks": [callback]},
    )
    answer: str = _normalize_agent_output(result["output"])

    if callback.answered_from_memory and _PAPER_QUERY.search(message):
        logger.warning("Agent answered from memory — retrying with forced tool use.")
        callback.reset()
        forced = (
            agent_input
            + "\n\n[SYSTEM OVERRIDE: You answered the previous turn without using any tools. "
            "That is not allowed. You MUST call search_arxiv_papers, search_semantic_scholar, "
            "or search_pubmed NOW before writing a Final Answer.]"
        )
        result = agent_executor.invoke(
            {"input": forced, "chat_history": chat_history},
            config={"callbacks": [callback]},
        )
        answer = _normalize_agent_output(result["output"])
        logger.info("Retry complete. Tools used: %s", callback.used_tools)

    violations = check_exclusion_violations(message, answer)
    if violations:
        logger.warning("Exclusion violation detected: %s", violations)
        answer += (
            "\n\n---\n"
            f"> ⚠️ **Auto-check:** This response may reference excluded topic(s): "
            f"**{', '.join(violations)}**. Please review the answer above carefully."
        )

    return answer


def _sync_db():
    from src.db.vector_store import sync_mongo_to_chroma
    sync_mongo_to_chroma()


def _run_agent_with(
    agent_executor,
    message: str,
    history_messages: list,
    model: str = "72b",
    extra_callback=None,
    hf_token: str | None = None,
    gemini_token: str | None = None,
) -> str:
    """Run a specific agent executor (for compare mode)."""
    from src.callbacks import ContextCaptureCallback
    from src.tools.model_context import apply_thread_context
    apply_thread_context(model, hf_token, gemini_token)
    chat_history = _format_history(history_messages)
    ctx_cb = ContextCaptureCallback()
    callbacks = [ctx_cb]
    if extra_callback is not None:
        callbacks.append(extra_callback)

    if extra_callback is not None and hasattr(extra_callback, "emit_cache_check_start"):
        extra_callback.emit_cache_check_start()
    kb_context = _preflight_kb(message)
    if extra_callback is not None and hasattr(extra_callback, "emit_cache_check_done"):
        extra_callback.emit_cache_check_done(bool(kb_context))
    if _EXPLICIT_WEB_SEARCH.search(message):
        clean_query = _EXPLICIT_WEB_SEARCH.sub("", message).lstrip(" -–—:").strip()
        agent_input = (
            "[MANDATORY — WEB SEARCH ONLY]\n"
            "The user has explicitly requested a web search. You MUST:\n"
            "  1. Call web_search_tool with the query below.\n"
            "  2. Do NOT call search_arxiv_papers, search_semantic_scholar, search_pubmed, "
            "search_internal_knowledge, or any download tool.\n"
            "  3. Present the web results directly.\n\n"
            f"Web search query: {clean_query}"
        )
    else:
        agent_input = (
            f"[KNOWLEDGE BASE CONTEXT — papers already indexed locally:]\n{kb_context}\n\n{message}"
            if kb_context else message
        )

    result = agent_executor.invoke(
        {"input": agent_input, "chat_history": chat_history},
        config={"callbacks": callbacks},
    )
    answer: str = _normalize_agent_output(result["output"])

    if ctx_cb.answered_from_memory and _PAPER_QUERY.search(message):
        logger.warning("[%s] Compare agent answered from memory — retrying with forced tool use.", model)
        ctx_cb.reset()
        forced = (
            agent_input
            + "\n\n[SYSTEM OVERRIDE: You answered without using any tools. "
            "You MUST call search_arxiv_papers, search_semantic_scholar, "
            "or search_pubmed NOW before writing a Final Answer.]"
        )
        result = agent_executor.invoke(
            {"input": forced, "chat_history": chat_history},
            config={"callbacks": callbacks},
        )
        answer = _normalize_agent_output(result["output"])

    violations = check_exclusion_violations(message, answer)
    if violations:
        answer += (
            "\n\n---\n"
            f"> ⚠️ **Auto-check:** Excluded topic(s): **{', '.join(violations)}**."
        )
    return answer


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.get("/api/auth/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return UserResponse(user_id=current_user["sub"], email=current_user["email"])


# ── OAuth endpoints ───────────────────────────────────────────────────────────

@app.get("/api/auth/google")
async def google_login():
    return RedirectResponse(google_auth_url())


@app.get("/api/auth/google/callback")
async def google_callback(code: str):
    try:
        user_info = await google_get_user(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {e}")
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google.")
    user = get_or_create_oauth_user(email, "google")
    token = create_token(user["user_id"], user["email"])
    return RedirectResponse(f"{FRONTEND_URL}?token={token}")


@app.get("/api/auth/github")
async def github_login():
    return RedirectResponse(github_auth_url())


@app.get("/api/auth/github/callback")
async def github_callback(code: str):
    try:
        user_info = await github_get_user(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub OAuth failed: {e}")
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from GitHub. Make sure your GitHub account has a public or verified email.")
    user = get_or_create_oauth_user(email, "github")
    token = create_token(user["user_id"], user["email"])
    return RedirectResponse(f"{FRONTEND_URL}?token={token}")


# ── Session endpoints ─────────────────────────────────────────────────────────

@app.get("/api/sessions", response_model=List[SessionMeta])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    return get_sessions_by_user(current_user["sub"])


@app.post("/api/sessions", response_model=SessionMeta, status_code=201)
async def new_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    session_id = create_session(current_user["sub"], body.title)
    session = get_session(session_id, current_user["sub"])
    return session


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_session(session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@app.delete("/api/sessions/{session_id}", status_code=204)
async def remove_session(session_id: str, current_user: dict = Depends(get_current_user)):
    deleted = delete_session(session_id, current_user["sub"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return Response(status_code=204)


# ── Compare session endpoints ─────────────────────────────────────────────────

@app.get("/api/compare/sessions", response_model=List[CompareSessionMeta])
async def list_compare_sessions(current_user: dict = Depends(get_current_user)):
    return get_compare_sessions_by_user(current_user["sub"])


@app.post("/api/compare/sessions", response_model=CompareSessionMeta, status_code=201)
async def new_compare_session(body: CompareSessionCreate, current_user: dict = Depends(get_current_user)):
    session_id = create_compare_session(current_user["sub"], body.title)
    session = get_compare_session(session_id, current_user["sub"])
    return session


@app.get("/api/compare/sessions/{session_id}", response_model=CompareSessionDetail)
async def get_compare_session_detail(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_compare_session(session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Comparison session not found.")
    return session


@app.delete("/api/compare/sessions/{session_id}", status_code=204)
async def remove_compare_session(session_id: str, current_user: dict = Depends(get_current_user)):
    deleted = delete_compare_session(session_id, current_user["sub"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Comparison session not found.")
    return Response(status_code=204)


@app.post("/api/compare/chat", response_model=CompareResponse)
async def compare_chat(req: CompareRequest, current_user: dict = Depends(get_current_user)):
    session = get_compare_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Comparison session not found.")

    # Lazy init compare agents
    try:
        await _ensure_compare_agents()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to load compare agents: {e}")

    # Pre-flight guardrail
    limit_refusal = request_limit_check(req.message)
    if limit_refusal:
        responses = {"qwen7b": limit_refusal, "qwen72b": limit_refusal, "gemini": limit_refusal}
        timings = {"qwen7b": 0.0, "qwen72b": 0.0, "gemini": 0.0}
        append_compare_turn(req.session_id, req.message, responses, timings)
        return CompareResponse(responses=responses, timings=timings)

    refusal = shield_check(req.message)
    if refusal:
        responses = {"qwen7b": refusal, "qwen72b": refusal, "gemini": refusal}
        timings = {"qwen7b": 0.0, "qwen72b": 0.0, "gemini": 0.0}
        append_compare_turn(req.session_id, req.message, responses, timings)
        return CompareResponse(responses=responses, timings=timings)

    # Update title on first turn
    if not session["turns"]:
        title = req.message[:48] + ("…" if len(req.message) > 48 else "")
        update_compare_session_title(req.session_id, title)

    def _history_for(model_key: str) -> list[dict]:
        history: list[dict] = []
        for turn in session["turns"]:
            history.append({"role": "user", "content": turn["user_message"]})
            history.append({"role": "assistant", "content": turn["responses"].get(model_key, "")})
        return history

    loop = asyncio.get_event_loop()
    import time as _time

    async def _run(agent_exec, label: str, model: str, model_key: str):
        t0 = _time.monotonic()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(_executor, _run_agent_with, agent_exec, req.message, _history_for(model_key), model),
                timeout=_COMPARE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            result = f"*{label} timed out after {_COMPARE_TIMEOUT_SECONDS}s.*"
        except Exception as e:
            result = f"*{label} error: {e}*"
        elapsed = round(_time.monotonic() - t0, 1)
        return result, elapsed

    (r7b, t7b), (r72b, t72b), (rg, tg) = await asyncio.gather(
        _run(_agent_7b, "Qwen 7B", "7b", "qwen7b"),
        _run(_agent, "Qwen 72B", "72b", "qwen72b"),
        _run(_agent_gemini, "Gemini Flash", "gemini-flash", "gemini"),
    )

    responses = {"qwen7b": r7b, "qwen72b": r72b, "gemini": rg}
    timings = {"qwen7b": t7b, "qwen72b": t72b, "gemini": tg}
    append_compare_turn(req.session_id, req.message, responses, timings)
    loop.run_in_executor(_executor, _sync_db)

    return CompareResponse(responses=responses, timings=timings)


@app.post("/api/compare/stream/{model_key}")
async def compare_stream_endpoint(
    model_key: str,
    req: CompareStreamRequest,
    current_user: dict = Depends(get_current_user),
):
    """SSE endpoint — streams tool events then final response for one model."""
    model_key = _validate_model_key(model_key)
    model_name = _resolve_model(model_key)
    cmp_hf_token = req.hf_token or None
    cmp_gemini_token = req.gemini_token or None
    try:
        agent_exec = await _get_agent_for_request(model_name, cmp_hf_token, cmp_gemini_token)
    except Exception as e:
        _err_msg = str(e)
        async def _err():
            yield f"data: {_json.dumps({'type': 'error', 'message': _err_msg})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    session = get_compare_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    refusal = shield_check(req.message)
    if refusal:
        async def _refused():
            yield f"data: {_json.dumps({'type': 'done', 'response': refusal, 'timing': 0.0})}\n\n"
        return StreamingResponse(_refused(), media_type="text/event-stream")

    limit_refusal = request_limit_check(req.message)
    if limit_refusal:
        async def _limited():
            yield f"data: {_json.dumps({'type': 'done', 'response': limit_refusal, 'timing': 0.0})}\n\n"
        return StreamingResponse(_limited(), media_type="text/event-stream")

    history: list[dict] = []
    for turn in session["turns"]:
        history.append({"role": "user", "content": turn["user_message"]})
        history.append({"role": "assistant", "content": turn["responses"].get(model_key, "")})

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    async def generate():
        import time as _time
        import functools
        from src.callbacks import StreamingCallback
        t0 = _time.monotonic()
        cb = StreamingCallback(queue, loop)

        def _run_with_tokens():
            from src.tools.model_context import apply_thread_context
            apply_thread_context(model_name, cmp_hf_token, cmp_gemini_token)
            return _run_agent_with(
                agent_exec, req.message, history, model_name, cb,
                hf_token=cmp_hf_token, gemini_token=cmp_gemini_token,
            )

        future = loop.run_in_executor(_executor, _run_with_tokens)

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.3)
                yield f"data: {event}\n\n"
            except asyncio.TimeoutError:
                if future.done():
                    break
                yield ": keepalive\n\n"

        elapsed = round(_time.monotonic() - t0, 1)
        try:
            result = future.result()
            yield f"data: {_json.dumps({'type': 'done', 'response': result, 'timing': elapsed})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(exc), 'timing': elapsed})}\n\n"
        finally:
            # Sync any newly downloaded papers into ChromaDB
            loop.run_in_executor(_executor, _sync_db)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/compare/sessions/{session_id}/turns", status_code=201)
async def save_compare_turn_endpoint(
    session_id: str,
    body: CompareTurnSave,
    current_user: dict = Depends(get_current_user),
):
    session = get_compare_session(session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session["turns"]:
        title = body.user_message[:48] + ("…" if len(body.user_message) > 48 else "")
        update_compare_session_title(session_id, title)
    append_compare_turn(session_id, body.user_message, body.responses, body.timings)
    return {"ok": True}


# ── Chat stream endpoint ──────────────────────────────────────────────────────

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """SSE version of /api/chat — streams tool events then the final response."""
    model_key = _validate_model_key(req.model_key)
    model_name = _resolve_model(model_key)

    session = get_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    refusal = shield_check(req.message)
    if refusal:
        append_message(req.session_id, "user", req.message)
        append_message(req.session_id, "assistant", refusal)
        async def _refused():
            yield f"data: {_json.dumps({'type': 'done', 'response': refusal})}\n\n"
        return StreamingResponse(_refused(), media_type="text/event-stream")

    limit_refusal = request_limit_check(req.message)
    if limit_refusal:
        append_message(req.session_id, "user", req.message)
        append_message(req.session_id, "assistant", limit_refusal)
        async def _limited():
            yield f"data: {_json.dumps({'type': 'done', 'response': limit_refusal})}\n\n"
        return StreamingResponse(_limited(), media_type="text/event-stream")

    user_hf_token = req.hf_token or None
    user_gemini_token = req.gemini_token or None
    try:
        agent_exec = await _get_agent_for_request(model_name, user_hf_token, user_gemini_token)
    except Exception as e:
        _err = str(e)
        async def _agent_error():
            yield f"data: {_json.dumps({'type': 'error', 'message': _err})}\n\n"
        return StreamingResponse(_agent_error(), media_type="text/event-stream")

    append_message(req.session_id, "user", req.message)

    if not session["messages"]:
        title = req.message[:48] + ("…" if len(req.message) > 48 else "")
        update_session_title(req.session_id, title)

    history = session["messages"]
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    async def generate():
        import time as _time
        from src.callbacks import StreamingCallback, ContextCaptureCallback
        t0 = _time.monotonic()

        stream_cb = StreamingCallback(queue, loop)
        ctx_cb = ContextCaptureCallback()

        def _run():
            from src.tools.model_context import apply_thread_context
            apply_thread_context(model_name, user_hf_token, user_gemini_token)
            chat_history = _format_history(history)

            stream_cb.emit_cache_check_start()
            kb_context = _preflight_kb(req.message)
            stream_cb.emit_cache_check_done(bool(kb_context))
            if _EXPLICIT_WEB_SEARCH.search(req.message):
                clean_query = _EXPLICIT_WEB_SEARCH.sub("", req.message).lstrip(" -–—:").strip()
                agent_input = (
                    "[MANDATORY — WEB SEARCH ONLY]\n"
                    "The user has explicitly requested a web search. You MUST:\n"
                    "  1. Call web_search_tool with the query below.\n"
                    "  2. Do NOT call search_arxiv_papers, search_semantic_scholar, search_pubmed, "
                    "search_internal_knowledge, or any download tool.\n"
                    "  3. Present the web results directly.\n\n"
                    f"Web search query: {clean_query}"
                )
            else:
                agent_input = (
                    f"[KNOWLEDGE BASE CONTEXT — papers already indexed locally:]\n{kb_context}\n\n{req.message}"
                    if kb_context else req.message
                )

            result = agent_exec.invoke(
                {"input": agent_input, "chat_history": chat_history},
                config={"callbacks": [ctx_cb, stream_cb]},
            )
            answer: str = _normalize_agent_output(result["output"])

            if ctx_cb.answered_from_memory and _PAPER_QUERY.search(req.message):
                forced = (
                    agent_input
                    + "\n\n[SYSTEM OVERRIDE: You answered without using any tools. "
                    "You MUST call search_arxiv_papers, search_semantic_scholar, "
                    "or search_pubmed NOW before writing a Final Answer.]"
                )
                result = agent_exec.invoke(
                    {"input": forced, "chat_history": chat_history},
                    config={"callbacks": [ctx_cb, stream_cb]},
                )
                answer = _normalize_agent_output(result["output"])

            violations = check_exclusion_violations(req.message, answer)
            if violations:
                answer += (
                    "\n\n---\n"
                    f"> ⚠️ **Auto-check:** Excluded topic(s): **{', '.join(violations)}**."
                )
            return answer

        future = loop.run_in_executor(_executor, _run)

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.3)
                yield f"data: {event}\n\n"
            except asyncio.TimeoutError:
                if future.done():
                    break
                yield ": keepalive\n\n"

        try:
            response = future.result()
        except asyncio.TimeoutError:
            response = "Query took too long. Try asking about one paper at a time."
        except Exception as exc:
            logger.error("Agent stream error: %s", exc)
            response = f"Error: {exc}"

        _ITER_LIMIT_MSGS = (
            "agent stopped due to iteration limit",
            "agent stopped due to time limit",
        )
        if any(m in response.lower() for m in _ITER_LIMIT_MSGS):
            response = (
                "I wasn't able to find that paper after exhausting my search steps. "
                "It may not be indexed on arXiv. Try rephrasing the title, providing the arXiv ID directly, "
                "or ask me to search Semantic Scholar or the web instead."
            )

        append_message(req.session_id, "assistant", response)
        loop.run_in_executor(_executor, _sync_db)
        yield f"data: {_json.dumps({'type': 'done', 'response': response})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent_ready": _startup_ready,
        "loaded_models": sorted(MODEL_NAME_TO_KEY.get(model, model) for model in _agents),
    }


@app.get("/api/models/status")
async def models_status():
    def _check_ollama():
        import os as _os
        import requests as _req
        local_url = _os.getenv("LOCAL_72B_BASE_URL", "http://localhost:8002/v1")
        health_url = local_url.rstrip("/v1").rstrip("/") + "/health"
        try:
            resp = _req.get(health_url, timeout=2)
            return resp.status_code == 200
        except Exception:
            pass
        # fallback: try Ollama
        try:
            resp = _req.get("http://localhost:11434/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    loop = asyncio.get_event_loop()
    local_available = await loop.run_in_executor(_executor, _check_ollama)
    return {"local_72b_available": local_available}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    model_key = _validate_model_key(req.model_key)
    model_name = _resolve_model(model_key)

    # Verify the session belongs to the current user
    session = get_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Pre-flight guardrail check
    refusal = shield_check(req.message)
    if refusal:
        logger.info("Guardrail triggered: %.80s", req.message)
        append_message(req.session_id, "user", req.message)
        append_message(req.session_id, "assistant", refusal)
        return ChatResponse(response=refusal)

    limit_refusal = request_limit_check(req.message)
    if limit_refusal:
        logger.info("Request limit triggered: %.80s", req.message)
        append_message(req.session_id, "user", req.message)
        append_message(req.session_id, "assistant", limit_refusal)
        return ChatResponse(response=limit_refusal)

    user_hf_token = req.hf_token or None
    user_gemini_token = req.gemini_token or None
    try:
        agent_exec = await _get_agent_for_request(model_name, user_hf_token, user_gemini_token)
    except Exception as e:
        logger.error("Agent load error for %s: %s", model_name, e)
        raise HTTPException(status_code=503, detail=str(e))

    # Save user message before running the agent
    append_message(req.session_id, "user", req.message)

    # Update session title on first message
    if not session["messages"]:
        title = req.message[:48] + ("…" if len(req.message) > 48 else "")
        update_session_title(req.session_id, title)

    loop = asyncio.get_event_loop()
    try:
        import functools
        fn = functools.partial(
            _run_agent, agent_exec, req.message, session["messages"], model_name,
            hf_token=user_hf_token, gemini_token=user_gemini_token,
        )
        future = loop.run_in_executor(_executor, fn)
        response = await asyncio.wait_for(future, timeout=_AGENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query took too long. Try asking about one paper at a time.")
    except Exception as e:
        logger.error("Agent error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    # Save assistant response
    append_message(req.session_id, "assistant", response)

    # Background DB sync
    loop.run_in_executor(_executor, _sync_db)

    return ChatResponse(response=response)
