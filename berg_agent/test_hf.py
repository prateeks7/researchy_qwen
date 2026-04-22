import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("HF_TOKEN")

headers = {"Authorization": f"Bearer {token}"}
models = ["Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-32B-Instruct"]

for repo in models:
    url = f"https://api-inference.huggingface.co/models/{repo}"
    resp = requests.post(url, headers=headers, json={"inputs": "hello"})
    print(f"{repo}: {resp.status_code}")
 