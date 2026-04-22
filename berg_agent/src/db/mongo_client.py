import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

try:
    client = MongoClient(MONGO_URI)
    client.admin.command("ping")
    print("Connected to MongoDB")
except ConnectionFailure as e:
    print(f"Failed to connect to MongoDB: {e}")

db = client["research_agent_db"]

papers_collection = db["papers"]
users_collection = db["users"]
sessions_collection = db["chat_sessions"]
compare_sessions_collection = db["compare_sessions"]

papers_collection.create_index("link", unique=True)
users_collection.create_index("email", unique=True)
sessions_collection.create_index([("user_id", ASCENDING), ("session_id", ASCENDING)])
compare_sessions_collection.create_index("session_id", unique=True)
compare_sessions_collection.create_index([("user_id", ASCENDING)])

def validate_paper_schema(paper_data:dict) -> bool:
    required_keys = ["link","title","date_published","text_content","keywords"]
    for key in required_keys:
        if key not in paper_data:
            raise ValueError(f"Missing required key in paper schema: '{key}'")
    if not isinstance(paper_data["text_content"],dict):
        raise ValueError("'text_content' must be a dictionary with parsed sections.")
    if not isinstance(paper_data["keywords"],list):
        raise ValueError("'keywords' must be a list of strings.")
    return True

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── User CRUD ─────────────────────────────────────────────────────────────────

def create_user(email: str, hashed_password: str) -> dict:
    user = {
        "user_id": str(uuid.uuid4()),
        "email": email,
        "password": hashed_password,
        "created_at": _now(),
    }
    users_collection.insert_one(user)
    return {"user_id": user["user_id"], "email": user["email"]}


def get_user_by_email(email: str) -> dict | None:
    return users_collection.find_one({"email": email}, {"_id": 0})


def get_or_create_oauth_user(email: str, provider: str) -> dict:
    """Find existing user by email or create one (no password for OAuth users)."""
    existing = get_user_by_email(email)
    if existing:
        return {"user_id": existing["user_id"], "email": existing["email"]}
    user = {
        "user_id": str(uuid.uuid4()),
        "email": email,
        "password": None,
        "oauth_provider": provider,
        "created_at": _now(),
    }
    users_collection.insert_one(user)
    return {"user_id": user["user_id"], "email": user["email"]}


# ── Session CRUD ──────────────────────────────────────────────────────────────

def create_session(user_id: str, title: str = "New conversation") -> str:
    session_id = str(uuid.uuid4())
    sessions_collection.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "title": title,
        "messages": [],
        "created_at": _now(),
        "updated_at": _now(),
    })
    return session_id


def get_sessions_by_user(user_id: str) -> list[dict]:
    cursor = sessions_collection.find(
        {"user_id": user_id},
        {"_id": 0, "messages": 0},
    ).sort("updated_at", -1)
    return list(cursor)


def get_session(session_id: str, user_id: str) -> dict | None:
    return sessions_collection.find_one(
        {"session_id": session_id, "user_id": user_id}, {"_id": 0}
    )


def append_message(session_id: str, role: str, content: str) -> None:
    msg = {"role": role, "content": content, "timestamp": _now()}
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$push": {"messages": msg}, "$set": {"updated_at": _now()}},
    )


def update_session_title(session_id: str, title: str) -> None:
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"title": title, "updated_at": _now()}},
    )


def delete_session(session_id: str, user_id: str) -> bool:
    result = sessions_collection.delete_one({"session_id": session_id, "user_id": user_id})
    return result.deleted_count > 0


# ── Paper CRUD ────────────────────────────────────────────────────────────────

def get_paper_by_link(url:str) -> dict:
    result = papers_collection.find_one({"link":url},{"_id":0})
    return result

def insert_paper(paper_data:dict) -> bool:
    try:
        validate_paper_schema(paper_data)
        papers_collection.insert_one(paper_data)
        print(f"Paper '{paper_data['title']}' inserted successfully")
        return True
    except DuplicateKeyError:
        print(f"Paper '{paper_data['title']}' already exists")
        return False
    except ValueError as e:
        print(f"Error validating paper schema: {e}")
        return False
    except Exception as e:
        print(f"Error inserting paper: {e}")
        return False


# ── Comparison Session CRUD ───────────────────────────────────────────────────

def create_compare_session(user_id: str, title: str = "New comparison") -> str:
    session_id = str(uuid.uuid4())
    compare_sessions_collection.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "title": title,
        "turns": [],
        "created_at": _now(),
        "updated_at": _now(),
    })
    return session_id


def get_compare_sessions_by_user(user_id: str) -> list[dict]:
    cursor = compare_sessions_collection.find(
        {"user_id": user_id},
        {"_id": 0, "turns": 0},
    ).sort("updated_at", -1)
    return list(cursor)


def get_compare_session(session_id: str, user_id: str) -> dict | None:
    return compare_sessions_collection.find_one(
        {"session_id": session_id, "user_id": user_id}, {"_id": 0}
    )


def append_compare_turn(session_id: str, user_message: str, responses: dict, timings: dict) -> None:
    """
    responses: {"qwen7b": str, "qwen72b": str, "gemini": str}
    timings:   {"qwen7b": float, "qwen72b": float, "gemini": float}
    """
    turn = {
        "user_message": user_message,
        "responses": responses,
        "timings": timings,
        "timestamp": _now(),
    }
    compare_sessions_collection.update_one(
        {"session_id": session_id},
        {"$push": {"turns": turn}, "$set": {"updated_at": _now()}},
    )


def update_compare_session_title(session_id: str, title: str) -> None:
    compare_sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"title": title, "updated_at": _now()}},
    )


def delete_compare_session(session_id: str, user_id: str) -> bool:
    result = compare_sessions_collection.delete_one({"session_id": session_id, "user_id": user_id})
    return result.deleted_count > 0