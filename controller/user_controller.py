import os
import bcrypt
import datetime
import json
from fastapi import FastAPI, Request, Depends, HTTPException, APIRouter
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from controller.google_auth import create_access_token
from models.config import conn 

router = APIRouter()
app = FastAPI()


app.add_middleware(SessionMiddleware, secret_key=os.getenv("GOOGLE_SECRET_KEY"))
GOOGLE_CLIENT_ID =  os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET =  os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY =  os.getenv("GOOGLE_SECRET_KEY")

config_data = {
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
    "SECRET_KEY": SECRET_KEY,
}
config = Config(environ=config_data)
oauth = OAuth(config)

google = oauth.register(
    name="google",
    client_id=config_data["GOOGLE_CLIENT_ID"],
    client_secret=config_data["GOOGLE_CLIENT_SECRET"],
    access_token_url="https://oauth2.googleapis.com/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)
class UserSignup(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/signup")
def create_new_user(user: UserSignup):
    try:
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users(email, password) VALUES (%s, %s)",
                (user.email, hashed_password)
            )
            conn.commit()
        return {"status": "success", "message": "User created successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/login")
def login(user: UserLogin):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (user.email,))
            user_record = cur.fetchone()

            if not user_record:
                return {"status": "fail", "message": "Invalid email or password"}

            if user_record[3] is None:
                return {"status": "fail", "message": "Try logging in with Google"}

            stored_hash_value = user_record[3]
            stored_hash = (
                stored_hash_value.tobytes()
                if hasattr(stored_hash_value, 'tobytes')
                else bytes.fromhex(stored_hash_value[2:])
            )

            user_input_password = user.password.encode('utf-8')
            if bcrypt.checkpw(user_input_password, stored_hash):
                access_token = create_access_token(
                    data={"sub": str(user_record[0])},
                    expires_delta=datetime.timedelta(minutes=60)      
                                        
                    )

                return {
                    "status": "success",
                    "message": "Login successful",
                    "token": access_token
                }
            else:
                return {"status": "fail", "message": "Invalid email or password"}

    except Exception as e:
        return {"status": "error", "message": str(e)}



@router.post("/delete")
def delete_user(user: UserLogin):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (user.email,))
            user_record = cur.fetchone()

            if user_record and bcrypt.checkpw(user.password.encode('utf-8'), user_record[2].encode('utf-8')):
                cur.execute("DELETE FROM users WHERE email = %s", (user.email,))
                conn.commit()
                return {"status": "success", "message": "User deleted successfully"}
            else:
                return {"status": "fail", "message": "Invalid credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# @router.get("/login_google")
# async def login_with_google(request: Request):
#     redirect_uri = str(request.base_url) + "auth"
#     return await google.authorize_redirect(request, redirect_uri)

# @router.get("/auth", name="auth") 
# async def auth(request: Request):
#     try:
#         token = await google.authorize_access_token(request)
#         user_info = await google.parse_id_token(request, token)
        
#         email = user_info.get('email')
#         name = user_info.get('name')
        
#         try:
#             with conn.cursor() as cur:
#                 cur.execute(
#                     "INSERT INTO users (email, username, is_google_user) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING",
#                     (email, name, True)
#                 )
#                 conn.commit()
#         except Exception as db_error:
#             print(f"Database error: {db_error}")
        
#         request.session["user"] = dict(user_info)
        
#         return RedirectResponse(url="http://localhost:3000/demo")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# @router.get("/logout")
# def logout(request: Request):
#     request.session.pop("user", None)
#     return RedirectResponse(url="http://localhost:3000/")

# @router.get("/")
# def home(request: Request):
#     user = request.session.get("user")
#     if user:
#         return {"logged_in": True, "user": user}
#     return {"logged_in": False, "message": "Not authenticated"}

# @router.get("/check-auth")
# def check_auth(request: Request):
    user = request.session.get("user")
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}