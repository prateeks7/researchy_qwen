"""
OAuth2 helpers for Google and GitHub authorization code flow.
"""

import os
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ── Google ────────────────────────────────────────────────────────────────────

def google_auth_url() -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BACKEND_URL}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def google_get_user(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{BACKEND_URL}/api/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        return user_resp.json()


# ── GitHub ────────────────────────────────────────────────────────────────────

def github_auth_url() -> str:
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": f"{BACKEND_URL}/api/auth/github/callback",
        "scope": "user:email",
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def github_get_user(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        headers = {"Authorization": f"token {access_token}", "Accept": "application/json"}

        user_resp = await client.get("https://api.github.com/user", headers=headers)
        user_resp.raise_for_status()
        user_data = user_resp.json()

        # Public email may be null — fetch primary email separately
        if not user_data.get("email"):
            email_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            emails = email_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            user_data["email"] = primary["email"] if primary else None

        return user_data
