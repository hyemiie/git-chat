import os
import psycopg2
from controller import google_auth, repo_chat, repo_names, user_controller
from fastapi import FastAPI
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
    allow_origins=["*"],  
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
