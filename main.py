import os
import psycopg2
from controller import google_auth, repo_chat, repo_names, user_controller
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from models.chat_history import create_history_table
from models.repo_names import create_tables
from models.users import create_users
import gitretrieval
from models.config import conn
import search_commits

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://gitxen-zq9s.vercel.app"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gitretrieval.router)
app.include_router(search_commits.router)
app.include_router(repo_names.router)
app.include_router(user_controller.router)
app.include_router(google_auth.router)
app.include_router(repo_chat.router)



DATA_PATH = "data/books"


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={"detail": "Server error"}, status_code=500)

    origin = request.headers.get("origin")
    if origin in ["http://localhost:3000", "https://gitxen-zq9s.vercel.app"]:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

@app.on_event("startup")
def on_startup():
    try:
        cur = conn.cursor()

        create_users(conn=conn)
        create_tables(conn=conn)
        create_history_table(conn=conn)
        # cur.execute("DROP SCHEMA public CASCADE;")
        # conn.commit()
    #     cur.execute("""
    #     -- create schema again (no-op if it already exists)
    #     CREATE SCHEMA IF NOT EXISTS public AUTHORIZATION CURRENT_USER;

    #     -- make sure your role can use it
    #     GRANT ALL ON SCHEMA public TO CURRENT_USER;
    # """)
        conn.commit()

        print("✅ Tables created or verified. PostgreSQL version")

    except Exception as e:
        print("❌ Error during database setup:", e)
