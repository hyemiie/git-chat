# import os
# import json
# import numpy as np
# import faiss
# from fastapi import HTTPException, APIRouter
# from pydantic import BaseModel
# from git import Repo, InvalidGitRepositoryError
# from sentence_transformers import SentenceTransformer
# import os
# import tempfile
# import uuid
# import shutil
# import git

# from search_commits import analyze_query, ask_llm_name
# router = APIRouter()


# class RepoResponse(BaseModel):
#     repo_name: str
#     summary: str

# class RepoRequest(BaseModel):
#     repo_path: str
#     query : str


# def get_commits(repo_url_or_path):
#     if os.path.exists(repo_url_or_path):
#         repo_path = repo_url_or_path
#     else:
#         temp_dir = tempfile.mkdtemp()
#         print(f"Cloning repo to temp dir: {temp_dir}")
#         repo_path = Repo.clone_from(repo_url_or_path, temp_dir).working_tree_dir

#     repo = Repo(repo_path)
#     commits = []

#     if not repo.head.is_valid():
#         print("No commits found.")
#         return []

#     for commit in repo.iter_commits():
#         commit_data = {
#             "hash": commit.hexsha,
#             "author": commit.author.name,
#             "email": commit.author.email,
#             "date": commit.committed_datetime.isoformat(),
#             "message": commit.message.strip(),
#             "diff": "".join(
#                 d.diff.decode("utf-8", errors="ignore") for d in commit.diff(commit.parents[0], create_patch=True)
#             ) if commit.parents else ""
#         }
#         commits.append(commit_data)

#     print(f"Indexed {len(commits)} commits.")
#     return commits


# def embed_and_save(commits, model_name="all-MiniLM-L6-v2"):
#     model = SentenceTransformer(model_name)

#     for commit in commits:
#         content = f"{commit['message']} \n {commit['diff']}"
#         commit["embedding"] = model.encode(content).tolist()

#     with open("commits_with_embeddings.json", "w") as f:
#         json.dump(commits, f, indent=2)

#     embeddings = np.array([c["embedding"] for c in commits]).astype("float32")
#     index = faiss.IndexFlatL2(embeddings.shape[1])
#     index.add(embeddings)
#     faiss.write_index(index, "faiss.index")
#     return f"Embedded {len(commits)} commits and saved index."

# @router.post("/embed-repo")
# def process_repo(request: RepoRequest):
#     commits = get_commits(request.repo_path)
#     result_message = embed_and_save(commits)
#     result = analyze_query(request.query)
#     return {"result": result, "commit_count": len(commits)}

# class RepoRequest(BaseModel):
#     repo_path: str

# @router.post("/analyze-repo")
# def analyze_repo(request: RepoRequest):
#     repo_url = request.repo_path.strip()
#     try:

#         # query = "Give a suitable and concise name for this repository based on its content. Just return the name only.Maximum 2-3 word"
#         query = "Give a concise name for this repository based on its content. Return ONLY the name. Use exactly 2 words. Do not include quotes or extra text or brackets or explanations."
#         generated_name = ask_llm_name(repo_url, query)
#         print("repo", generated_name)

#         return {
#             "repo_name": generated_name
#         }

#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Failed to process repo: {str(e)}")
   

import os
import json
import tempfile
import hashlib
import numpy as np
import faiss
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from git import Repo

from search_commits import ask_llm, ask_llm_name

router = APIRouter()

MODEL = SentenceTransformer("all-MiniLM-L6-v2")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def get_repo_id(repo_url_or_path: str) -> str:
    """Generate a stable ID for each repo using its URL or path."""
    return hashlib.md5(repo_url_or_path.encode()).hexdigest()


def get_commits(repo_url_or_path):
    """Clone or open repo and extract commits + diffs."""
    if os.path.exists(repo_url_or_path):
        repo_path = repo_url_or_path
    else:
        temp_dir = tempfile.mkdtemp()
        print(f"Cloning repo to temp dir: {temp_dir}")
        repo_path = Repo.clone_from(repo_url_or_path, temp_dir).working_tree_dir

    repo = Repo(repo_path)
    commits = []

    if not repo.head.is_valid():
        print("No commits found.")
        return []

    for commit in repo.iter_commits():
        commit_data = {
            "hash": commit.hexsha,
            "author": commit.author.name,
            "email": commit.author.email,
            "date": commit.committed_datetime.isoformat(),
            "message": commit.message.strip(),
            "diff": "".join(
                d.diff.decode("utf-8", errors="ignore")
                for d in commit.diff(commit.parents[0], create_patch=True)
            )
            if commit.parents
            else ""
        }
        commits.append(commit_data)

    print(f"Indexed {len(commits)} commits.")
    return commits


