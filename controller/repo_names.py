from fastapi import FastAPI, HTTPException, Request, status, APIRouter
from pydantic import BaseModel
from psycopg2 import DatabaseError
from models.config import conn 
import datetime

router = APIRouter()

class RepoCreateRequest(BaseModel):
    user_id: int
    repo_name: str
    repo_link: str

class RepoUserRequest(BaseModel):
    user_id: int

class RepoDeleteRequest(BaseModel):
    repo_id: int


@router.post("/repos/", status_code=201)
def create_new_repo(payload: RepoCreateRequest):
    try:
        date_created = datetime.date.today()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO repo_names (user_id, repo_name, repo_link, date_created)
                VALUES (%s, %s, %s, %s)
            """, (payload.user_id, payload.repo_name, payload.repo_link, date_created))
            conn.commit()
        return {"message": "Repository added successfully"}
    except DatabaseError as e:
        conn.rollback()
        print('rgyhuji', e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print("error", e)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/repos/list", status_code=200)
def list_repo(user_id: int):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM repo_names WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            repos = [dict(zip(columns, row)) for row in rows]
            return {"repos": repos}
    except DatabaseError as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.delete("/repos/", status_code=200)
def delete_repo(payload: RepoDeleteRequest):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM repo_names WHERE id = %s", (payload.repo_id,))
            repo_record = cur.fetchone()

            if repo_record:
                cur.execute("DELETE FROM repo_names WHERE id = %s", (payload.repo_id,))
                conn.commit()
                return {"message": "Repository deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Repository not found")
    except DatabaseError as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
