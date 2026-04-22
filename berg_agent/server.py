import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List

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
from src.auth.password import hash_password, verify_password
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_PAPER_QUERY = re.compile(
    r'\b(paper|papers|research|study|studies|find|search|recent|published|tell me about)\b', re.I
)

# ── Agent singletons ──────────────────────────────────────────────────────────

_agent = None        # Qwen 72B (startup)
_agent_7b = None     # Qwen 7B  (lazy)
_agent_gemini = None # Gemini   (lazy)
_compare_init_lock = asyncio.Lock()

_executor = ThreadPoolExecutor(max_workers=4)
_AGENT_TIMEOUT_SECONDS = 600
_COMPARE_TIMEOUT_SECONDS = 600


def _init_agent():
    from src.db.vector_store import sync_mongo_to_chroma
    from src.agent import get_research_agent
    logger.info("Syncing MongoDB → ChromaDB …")
    sync_mongo_to_chroma()
    logger.info("Loading Qwen 72B agent …")
    return get_research_agent("72b")


def _init_compare_agents():
    from src.agent import get_research_agent
    agents = {}
    logger.info("Loading Qwen 7B agent …")
    agents["7b"] = get_research_agent("7b")
    logger.info("Loading Gemini Flash agent …")
    agents["gemini"] = get_research_agent("gemini-flash")
    return agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    loop = asyncio.get_event_loop()
    _agent = await loop.run_in_executor(_executor, _init_agent)
    logger.info("✅ Berg Agent ready.")
    yield
    _executor.shutdown(wait=False)


async def _ensure_compare_agents():
    """Lazy-initialize 7B and Gemini agents on first compare request."""
    global _agent_7b, _agent_gemini
    if _agent_7b is not None and _agent_gemini is not None:
        return
    async with _compare_init_lock:
        if _agent_7b is not None and _agent_gemini is not None:
            return
        loop = asyncio.get_event_loop()
        agents = await loop.run_in_executor(_executor, _init_compare_agents)
        _agent_7b = agents["7b"]
        _agent_gemini = agents["gemini"]
        logger.info("✅ Compare agents ready (7B + Gemini).")


app = FastAPI(title="Berg Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

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

class CompareTurnSave(BaseModel):
    user_message: str
    responses: dict
    timings: dict


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_history(messages: list) -> str:
    if not messages:
        return ""
    lines = []
    for msg in messages:
        prefix = "Human" if msg["role"] == "user" else "AI"
        lines.append(f"{prefix}: {msg['content']}")
    return "\n".join(lines)


def _run_agent(message: str, history_messages: list) -> str:
    from src.evaluation.callback import ContextCaptureCallback

    chat_history = _format_history(history_messages)
    callback = ContextCaptureCallback()

    result = _agent.invoke(
        {"input": message, "chat_history": chat_history},
        config={"callbacks": [callback]},
    )
    answer: str = result["output"]

    if callback.answered_from_memory and _PAPER_QUERY.search(message):
        logger.warning("Agent answered from memory — retrying with forced tool use.")
        callback.reset()
        forced = (
            message
            + "\n\n[SYSTEM OVERRIDE: You answered the previous turn without using any tools. "
            "That is not allowed. You MUST call search_arxiv_papers, search_semantic_scholar, "
            "or search_pubmed NOW before writing a Final Answer.]"
        )
        result = _agent.invoke(
            {"input": forced, "chat_history": chat_history},
            config={"callbacks": [callback]},
        )
        answer = result["output"]
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


def _run_agent_with(agent_executor, message: str, history_messages: list, extra_callback=None) -> str:
    """Run a specific agent executor (for compare mode)."""
    from src.evaluation.callback import ContextCaptureCallback
    chat_history = _format_history(history_messages)
    callbacks = [ContextCaptureCallback()]
    if extra_callback is not None:
        callbacks.append(extra_callback)
    result = agent_executor.invoke(
        {"input": message, "chat_history": chat_history},
        config={"callbacks": callbacks},
    )
    answer: str = result["output"]
    violations = check_exclusion_violations(message, answer)
    if violations:
        answer += (
            "\n\n---\n"
            f"> ⚠️ **Auto-check:** Excluded topic(s): **{', '.join(violations)}**."
        )
    return answer


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = create_user(req.email, hash_password(req.password))
    token = create_token(user["user_id"], user["email"])
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_token(user["user_id"], user["email"])
    return TokenResponse(access_token=token)


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
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent is still initialising, please retry.")

    session = get_compare_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Comparison session not found.")

    # Lazy init compare agents
    try:
        await _ensure_compare_agents()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to load compare agents: {e}")

    # Pre-flight guardrail
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

    # Build history from previous turns
    history: list[dict] = []
    for turn in session["turns"]:
        history.append({"role": "user", "content": turn["user_message"]})
        history.append({"role": "assistant", "content": turn["responses"].get("qwen72b", "")})

    loop = asyncio.get_event_loop()
    import time as _time

    async def _run(agent_exec, label: str):
        t0 = _time.monotonic()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(_executor, _run_agent_with, agent_exec, req.message, history),
                timeout=_COMPARE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            result = f"*{label} timed out after {_COMPARE_TIMEOUT_SECONDS}s.*"
        except Exception as e:
            result = f"*{label} error: {e}*"
        elapsed = round(_time.monotonic() - t0, 1)
        return result, elapsed

    (r7b, t7b), (r72b, t72b), (rg, tg) = await asyncio.gather(
        _run(_agent_7b, "Qwen 7B"),
        _run(_agent, "Qwen 72B"),
        _run(_agent_gemini, "Gemini Flash"),
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
    _MODEL_MAP = {"qwen7b": lambda: _agent_7b, "qwen72b": lambda: _agent, "gemini": lambda: _agent_gemini}
    if model_key not in _MODEL_MAP:
        raise HTTPException(status_code=400, detail="Unknown model key.")

    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not ready.")

    if model_key in ("qwen7b", "gemini"):
        try:
            await _ensure_compare_agents()
        except Exception as e:
            async def _err():
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return StreamingResponse(_err(), media_type="text/event-stream")

    agent_exec = _MODEL_MAP[model_key]()
    if agent_exec is None:
        async def _not_ready():
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Agent not initialised.'})}\n\n"
        return StreamingResponse(_not_ready(), media_type="text/event-stream")

    session = get_compare_session(req.session_id, current_user["sub"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    refusal = shield_check(req.message)
    if refusal:
        async def _refused():
            yield f"data: {_json.dumps({'type': 'done', 'response': refusal, 'timing': 0.0})}\n\n"
        return StreamingResponse(_refused(), media_type="text/event-stream")

    history: list[dict] = []
    for turn in session["turns"]:
        history.append({"role": "user", "content": turn["user_message"]})
        history.append({"role": "assistant", "content": turn["responses"].get(model_key, "")})

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    async def generate():
        import time as _time
        from src.evaluation.callback import StreamingCallback
        t0 = _time.monotonic()
        cb = StreamingCallback(queue, loop)

        future = loop.run_in_executor(
            _executor, _run_agent_with, agent_exec, req.message, history, cb
        )

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


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "agent_ready": _agent is not None}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent is still initialising, please retry.")

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

    # Save user message before running the agent
    append_message(req.session_id, "user", req.message)

    # Update session title on first message
    if not session["messages"]:
        title = req.message[:48] + ("…" if len(req.message) > 48 else "")
        update_session_title(req.session_id, title)

    loop = asyncio.get_event_loop()
    try:
        future = loop.run_in_executor(
            _executor, _run_agent, req.message, session["messages"]
        )
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
