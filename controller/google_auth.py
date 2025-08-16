import os
import jwt
import datetime
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from models.config import conn

router = APIRouter(tags=["google-auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth login"""
    try:
        google_auth_url = (
            f"https://accounts.google.com/o/oauth2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"scope=openid email profile&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        return RedirectResponse(url=google_auth_url)
    except Exception as e:
        print(f"Error initiating Google login: {e}")
        return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=google_login_failed")

@router.get("/auth/google/callback")
async def google_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback"""
    if error:
        print(f"Google OAuth error: {error}")
        return RedirectResponse(url=f"https://gitxen-zq9s.vercel.app/auth?error={error}")
    
    if not code:
        print("No authorization code received")
        return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=no_authorization_code")
    
    try:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI,
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_json = token_response.json()
        
        if "access_token" not in token_json:
            print(f"Token exchange failed: {token_json}")
            return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=token_exchange_failed")
        
        access_token = token_json["access_token"]
        
        user_info_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}"
        
        async with httpx.AsyncClient() as client:
            user_response = await client.get(user_info_url)
            user_info = user_response.json()
        
        if "email" not in user_info:
            print(f"Failed to get user info: {user_info}")
            return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=failed_to_get_user_info")
        
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])  
        google_id = user_info.get('id')
        picture = user_info.get('picture')
        
        print(f"Google user info: {user_info}")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
                existing_user = cur.fetchone()

                if existing_user:
                    cur.execute(
                        """UPDATE users SET 
                        username = %s, 
                        google_id = %s, 
                        profile_picture = %s
                        WHERE email = %s
                        RETURNING id, username, email""",
                        (name, google_id, picture, email)
                    )
                else:
                    cur.execute(
                        """INSERT INTO users (email, username, google_id, is_google_user, profile_picture) 
                        VALUES (%s, %s, %s, %s, %s) 
                        RETURNING id, username, email""",
                        (email, name, google_id, True, picture)
                    )

                user_record = cur.fetchone() 
                conn.commit()

                if not user_record:
                    raise Exception("Failed to create or update user")

        except Exception as db_error:
            print(f"Database error: {db_error}")
            return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=database_error")

            
        user_data = {
            "id": user_record[0],
            "username": user_record[1],
            "email": user_record[2],
            "is_google_user": True,
            "profile_picture": picture
        }
        
        jwt_token = create_access_token(data={"sub": email, "user": user_data})
        
        frontend_url = f"https://gitxen-zq9s.vercel.app/auth?token={jwt_token}"
        return RedirectResponse(url=frontend_url)
        
    except httpx.RequestError as e:
        print(f"HTTP request error: {e}")
        return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=network_error")
    except Exception as e:
        print(f"Unexpected error in Google callback: {e}")
        return RedirectResponse(url="https://gitxen-zq9s.vercel.app/auth?error=unexpected_error")

@router.post("/google/logout")
async def google_logout():
    """Handle Google logout (JWT is stateless, so just return success)"""
    return {"message": "Logged out successfully", "status": "success"}

@router.get("/google/user")
async def get_google_user_info(request: Request):
    """Get current Google user info (requires JWT token in Authorization header)"""
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Depends
    
    security = HTTPBearer()
    
    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        return {
            "authenticated": True,
            "user": payload.get("user"),
            "expires": payload.get("exp")
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        print(f"Error verifying token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error"
        )