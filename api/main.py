# /srv/jupyterhub/api/main.py
import os
import asyncio
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote
import pathlib
import requests
import httpx
import jwt
from jose import JWTError, jwt
from fastapi import FastAPI, Header, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel

HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8000")
HUB_API_TOKEN = os.getenv("HUB_API_TOKEN") 
FILES_ROOT = os.getenv("FILES_ROOT", "/home")
APP_DIRNAME = os.getenv("APP_DIRNAME", "apps")
DEFAULT_DOC = os.getenv("DEFAULT_DOC", "welcome_app.py")
AUTH0_DOMAIN = os.getenv("AUTH_DOMAIN")  # Add this

app = FastAPI(title="marimo-api", version="1.0.0")

# Cache JWKS at startup
JWKS_CACHE = None

async def get_auth0_jwks():
    """Get Auth0 JWKS for token verification"""
    global JWKS_CACHE
    if JWKS_CACHE is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
            JWKS_CACHE = response.json()
    return JWKS_CACHE

def _get_key(header, jwks):
    """Get the correct key from JWKS"""
    kid = header.get("kid")
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    return None

async def verify_auth0_token(token: str):
    """Verify Auth0 JWT token"""
    try:
        jwks = await get_auth0_jwks()
        issuer = f"https://{AUTH0_DOMAIN}/"
        
        header = jwt.get_unverified_header(token)
        key = _get_key(header, jwks)
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token key")
        
        # Verify the token
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=os.getenv("AUTH_AUDIENCE"),  # Your API audience
            issuer=issuer,
        )
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification error: {str(e)}")

def _hub_headers():
    """Headers for JupyterHub API calls"""
    if not HUB_API_TOKEN:
        raise RuntimeError("HUB_API_TOKEN not set")
    return {
        "Authorization": f"token {HUB_API_TOKEN}",
        "Content-Type": "application/json"
    }

async def _ensure_user_exists(username: str):
    """Ensure user exists in JupyterHub"""
    try:
        async with httpx.AsyncClient() as client:
            # Check if user exists
            r = await client.get(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code == 404:
                # User doesn't exist, create it
                r = await client.post(
                    f"{HUB_URL}/hub/api/users/{username}", 
                    headers=_hub_headers()
                )
                if r.status_code not in (201, 409):  # 409 = already exists
                    raise HTTPException(status_code=r.status_code, detail=f"Failed to create user: {r.text}")
            
    except Exception as e:
        if not isinstance(e, HTTPException):
            raise HTTPException(status_code=500, detail=f"Error ensuring user exists: {str(e)}")
        raise e

async def _ensure_user_directory(username: str):
    """Ensure user home directory exists"""
    user_home = pathlib.Path(FILES_ROOT) / username
    apps_dir = user_home / APP_DIRNAME

    user_home.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    user_home.chmod(0o755)
    apps_dir.chmod(0o755)

def _ensure_marimo_file(path: pathlib.Path):
    """Create marimo file if it doesn't exist"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('''import marimo as mo

app = mo.App()

@app.cell
def __():
    import marimo as mo
    return mo,

@app.cell
def __(mo):
    mo.md("# Welcome to Marimo!")
    return

if __name__ == "__main__":
    app.run()
''')
    path.chmod(0o644)

def _app_path(username: str, document_name: str) -> pathlib.Path:
    return pathlib.Path(FILES_ROOT) / username / APP_DIRNAME / document_name

async def get_username_from_token(token: str) -> str:
    """Extract username from verified token claims"""
    claims = await verify_auth0_token(token)
    
    # Try different claims for username
    username = (claims.get("email") or 
                claims.get("preferred_username") or 
                claims.get("nickname") or 
                claims.get("sub"))
    
    if not username:
        raise HTTPException(status_code=400, detail="No usable username in token")
    
    # Clean username - remove special characters if needed
    if "@" in username and claims.get("email"):
        username = claims["email"].split("@")[0]
    
    return username

################
# API endpoints
################
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/spawn")
async def spawn_user_server(authorization: Optional[str] = Header(None)):
    """
    Frontend sends: Authorization: Bearer <Auth0 access_token>
    API verifies token and returns JupyterHub user URL
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    
    # Verify Auth0 token and get username
    username = await get_username_from_token(token)
    
    # Ensure user exists in JupyterHub
    await _ensure_user_exists(username)
    
    # Ensure user directories exist
    await _ensure_user_directory(username)
    
    # Return the URL where user can access their Jupyter server
    next_url = f"/hub/user/{quote(username)}/"
    return JSONResponse({
        "ok": True, 
        "user": username, 
        "nextUrl": next_url,
        "message": f"Server ready for user {username}"
    })

@app.post("/users")
async def create_user(authorization: Optional[str] = Header(None)):
    """Create a user from Auth0 token"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        await _ensure_user_exists(username)
        await _ensure_user_directory(username)
        return {"ok": True, "message": f"User {username} created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@app.post("/documents")
async def create_document(
    authorization: Optional[str] = Header(None),
    document_name: str = Form(...)
):
    """Create a new Marimo document for the authenticated user"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        await _ensure_user_exists(username)
        await _ensure_user_directory(username)
        
        p = _app_path(username, document_name)
        _ensure_marimo_file(p)
        return {
            "ok": True, 
            "path": str(p), 
            "message": f"Document {document_name} created for user {username}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")

# Additional management endpoints (protected with HUB_API_TOKEN)
@app.get("/admin/users")
async def list_users(x_api_token: Optional[str] = Header(None)):
    """List all users (admin only)"""
    if x_api_token != HUB_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")
    
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HUB_URL}/hub/api/users", headers=_hub_headers())
            r.raise_for_status()
            users_data = r.json()
            return [u["name"] for u in users_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")