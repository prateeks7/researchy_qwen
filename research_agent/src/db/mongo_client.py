import os 
from pymongo import MongoClient
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

papers_collection.create_index("link", unique=True)

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