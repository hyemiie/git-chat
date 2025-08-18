import os
import json
import numpy as np
import faiss
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
from git import Repo, InvalidGitRepositoryError
from sentence_transformers import SentenceTransformer
import os
import tempfile
import uuid
import shutil
import git

from search_commits import analyze_query, ask_llm_name
router = APIRouter()


class RepoResponse(BaseModel):
    repo_name: str
    summary: str

class RepoRequest(BaseModel):
    repo_path: str
    query : str


def get_commits(repo_url_or_path):
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
                d.diff.decode("utf-8", errors="ignore") for d in commit.diff(commit.parents[0], create_patch=True)
            ) if commit.parents else ""
        }
        commits.append(commit_data)

    print(f"Indexed {len(commits)} commits.")
    return commits


def embed_and_save(commits, model_name="all-MiniLM-L6-v2"):
    model = SentenceTransformer(model_name)

    for commit in commits:
        content = f"{commit['message']} \n {commit['diff']}"
        commit["embedding"] = model.encode(content).tolist()

    with open("commits_with_embeddings.json", "w") as f:
        json.dump(commits, f, indent=2)

    embeddings = np.array([c["embedding"] for c in commits]).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, "faiss.index")
    return f"Embedded {len(commits)} commits and saved index."

@router.post("/embed-repo")
def process_repo(request: RepoRequest):
    commits = get_commits(request.repo_path)
    result_message = embed_and_save(commits)
    result = analyze_query(request.query)
    return {"result": result, "commit_count": len(commits)}

class RepoRequest(BaseModel):
    repo_path: str

@router.post("/analyze-repo")
def analyze_repo(request: RepoRequest):
    repo_url = request.repo_path.strip()
    try:

        # query = "Give a suitable and concise name for this repository based on its content. Just return the name only.Maximum 2-3 word"
        query = "Give a concise name for this repository based on its content. Return ONLY the name. Use exactly 2 words. Do not include quotes or extra text or brackets or explanations."
        generated_name = ask_llm_name(repo_url, query)
        print("repo", generated_name)

        return {
            "repo_name": generated_name
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process repo: {str(e)}")
   