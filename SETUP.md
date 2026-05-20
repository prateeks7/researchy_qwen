# Berg Agent — Setup Guide

A multi-model AI research assistant that searches, downloads, and summarises academic papers from arXiv, Semantic Scholar, and PubMed.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | Tested on 3.10 |
| Node.js | 18+ | For the React frontend |
| MongoDB | 6+ | Local or Atlas (free tier works) |
| Git | any | — |

---

## 1. Clone the repo

```bash
git clone <your-repo-url>
cd researchy_qwen
```

---

## 2. Backend setup

### 2a. Create and activate a virtual environment

```bash
cd berg_agent
python3 -m venv .nlp
source .nlp/bin/activate        # Linux/Mac
# .nlp\Scripts\activate         # Windows
```

### 2b. Install dependencies

```bash
pip install -r requirements.txt
```

### 2c. Create the `.env` file

Copy the template below into `berg_agent/.env` and fill in your keys:

```env
# ── Required ─────────────────────────────────────────────────

# HuggingFace token — used for Qwen 72B and Qwen 7B via HF Inference Router
# Get one at https://huggingface.co/settings/tokens (read access is enough)
HF_TOKEN=hf_...

# MongoDB connection string
# Local:  mongodb://localhost:27017/berg_agent
# Atlas:  mongodb+srv://<user>:<pass>@cluster.mongodb.net/berg_agent
MONGO_URI=mongodb://localhost:27017/berg_agent

# JWT secret — any long random string (used to sign auth tokens)
# Generate one: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=your_random_secret_here

# Google Gemini API key — used for Gemini 2.5 Flash in compare mode
# Get one at https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=AIza...

# ── URLs (update if not running locally) ─────────────────────
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

# ── Optional: OAuth login (leave blank to disable) ───────────
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# ── Optional: model overrides (defaults shown) ───────────────
# QWEN_72B_MODEL=Qwen/Qwen2.5-72B-Instruct
# QWEN_72B_BASE_URL=https://router.huggingface.co/v1
# QWEN_7B_MODEL=Qwen/Qwen2.5-7B-Instruct
# QWEN_7B_BASE_URL=https://router.huggingface.co/v1
# GEMINI_MODEL=gemini-2.5-flash
```

> **Note:** `FIREWORKS_API_KEY` and `OPEN_ROUTER_API_KEY` in the `.env` are legacy — they are not used by the current codebase and can be left blank or removed.

### 2d. Start the backend

```bash
# From inside berg_agent/ with .nlp activated
uvicorn server:app --reload --port 8000
```

You should see:
```
🔄 Syncing MongoDB papers to Vector Database...
⚡ Vector Database is already up to date with MongoDB.
✅ Berg Agent ready.
INFO: Application startup complete.
```

---

## 3. Frontend setup

```bash
cd ../client
npm install
npm run dev
```

The app will be available at **http://localhost:5173**

---

## 4. First run

1. Open http://localhost:5173
2. Register an account (email + password)
3. Click the **Keys** button (top right of chat) and enter your **HuggingFace token**
4. Select **Qwen 72B** as your model and ask a research question

> The first query will be slow (~10–30s) while the agent initialises and the HuggingFace model warms up.

---

## 5. Compare mode

The compare view runs Qwen 7B, Qwen 72B, and Gemini 2.5 Flash in parallel.

1. Switch to the **Compare** tab in the sidebar
2. Click **Keys** and enter:
   - **HuggingFace token** — for both Qwen models
   - **Gemini API key** — for Gemini 2.5 Flash
3. Send a research question

---

## 6. Local LLM (Optional)

If you want to run Qwen 72B locally using vLLM instead of HuggingFace's API:

### Requirements
- A GPU with at least 40 GB VRAM (e.g. 2× A100 40GB or 1× A100 80GB)
- vLLM installed: `pip install vllm`

### Start the local vLLM server

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --port 8002 \
  --tensor-parallel-size 2   # adjust to your GPU count
```

### Configure `.env` to use local server

```env
LOCAL_72B_BASE_URL=http://localhost:8002/v1
LOCAL_72B_MODEL=Qwen/Qwen2.5-72B-Instruct
```

### Switch to local model in the UI

Select **Local 72B** from the model dropdown. No API key is required — the local server handles everything. HuggingFace token is only needed when using the HF-hosted models.

---

## 7. MongoDB setup (if running locally)

```bash
# Install MongoDB (Ubuntu)
sudo apt install mongodb
sudo systemctl start mongodb

# Or use Docker
docker run -d -p 27017:27017 --name mongo mongo:6
```

No schema setup needed — collections are created automatically on first use.

---

## 8. Environment variable reference

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_TOKEN` | Yes (for HF models) | HuggingFace API token |
| `MONGO_URI` | Yes | MongoDB connection string |
| `JWT_SECRET` | Yes | Auth token signing secret |
| `GOOGLE_API_KEY` | Yes (for Gemini) | Gemini API key |
| `BACKEND_URL` | Yes | Backend base URL |
| `FRONTEND_URL` | Yes | Frontend base URL (for OAuth redirects) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth app client secret |
| `GITHUB_CLIENT_ID` | No | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | No | GitHub OAuth app client secret |
| `QWEN_72B_MODEL` | No | Override 72B model name |
| `QWEN_72B_BASE_URL` | No | Override 72B base URL |
| `QWEN_7B_MODEL` | No | Override 7B model name |
| `QWEN_7B_BASE_URL` | No | Override 7B base URL |
| `GEMINI_MODEL` | No | Override Gemini model name |
| `LOCAL_72B_BASE_URL` | No | Local vLLM server URL |
| `LOCAL_72B_MODEL` | No | Local vLLM model name |
