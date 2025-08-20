import json
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from typing import Optional
from models.config import conn 
from psycopg2 import Error
import datetime

router = APIRouter()

class ChatAddRequest(BaseModel):
    user_id: int
    repo_id: int
    sender: str  # "user" or "ai"
    message_text: str

class ChatListRequest(BaseModel):
    repo_id: int

class ChatDeleteRequest(BaseModel):
    repo_id: int 

@router.post("/chat/add")
def add_to_chat(payload: ChatAddRequest):
    try:
        with conn.cursor() as cur:
            # Get the next message order for this repo
            cur.execute(
                "SELECT COALESCE(MAX(message_order), 0) + 1 FROM chat_history WHERE repo_id = %s",
                (payload.repo_id,)
            )
            next_order = cur.fetchone()[0]
            
            # Insert the new message
            cur.execute(
                """INSERT INTO chat_history (repo_id, sender_id, sender_type, message_text, message_order, created_at) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (payload.repo_id, payload.user_id, payload.sender, payload.message_text, next_order, datetime.datetime.now())
            )
            
            conn.commit()
            return {"status": "success", "message": "Chat message added"}
            
    except Error as e:
        conn.rollback()
        print("error", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/list")
def list_user_chat(payload: ChatListRequest):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, sender_id, sender_type, message_text, created_at, message_order 
                   FROM chat_history 
                   WHERE repo_id = %s 
                   ORDER BY message_order ASC""",
                (payload.repo_id,)
            )
            messages = cur.fetchall()
            
            if messages:
                message_list = []
                for msg in messages:
                    message_list.append({
                        "id": msg[0],
                        "sender_id": msg[1],
                        "sender": msg[2],  
                        "text": msg[3],  
                        "created_at": msg[4].isoformat() if msg[4] else None,
                        "order": msg[5]  
                    })
                return {"status": "success", "data": message_list}
            else:
                return {"status": "success", "data": []}
    except Error as e:
        print('error', e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/delete")
def delete_chat(payload: ChatDeleteRequest):
    try:
        with conn.cursor() as cur:
            # Check if chat exists
            cur.execute(
                "SELECT COUNT(*) FROM chat_history WHERE repo_id = %s",
                (payload.repo_id,)
            )
            count = cur.fetchone()[0]

            if count > 0:
                cur.execute(
                    "DELETE FROM chat_history WHERE repo_id = %s",
                    (payload.repo_id,)
                )
                conn.commit()
                return {"status": "success", "message": f"Deleted {count} messages for repo {payload.repo_id}"}
            else:
                raise HTTPException(status_code=404, detail="No chat messages found for this repository")
    except Error as e:
        conn.rollback()
        print("error", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/history/{user_id}/{repo_id}")
def get_chat_history(user_id: int, repo_id: int):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, sender_type, message_text, created_at, message_order
                   FROM chat_history 
                   WHERE sender_id = %s AND repo_id = %s 
                   ORDER BY message_order ASC""",
                (user_id, repo_id)
            )
            messages = cur.fetchall()
            
            if messages:
                message_list = []
                for msg in messages:
                    message_list.append({
                        "id": msg[0],
                        "sender": msg[1],  # sender_type
                        "text": msg[2],    # message_text
                        "created_at": msg[3].isoformat() if msg[3] else None,
                        "order": msg[4]    # message_order
                    })
                return {"status": "success", "data": message_list}
            else:
                return {"status": "success", "data": []}
    except Error as e:
        print("error", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/stats/{repo_id}")
def get_chat_stats(repo_id: int):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 
                   COUNT(*) as total_messages,
                   COUNT(CASE WHEN sender_type = 'user' THEN 1 END) as user_messages,
                   COUNT(CASE WHEN sender_type = 'ai' THEN 1 END) as ai_messages,
                   MIN(created_at) as first_message,
                   MAX(created_at) as last_message
                   FROM chat_history 
                   WHERE repo_id = %s""",
                (repo_id,)
            )
            stats = cur.fetchone()
            
            return {
                "status": "success", 
                "stats": {
                    "total_messages": stats[0],
                    "user_messages": stats[1],
                    "ai_messages": stats[2],
                    "first_message": stats[3].isoformat() if stats[3] else None,
                    "last_message": stats[4].isoformat() if stats[4] else None
                }
            }
    except Error as e:
        print("error", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/clear_old/{repo_id}")
def clear_old_messages(repo_id: int, days: int = 30):
    try:
        with conn.cursor() as cur:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            cur.execute(
                "DELETE FROM chat_history WHERE repo_id = %s AND created_at < %s",
                (repo_id, cutoff_date)
            )
            deleted_count = cur.rowcount
            conn.commit()
            
            return {
                "status": "success", 
                "message": f"Deleted {deleted_count} messages older than {days} days"
            }
    except Error as e:
        conn.rollback()
        print("error", e)
        raise HTTPException(status_code=500, detail=str(e))