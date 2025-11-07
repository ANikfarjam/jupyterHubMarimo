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
from fastapi import FastAPI, Header, HTTPException, Depends, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel
import json
from typing import Dict, Any
import logging 

HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8000")
HUB_API_TOKEN = os.getenv("HUB_API_TOKEN") 
FILES_ROOT = os.getenv("FILES_ROOT", "/home")
APP_DIRNAME = os.getenv("APP_DIRNAME", "apps")
DEFAULT_DOC = os.getenv("DEFAULT_DOC", "welcome_app.py")
AUTH0_DOMAIN = os.getenv("AUTH_DOMAIN")  # Add this

app = FastAPI(title="marimo-api", version="1.0.0")
log = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # or ["*"] only for quick local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "*"],
)
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
        print(f"DEBUG: Starting token verification for domain: {AUTH0_DOMAIN}")
        print(f"DEBUG: Expected audience: {os.getenv('AUTH_AUDIENCE')}")
        
        jwks = await get_auth0_jwks()
        issuer = f"https://{AUTH0_DOMAIN}/"
        
        # Decode without verification first to get the header
        header = jwt.get_unverified_header(token)
        print(f"DEBUG: Token header: {header}")
        
        key = _get_key(header, jwks)
        if not key:
            print("DEBUG: No matching key found in JWKS")
            raise HTTPException(status_code=401, detail="Invalid token key")
        
        print("DEBUG: Key found, verifying token...")
        
        # Verify the token
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=os.getenv("AUTH_AUDIENCE"),
            issuer=issuer,
        )
        print(f"DEBUG: Token verified successfully for user: {claims.get('email')}")
        return claims
        
    except jwt.ExpiredSignatureError:
        print("DEBUG: Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTClaimsError as e:
        print(f"DEBUG: JWT claims error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid claims: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Token verification error: {str(e)}")
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
    print(f"Debug: all token claims: {claims}")
    if not username:
        raise HTTPException(status_code=400, detail="No usable username in token")
    
    # Clean username - remove special characters if needed
    if "@" in username and claims.get("email"):
        username = claims["email"].split("@")[0]
    
    return username

async def _check_user_server_running(username: str) -> bool:
    """Check if user has a running server"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HUB_URL}/hub/api/users/{username}",
                headers=_hub_headers()
            )
            
            if response.status_code == 200:
                user_data = response.json()
                server_info = user_data.get('servers', {}).get('')
                return server_info and server_info.get('ready', False)
            
            return False
    except Exception:
        return False
################
# API endpoints
################

@app.post("/spawn")
async def spawn_user_server(authorization: Optional[str] = Header(None)):
    """
    Spawn a JupyterHub server for the user (no document creation)
    """
    log.info("DEBUG: /spawn endpoint called")
    
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    
    try:
        # Verify Auth0 token and get username
        username = await get_username_from_token(token)
        log.info(f"DEBUG: Spawning server for user: {username}")
        
        # Ensure user exists in JupyterHub
        await _ensure_user_exists(username)
        log.info(f"DEBUG: User {username} ensured in JupyterHub")
        
        # Ensure user directories exist
        await _ensure_user_directory(username)
        log.info(f"DEBUG: Directories created for user {username}")
        
        # Start the JupyterHub server
        async with httpx.AsyncClient() as client:
            # Start user server
            spawn_response = await client.post(
                f"{HUB_URL}/hub/api/users/{username}/server",
                headers=_hub_headers()
            )
            
            if spawn_response.status_code in [202, 201]:
                log.info(f"DEBUG: Server spawn initiated for {username}")
                # Wait a bit for server to start
                max_wait = 60
                poll_interval = 3
                waited = 0

                while waited < max_wait:
                    await asyncio.sleep(poll_interval)
                    waited += poll_interval
                    
                    # Check server status
                    status_response = await client.get(
                        f"{HUB_URL}/hub/api/users/{username}",
                        headers=_hub_headers()
                    )
                    
                    if status_response.status_code == 200:
                        user_data = status_response.json()
                        server_info = user_data.get('servers', {}).get('')
                        
                        if server_info and server_info.get('ready'):
                            # Server is ready!
                            break

                
                # Check server status
                server_status = await client.get(
                    f"{HUB_URL}/hub/api/users/{username}",
                    headers=_hub_headers()
                )
                
                if server_status.status_code == 200:
                    user_data = server_status.json()
                    server_info = user_data.get('servers', {}).get('')
                    
                    if server_info and server_info.get('ready'):
                        server_url = server_info.get('url', f"/hub/user/{quote(username)}/")
                        log.info(f"DEBUG: Server ready at: {server_url}")
                        
                        return JSONResponse({
                            "ok": True, 
                            "user": username, 
                            "nextUrl": server_url,
                            "server_ready": True,
                            "message": f"Server ready for user {username}"
                        })
                    else:
                        # Server is starting but not ready yet
                        return JSONResponse({
                            "ok": True,
                            "user": username,
                            "nextUrl": f"/hub/user/{quote(username)}/",
                            "server_ready": False,
                            "message": f"Server is starting for user {username}. Please wait..."
                        })
                else:
                    raise HTTPException(status_code=500, detail="Failed to check server status")
            else:
                error_detail = spawn_response.text
                log.info(f"DEBUG: Spawn failed with status {spawn_response.status_code}: {error_detail}")
                raise HTTPException(
                    status_code=spawn_response.status_code, 
                    detail=f"Failed to spawn server: {error_detail}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        log.info(f"DEBUG: Unexpected error in spawn: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error spawning server: {str(e)}")
    

@app.get("/users/{username}/servers")
async def get_user_servers(
    username: str,
    x_api_token: Optional[str] = Header(None)
):
    """Get all servers/spawned environments for a specific user"""
    # Verify admin token for security
    if x_api_token != HUB_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user info from JupyterHub API
            r = await client.get(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code == 404:
                return {
                    "ok": True,
                    "user_exists": False,
                    "servers": [],
                    "message": f"User {username} does not exist"
                }
            
            r.raise_for_status()
            user_data = r.json()
            
            # Extract server information
            servers = []
            if user_data.get("servers"):
                for server_name, server_info in user_data["servers"].items():
                    server_data = {
                        "name": server_name,
                        "ready": server_info.get("ready", False),
                        "pending": server_info.get("pending"),
                        "url": server_info.get("url"),
                        "progress_url": server_info.get("progress_url"),
                        "started": server_info.get("started"),
                        "last_activity": server_info.get("last_activity"),
                    }
                    servers.append(server_data)
            
            return {
                "ok": True,
                "user_exists": True,
                "servers": servers,
                "message": f"Found {len(servers)} servers for user {username}"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user servers: {str(e)}")

@app.get("/users/{username}/servers/{server_name}")
async def get_user_server_status(
    username: str,
    server_name: str,
    x_api_token: Optional[str] = Header(None)
):
    """Get status of a specific server for a user"""
    # Verify admin token for security
    if x_api_token != HUB_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user info from JupyterHub API
            r = await client.get(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail=f"User {username} not found")
            
            r.raise_for_status()
            user_data = r.json()
            
            # Check if the specific server exists
            servers = user_data.get("servers", {})
            if server_name not in servers:
                return {
                    "ok": True,
                    "server_exists": False,
                    "message": f"Server '{server_name}' not found for user {username}"
                }
            
            server_info = servers[server_name]
            
            return {
                "ok": True,
                "server_exists": True,
                "server": {
                    "name": server_name,
                    "ready": server_info.get("ready", False),
                    "pending": server_info.get("pending"),
                    "url": server_info.get("url"),
                    "progress_url": server_info.get("progress_url"),
                    "started": server_info.get("started"),
                    "last_activity": server_info.get("last_activity"),
                    "state": "ready" if server_info.get("ready") else "pending" if server_info.get("pending") else "stopped"
                },
                "message": f"Server '{server_name}' status retrieved"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching server status: {str(e)}")

@app.get("/my-servers")
async def get_my_servers(authorization: Optional[str] = Header(None)):
    """Get all servers for the authenticated user (uses Auth0 token)"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user info from JupyterHub API
            r = await client.get(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code == 404:
                return {
                    "ok": True,
                    "user_exists": False,
                    "servers": [],
                    "message": f"User {username} does not exist in JupyterHub"
                }
            
            r.raise_for_status()
            user_data = r.json()
            
            # Extract server information
            servers = []
            if user_data.get("servers"):
                for server_name, server_info in user_data["servers"].items():
                    server_data = {
                        "name": server_name,
                        "ready": server_info.get("ready", False),
                        "pending": server_info.get("pending"),
                        "url": server_info.get("url"),
                        "progress_url": server_info.get("progress_url"),
                        "started": server_info.get("started"),
                        "last_activity": server_info.get("last_activity"),
                        "state": "ready" if server_info.get("ready") else "pending" if server_info.get("pending") else "stopped"
                    }
                    servers.append(server_data)
            
            return {
                "ok": True,
                "user_exists": True,
                "username": username,
                "servers": servers,
                "server_count": len(servers),
                "message": f"Found {len(servers)} servers for user {username}"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user servers: {str(e)}")

@app.get("/my-servers/status")
async def check_my_servers_status(authorization: Optional[str] = Header(None)):
    """Check if user has any running servers"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user info from JupyterHub API
            r = await client.get(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code == 404:
                return {
                    "ok": True,
                    "has_servers": False,
                    "has_running_servers": False,
                    "message": f"User {username} does not exist"
                }
            
            r.raise_for_status()
            user_data = r.json()
            
            servers = user_data.get("servers", {})
            running_servers = []
            
            for server_name, server_info in servers.items():
                if server_info.get("ready"):
                    running_servers.append({
                        "name": server_name,
                        "url": server_info.get("url"),
                        "started": server_info.get("started")
                    })
            
            has_servers = len(servers) > 0
            has_running_servers = len(running_servers) > 0
            
            return {
                "ok": True,
                "has_servers": has_servers,
                "has_running_servers": has_running_servers,
                "total_servers": len(servers),
                "running_servers_count": len(running_servers),
                "running_servers": running_servers,
                "message": f"User {username} has {len(running_servers)} running server(s) out of {len(servers)} total"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking server status: {str(e)}")

##########################################
# user and documents management routes
##########################################
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
    document_name: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """Create a new Marimo document - requires running server"""
    print("DEBUG: /documents endpoint called")
    print(f"DEBUG: Received document_name query parameter: {document_name}")
    print(f"DEBUG: Authorization header: {authorization[:50] if authorization else 'None'}...")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    
    try:
        # Verify Auth0 token and get username
        username = await get_username_from_token(token)
        print(f"DEBUG: Creating document for user: {username}")
        
        # Check if user has a running server
        server_running = await _check_user_server_running(username)
        if not server_running:
            raise HTTPException(
                status_code=400, 
                detail="No running server found. Please spawn a server first."
            )
        
        print(f"DEBUG: Server is running for user {username}, creating document...")
        
        # Ensure user exists and directories are ready
        await _ensure_user_exists(username)
        await _ensure_user_directory(username)
        
        # Create the document
        p = _app_path(username, document_name)
        _ensure_marimo_file(p)

        print(f"DEBUG: Document created at: {p}")

        return {
            "ok": True,
            "path": str(p),
            "message": f"Document {document_name} created for user {username}",
            "server_running": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")
    

# getting existing documents from the spawned server
@app.get("/documents")
async def list_documents(authorization: Optional[str] = Header(None)):
    """List all Marimo documents for the authenticated user"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        await _ensure_user_exists(username)
        
        # Get the user's apps directory
        apps_dir = _app_path(username, "")
        
        # List all Python files in the apps directory
        documents = []
        if apps_dir.exists():
            for file_path in apps_dir.iterdir():
                if file_path.is_file() and file_path.suffix == '.py':
                    documents.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime
                    })
        
        return {
            "ok": True,
            "documents": documents,
            "message": f"Found {len(documents)} documents for user {username}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.get("/documents/{document_name}")
async def get_document(
    document_name: str,
    authorization: Optional[str] = Header(None)
):
    """Get the content of a specific document"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        # Security: Prevent path traversal
        if ".." in document_name or "/" in document_name:
            raise HTTPException(status_code=400, detail="Invalid document name")
        
        p = _app_path(username, document_name)
        
        if not p.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        content = p.read_text()
        
        return {
            "ok": True,
            "name": document_name,
            "content": content,
            "path": str(p)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading document: {str(e)}")
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

#health check endpoints
@app.get("/")
async def root():
    """Root endpoint for health checks"""
    return {"status": "ok", "service": "marimo-api"}

@app.get("/services/marimo-api/")
async def service_root():
    """Endpoint for JupyterHub service health checks"""
    return {"status": "ok", "service": "marimo-api"}
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/server-status")
async def check_server_status(authorization: Optional[str] = Header(None)):
    """Check if user has a running server"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    username = await get_username_from_token(token)
    
    try:
        server_running = await _check_user_server_running(username)
        
        return {
            "ok": True,
            "username": username,
            "server_running": server_running,
            "message": f"Server is {'running' if server_running else 'not running'} for user {username}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking server status: {str(e)}")