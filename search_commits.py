import os
import json
import faiss
import requests
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from fastapi import APIRouter

router =  APIRouter()

load_dotenv()
OPENROUTER_API_KEY = os.getenv('OPEN_ROUTER_AI_KEY')

model = SentenceTransformer("all-MiniLM-L6-v2")
index = faiss.read_index("faiss.index")

with open("commits_with_embeddings.json") as f:
    commits = json.load(f)

# def retrieve_top_k(query, k=3):
#     query_vec = model.encode(query).astype("float32").reshape(1, -1)
#     _, indices = index.search(query_vec, k)
#     return [commits[i] for i in indices[0]]

# def ask_llm(commit_context, question):
#     context_str = "\n\n".join(
# [
#   f"Commit: {c['message']}\nAuthor: {c.get('author', 'Unknown')} <{c.get('email', 'no-email')}>\nDate: {c.get('date', 'no-date')}\nDiff:\n{c.get('diff', '')}"
#   for c in commit_context
# ]
#     )
#     prompt = f"""You are an expert AI code assistant.

# You will be given:
# - A set of git commits and code changes (context).
# - A user question.

# Instructions:
# - Use only the context provided when answering.
# - Be concise, clear, and directly answer the question.
# - Do not include explanations unless explicitly asked.

# Context:
# {context_str}

# Question:
# {question}

# Answer:
# """

#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "model": "mistralai/mistral-7b-instruct",
#         "messages": [{"role": "user", "content": prompt}]
#     }

#     try:
#         res = requests.post(url, headers=headers, json=payload)
#         print("res", res)
#         res.raise_for_status()
#         return res.json()["choices"][0]["message"]["content"]
#     except Exception as e:
#         return f"LLM request failed: {str(e)}"
    


def load_repo_data(repo_id):
    """Load commits + FAISS index for a given repo_id"""
    repo_dir = f"data/{repo_id}"

    # Load commits
    with open(f"{repo_dir}/commits.json", "r") as f:
        commits = json.load(f)

    # Load FAISS index
    index = faiss.read_index(f"{repo_dir}/faiss.index")

    return commits, index


def retrieve_top_k(repo_id, query, k=3, model_name="all-MiniLM-L6-v2"):
    """Retrieve top-k relevant commits for a query from a given repo"""
    commits, index = load_repo_data(repo_id)
    model = SentenceTransformer(model_name)

    query_vec = model.encode(query).astype("float32").reshape(1, -1)
    _, indices = index.search(query_vec, k)

    return [commits[i] for i in indices[0]]


# def ask_llm(commit_context, question):
#     """Ask the LLM given commit context + question"""
#     context_str = "\n\n".join(
#         [
#             f"Commit: {c['message']}\nAuthor: {c.get('author', 'Unknown')} <{c.get('email', 'no-email')}>\nDate: {c.get('date', 'no-date')}\nDiff:\n{c.get('diff', '')}"
#             for c in commit_context
#         ]
#     )

#     prompt = f"""You are an expert AI code assistant.
# You will be given:
# - A set of git commits and code changes (context).
# - A user question.

# Instructions:
# - Use only the context provided when answering.
# - Be concise, clear, and directly answer the question.
# - Do not include explanations unless explicitly asked.

# Context:
# {context_str}

# Question:
# {question}

# Answer:
# """

#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "model": "mistralai/mistral-7b-instruct",
#         "messages": [{"role": "user", "content": prompt}]
#     }

#     try:
#         res = requests.post(url, headers=headers, json=payload)
#         res.raise_for_status()
#         data = res.json()
#         return data["choices"][0]["message"]["content"]
#     except Exception as e:
#         return f"LLM request failed: {str(e)}"

def ask_llm(top_commits, query: str):
    commit_summaries = "\n".join(
        [f"- {c['hash'][:7]} ({c['date']} by {c['author']}): {c['message']}" for c in top_commits]
    )

    prompt = f"""
    You are analyzing a Git repository.
    The user asked: "{query}".

    Here are the most relevant commits:
    {commit_summaries}

    Provide a concise, human-readable answer.
    """

    payload = {
        "model": "openai/gpt-3.5-turbo",  
        "messages": [
            {"role": "system", "content": "You are a helpful Git commit analyst."},
            {"role": "user", "content": prompt}
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("LLM request failed:", e)
        return "⚠️ Failed to get response from LLM."



def ask_llm_name(url, question):
    

    prompt = f"""You are a helpful and expert AI code assistant. Below is a url and a query

URL:
{url}

Now answer the following query sticking to its rules nad requirements:
{question}
"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM request failed: {str(e)}"


@router.post("/analyze-query")
def analyze_query(query: str):
    
    try:
        top_commits = retrieve_top_k(query)
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