def embed_and_save(repo_id: str, commits):
    """Embed only new commits and update FAISS index for this repo."""
    repo_dir = os.path.join(DATA_DIR, repo_id)
    os.makedirs(repo_dir, exist_ok=True)

    commits_file = os.path.join(repo_dir, "commits.json")
    index_file = os.path.join(repo_dir, "faiss.index")

    try:
        with open(commits_file, "r") as f:
            existing = {c["hash"]: c for c in json.load(f)}
    except FileNotFoundError:
        existing = {}

    new_commits = []
    for commit in commits:
        if commit["hash"] not in existing:
            content = f"{commit['message']} \n {commit['diff']}"
            commit["embedding"] = MODEL.encode(content).tolist()
            existing[commit["hash"]] = commit
            new_commits.append(commit)

    with open(commits_file, "w") as f:
        json.dump(list(existing.values()), f, indent=2)

    if new_commits:
        embeddings = np.array([c["embedding"] for c in new_commits]).astype("float32")

        if os.path.exists(index_file):
            index = faiss.read_index(index_file)
        else:
            index = faiss.IndexFlatL2(embeddings.shape[1])

        index.add(embeddings)
        faiss.write_index(index, index_file)

    return f"Embedded {len(new_commits)} new commits."


def retrieve_top_k(repo_id: str, query: str, k: int = 5):
    """Retrieve top-k relevant commits for a given repo."""
    repo_dir = os.path.join(DATA_DIR, repo_id)
    commits_file = os.path.join(repo_dir, "commits.json")
    index_file = os.path.join(repo_dir, "faiss.index")

    if not (os.path.exists(commits_file) and os.path.exists(index_file)):
        raise ValueError("Repo not embedded yet. Please call /embed-repo first.")

    with open(commits_file, "r") as f:
        commits = json.load(f)

    index = faiss.read_index(index_file)

    query_emb = MODEL.encode(query).astype("float32").reshape(1, -1)
    D, I = index.search(query_emb, k)

    return [commits[i] for i in I[0] if i < len(commits)]



@router.post("/embed-repo")
def process_repo(request: dict):
    repo_path = request["repo_path"]
    repo_id = get_repo_id(repo_path)

    commits = get_commits(repo_path)
    result_message = embed_and_save(repo_id, commits)

    return {"repo_id": repo_id, "message": result_message, "commit_count": len(commits)}


# @router.post("/analyze-query")
# def analyze_query(request: dict):
#     try:
#         repo_id = request["repo_id"]
#         query = request["query"]

#         top_commits = retrieve_top_k(repo_id, query)
#         summary = ask_llm(top_commits, query)

#         return {
#             "top_commits": [
#                 {
#                     "date": c["date"],
#                     "author": c["author"],
#                     "message": c["message"].strip(),
#                     "hash": c["hash"][:7]
#                 }
#                 for c in top_commits
#             ],
#             "summary": summary
#         }
#     except Exception as e:
#         return {"error": str(e)}



@router.post("/analyze-query")
def analyze_query(request: dict):
    try:
        repo_id = request["repo_id"]
        query = request["query"]

        top_commits = retrieve_top_k(repo_id, query)
        summary = ask_llm(top_commits, query)

        return {
            "top_commits": [
                {
                    "date": c["date"],
                    "author": c["author"],
                    "message": c["message"].strip(),
                    "hash": c["hash"][:7]
                }
                for c in top_commits
            ],
            "summary": summary
        }
    except Exception as e:
        return {"error": str(e)}

class RepoRequest(BaseModel):
    repo_path: str
    query : str


@router.post("/analyze-repo")
def analyze_repo(request: RepoRequest):
    repo_url = request.repo_path.strip()
    try:

        query = "Give a concise name for this repository based on its content. Return ONLY the name. Use exactly 2 words. Do not include quotes or extra text or brackets or explanations."
        generated_name = ask_llm_name(repo_url, query)
        print("repo", generated_name)

        return {
            "repo_name": generated_name
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process repo: {str(e)}")
   
