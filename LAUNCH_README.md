# Researchy Berg — Launch Guide

Quick-start instructions to get the full-stack app running locally.

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| MongoDB | local or Atlas | Free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas) |

---

## 1 · Clone & Enter the Repo

```bash
git clone https://github.com/prateek-d/researchy_qwen.git
cd researchy_qwen
```

---

## 2 · Backend Setup (`berg_agent/`)

### 2a · Create a Python virtual environment

```bash
cd berg_agent
python3 -m venv .nlp
source .nlp/bin/activate        # macOS / Linux
# .nlp\Scripts\activate          # Windows
```

### 2b · Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2c · Create the `.env` file

Create `berg_agent/.env` with the following — only `MONGO_URI`, `JWT_SECRET`, and the OAuth credentials are required. API keys for HuggingFace and Gemini can be left blank and entered in the UI instead.

```env
# ── Database (required) ────────────────────────────────────
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?appName=YourApp
# or local: mongodb://localhost:27017/research_agent_db

# ── Auth (required) ────────────────────────────────────────
JWT_SECRET=any_random_64_char_hex_string
# Generate one: openssl rand -hex 32

# ── OAuth (required for Google / GitHub login) ─────────────
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret

# ── URLs ───────────────────────────────────────────────────
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

# ── LLM API keys (optional — can be entered in the UI) ─────
# HF_TOKEN=hf_...          # HuggingFace — powers Qwen 7B and 72B
# GOOGLE_API_KEY=AIza...   # Google AI Studio — powers Gemini 2.5 Flash
```

> **Where to get each key:**
>
> | Variable | Where to get it |
> |----------|----------------|
> | `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — create a read token |
> | `GOOGLE_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
> | `MONGO_URI` | MongoDB Atlas → Connect → Drivers → copy connection string |
> | `JWT_SECRET` | Run `openssl rand -hex 32` in your terminal |
> | `GOOGLE_CLIENT_ID/SECRET` | [console.cloud.google.com](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth 2.0 |
> | `GITHUB_CLIENT_ID/SECRET` | [github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps → New |

### 2d · Start the backend

```bash
# from inside berg_agent/ with .nlp activated
uvicorn server:app --reload
```

You should see:

```
INFO:server:Syncing MongoDB → ChromaDB …
INFO:server:✅ Berg Agent ready.
INFO:     Application startup complete.
```

> Wait for `✅ Berg Agent ready` before sending any queries — the first start downloads the embedding model and syncs the vector store.

---

## 3 · Frontend Setup (`client/`)

Open a **new terminal** (keep the backend running).

```bash
cd client
npm install
npm run dev
```

The frontend starts on **http://localhost:5173**.

---

## 4 · Using the App

1. Sign in with **Google** or **GitHub** via OAuth.
2. Click the **Keys** button (top right of chat) and enter your **HuggingFace token** and/or **Gemini API key**. Keys are saved in your browser and persist across refreshes.
3. Select a model from the dropdown (Qwen 7B, Qwen 72B, Gemini 2.5 Flash, or Local 72B).
4. **Normal Chat** — click **+ New conversation** and ask a research question.
5. **Compare Models** — click **Compare Models** in the sidebar to run all three models side-by-side on the same question.

> **Which key do I need?**
> - Qwen 7B / Qwen 72B → HuggingFace token
> - Gemini 2.5 Flash → Google API key
> - Local 72B → no key needed (requires local vLLM / Ollama server)

---

## 5 · Local LLM (Optional)

To run Qwen 72B locally instead of via HuggingFace:

**Requirements:** GPU with at least 40 GB VRAM

```bash
# Install vLLM
pip install vllm

# Start the local server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --port 8002 \
  --tensor-parallel-size 2
```

Add to `.env`:

```env
LOCAL_72B_BASE_URL=http://localhost:8002/v1
LOCAL_72B_MODEL=Qwen/Qwen2.5-72B-Instruct
```

Then select **Local 72B** from the model dropdown — no API key required.

---

## MongoDB Collections

The app auto-creates these collections in the `research_agent_db` database:

| Collection | Purpose |
|------------|---------|
| `users` | User accounts (OAuth) |
| `papers` | Downloaded and indexed papers (shared across all users) |
| `chat_sessions` | Normal chat conversations per user |
| `compare_sessions` | Compare-mode conversations per user |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Agent is still initialising` | Wait ~30s on first start; check terminal for errors |
| HuggingFace 429 / quota error | Free monthly credits exhausted — resets next billing cycle |
| `QWEN_7B_API_KEY or HF_TOKEN not set` | Enter your HuggingFace token in the UI Keys modal |
| `GEMINI_API_KEY or GOOGLE_API_KEY not set` | Enter your Gemini key in the UI Keys modal |
| OAuth redirect fails | Ensure `BACKEND_URL` / `FRONTEND_URL` match your ports and OAuth redirect URIs are configured in Google / GitHub |
| `ModuleNotFoundError` | Virtual environment not activated — run `source .nlp/bin/activate` |
| Frontend shows blank page | Backend must be running on port 8000 |
| Compare view shows nothing | Check browser console for CORS or 503 errors |

---

## Project Structure

```
researchy_qwen/
├── berg_agent/                 # Backend (FastAPI + LangChain)
│   ├── server.py               # Main API server + streaming SSE
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Environment variables (create this)
│   └── src/
│       ├── agent.py            # AgentExecutor — 16 tools + prompt
│       ├── auth/               # JWT, bcrypt, Google + GitHub OAuth
│       ├── db/                 # MongoDB CRUD + ChromaDB vector store
│       ├── guardrails/         # Prompt shield, exclusions, request limits
│       ├── prompt/             # Modular prompt sections + builder
│       └── tools/              # Search, download, RAG, compare, synthesize
└── client/                     # Frontend (React + Vite + Tailwind)
    ├── src/
    │   ├── App.tsx             # Main app + token/model state
    │   ├── components/         # ChatArea, CompareView, Sidebar, ChatInput
    │   ├── contexts/           # AuthContext (OAuth token handling)
    │   ├── lib/                # API client
    │   └── pages/              # LoginPage (Google + GitHub only)
    └── utils/backgrounds/      # Background images
```
