# 🚀 Researchy Berg — Launch Guide

Quick-start instructions to get the full-stack app running locally.

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| MongoDB Atlas | — | Free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas) |

---

## 1 · Clone & Enter the Repo

```bash
git clone <your-repo-url>
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

Create `berg_agent/.env` with the following variables:

```env
# ── LLM Providers ─────────────────────────────────────────
HF_TOKEN=your_huggingface_token            # HuggingFace — powers Qwen 72B
GOOGLE_API_KEY=your_google_api_key         # Google AI — powers Gemini 2.5 Flash
OPEN_ROUTER_API_KEY=your_openrouter_key    # OpenRouter — powers Qwen 7B

# ── Database ──────────────────────────────────────────────
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?appName=YourApp

# ── Auth ──────────────────────────────────────────────────
JWT_SECRET=any_random_64_char_hex_string   # e.g. openssl rand -hex 32

# ── OAuth (optional — only needed for Google/GitHub login) ─
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret

# ── URLs ──────────────────────────────────────────────────
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

> **Where to get each key:**
>
> | Variable | Where to get it |
> |----------|----------------|
> | `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — create a read token |
> | `GOOGLE_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
> | `OPEN_ROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
> | `MONGO_URI` | MongoDB Atlas → Connect → Drivers → copy connection string |
> | `JWT_SECRET` | Run `openssl rand -hex 32` in your terminal |
> | `GOOGLE_CLIENT_ID/SECRET` | [console.cloud.google.com](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth 2.0 |
> | `GITHUB_CLIENT_ID/SECRET` | [github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps → New |

### 2d · Start the Backend

```bash
uvicorn server:app --reload
```

The server starts on **http://localhost:8000**. You'll see logs like:

```
INFO:server:Syncing MongoDB → ChromaDB …
INFO:server:Loading Qwen 72B agent …
INFO:server:✅ Berg Agent ready.
INFO:     Application startup complete.
```

> Wait for `✅ Berg Agent ready` before using the app — the first start downloads the embedding model and syncs the vector store.

---

## 3 · Frontend Setup (`client/`)

Open a **new terminal** (keep the backend running).

```bash
cd client
npm install
npm run dev
```

The frontend starts on **http://localhost:5173**. Open it in your browser.

---

## 4 · Using the App

1. **Register** with email + password, or click **Google** / **GitHub** to sign in via OAuth.
2. **Normal Chat** — click **+ New conversation**, type a research question, and Berg will search arXiv/Semantic Scholar/PubMed.
3. **Compare Models** — click **Compare Models** in the sidebar. All three models (Qwen 7B, Qwen 72B, Gemini 2.5 Flash) answer side-by-side.

---

## MongoDB Collections

The app auto-creates these collections in your `research_agent_db` database:

| Collection | Purpose |
|------------|---------|
| `users` | Registered user accounts |
| `papers` | Downloaded/indexed papers (shared across users) |
| `chat_sessions` | Normal chat conversations per user |
| `compare_sessions` | Compare-mode conversations per user |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Agent is still initialising` | Wait ~30s for startup to finish; check terminal for errors |
| HuggingFace 429 / quota error | Monthly free credits exhausted — resets next billing cycle |
| OAuth redirect fails | Make sure `BACKEND_URL` and `FRONTEND_URL` match your ports, and OAuth redirect URIs are configured in Google/GitHub |
| `ModuleNotFoundError` | Make sure the venv is activated: `source .nlp/bin/activate` |
| Frontend shows blank | Ensure backend is running on port 8000 — the frontend expects `http://localhost:8000` |
| Compare view shows nothing | Backend must be running; check browser console for CORS or 503 errors |

---

## Project Structure

```
researchy_qwen/
├── berg_agent/                 # Backend (FastAPI + LangChain)
│   ├── server.py               #   Main API server
│   ├── requirements.txt        #   Python dependencies
│   ├── .env                    #   Environment variables (create this)
│   ├── chroma_db/              #   Local vector store (auto-generated)
│   └── src/
│       ├── agent.py            #   ReAct agent setup
│       ├── auth/               #   JWT, OAuth, passwords
│       ├── db/                 #   MongoDB client + vector store sync
│       ├── evaluation/         #   RAGAS eval + streaming callbacks
│       ├── guardrails/         #   Prompt shield + exclusion checking
│       ├── prompt/             #   Modular prompt sections + builder
│       └── tools/              #   11 research tools + LLM setup
└── client/                     # Frontend (React + Vite + Tailwind)
    ├── package.json
    ├── src/
    │   ├── App.tsx             #   Main app + state management
    │   ├── components/         #   ChatArea, CompareView, Sidebar, etc.
    │   ├── contexts/           #   AuthContext
    │   ├── lib/                #   API client
    │   └── pages/              #   LoginPage
    └── utils/backgrounds/      #   Background images
```
