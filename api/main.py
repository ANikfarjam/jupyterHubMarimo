# main.py
import pwd, grp
import os, stat
import json
import socket
import pathlib
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Form, Query, Depends 
from authentication import verify_auth0_token, verify_service_token
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv


load_dotenv()

# Environment variables
HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8000")
HUB_API_TOKEN = os.getenv("HUB_API_TOKEN")  
FILES_ROOT = os.getenv("FILES_ROOT", "/home")  
APP_DIRNAME = os.getenv("APP_DIRNAME", "apps")  
DEFAULT_DOC = os.getenv("DEFAULT_DOC", "welcome_app.py")  
PUBLIC_HUB_URL = os.getenv("PUBLIC_HUB_URL", "http://localhost:8000")

app = FastAPI(title="Marimo API", description="API for managing JupyterHub users and Marimo apps")

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

###########################    
# Utils functions 
###########################
def get_authenticated_user(user_info: dict = Depends(verify_auth0_token)):
    """Get authenticated username from Auth0 token"""
    return user_info['username']

def _hub_headers():
    if not HUB_API_TOKEN:
        raise RuntimeError("HUB_API_TOKEN not set")
    return {
        "Authorization": f"token {HUB_API_TOKEN}",
        "Content-Type": "application/json"
    }

def _user_home(username: str) -> pathlib.Path:
    return pathlib.Path(FILES_ROOT) / username

def _app_path(username: str, document_name: str) -> pathlib.Path:
    return _user_home(username) / APP_DIRNAME / document_name

def _get_uid_gid(username: str) -> tuple[int, int]:
    pw = pwd.getpwnam(username)  # raises KeyError if user doesn't exist yet
    return pw.pw_uid, pw.pw_gid

def _chown_recursive(path: pathlib.Path, uid: int, gid: int):
    for root, dirs, files in os.walk(path, topdown=True):
        os.chown(root, uid, gid)
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)
        for f in files:
            os.chown(os.path.join(root, f), uid, gid)

def _ensure_user_directory(username: str, uid: Optional[int] = None, gid: Optional[int] = None):
    """Ensure user home/apps exist and are owned by the user."""
    user_home = _user_home(username)
    apps_dir = user_home / APP_DIRNAME

    # Create if missing (may be root-owned at first)
    user_home.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    # If we know uid/gid, chown recursively
    if uid is not None and gid is not None:
        _chown_recursive(user_home, uid, gid)

    # Mode bits are fine, but ownership is what matters
    user_home.chmod(0o755)
    apps_dir.chmod(0o755)


def _ensure_marimo_file(path: pathlib.Path):
    """Create marimo file if it doesn't exist"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('''import marimo

__file__ = marimo.__file__

app = marimo.App()

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

def _pick_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def _normalize_notebook_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    if not name:
        raise HTTPException(status_code=400, detail="document_name required")
    if not name.endswith(".py"):
        name += ".py"
    # Disallow directory traversal
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="document_name must be a file name, not a path")
    return name

async def _wait_for_server(username: str, timeout_s: int = 300, interval_s: float = 2.0):
    """
    Wait until the default server ('') is ready.
    If spawn fails, raise with a meaningful message from spawner state.
    """
    async with httpx.AsyncClient() as client:
        deadline = asyncio.get_event_loop().time() + timeout_s
        while True:
            r = await client.get(f"{HUB_URL}/hub/api/users/{username}", headers=_hub_headers())
            r.raise_for_status()
            u = r.json()
            servers = u.get("servers") or {}
            default = servers.get("") or {}

            if default.get("ready") is True:
                return

            # Look for explicit failure clues
            state = default.get("state") or {}
            status = state.get("status")
            failed = state.get("failed")
            exit_code = state.get("exit_code")
            if failed or status == "failed" or (isinstance(exit_code, int) and exit_code != 0):
                msg = state.get("message") or state.get("reason") or "spawn failed"
                raise HTTPException(status_code=502, detail=f"Single-user server failed to start: {msg}")

            if asyncio.get_event_loop().time() > deadline:
                pending = default.get("pending")
                brief = {k: v for k, v in state.items() if k in ("status", "message", "reason", "exit_code")}
                raise HTTPException(status_code=504, detail=f"Timed out waiting for server (pending={pending}, state={brief})")

            await asyncio.sleep(interval_s)


async def _ensure_user_exists(username: str, password: Optional[str] = None):
    """Ensure JupyterHub user exists and the filesystem is owned by that user."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HUB_URL}/hub/api/users/{username}", headers=_hub_headers())
            if r.status_code == 404:
                r = await client.post(f"{HUB_URL}/hub/api/users/{username}", headers=_hub_headers())
                if r.status_code not in (201, 409):
                    raise HTTPException(r.status_code, f"Failed to create user: {r.text}")
            elif r.status_code != 200:
                r.raise_for_status()

        # At this point, the PAMAuthenticator has created the OS user (same host/container).
        # Lookup uid/gid and ensure directories are owned by that user:
        try:
            uid, gid = _get_uid_gid(username)
        except KeyError:
            # If the OS user isn't present yet for some reason, fall back to making dirs without chown
            uid = gid = None

        _ensure_user_directory(username, uid, gid)

    except Exception as e:
        if not isinstance(e, HTTPException):
            raise HTTPException(500, f"Error ensuring user exists: {str(e)}")
        raise

###########################
# API Endpoints
###########################
@app.post("/users")
async def create_user(
    username: str = Form(...),
    authenticated_user: str = Depends(get_authenticated_user)
):
    """Create a new JupyterHub user (uses authenticated username from Auth0)"""
    try:
        # Use the authenticated username from Auth0 token
        await _ensure_user_exists(authenticated_user)
        return {"ok": True, "message": f"User {authenticated_user} created successfully"}
    except Exception as e:
        raise HTTPException(500, f"Error creating user: {str(e)}")

@app.get("/users")
async def list_users(verified: bool = Depends(verify_service_token)):
    """List all JupyterHub users (service endpoint)"""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HUB_URL}/hub/api/users", headers=_hub_headers())
            r.raise_for_status()
            users_data = r.json()
            return [u["name"] for u in users_data]
    except Exception as e:
        raise HTTPException(500, f"Error fetching users: {str(e)}")

@app.post("/documents")
async def create_document(
    document_name: str = Form(...),
    authenticated_user: str = Depends(get_authenticated_user)
):
    """Create a new Marimo document for the authenticated user"""
    try:
        # Use the authenticated username from Auth0 token
        await _ensure_user_exists(authenticated_user)
        
        p = _app_path(authenticated_user, document_name)
        _ensure_marimo_file(p)
        return {"ok": True, "path": str(p), "message": f"Document {document_name} created for user {authenticated_user}"}
    except Exception as e:
        raise HTTPException(500, f"Error creating document: {str(e)}")

@app.get("/documents")
async def list_documents(authenticated_user: str = Depends(get_authenticated_user)):
    """List all documents for the authenticated user"""
    try:
        d = _user_home(authenticated_user) / APP_DIRNAME
        if not d.exists():
            return []
        return [p.name for p in d.glob("*.py") if p.is_file()]
    except Exception as e:
        raise HTTPException(500, f"Error listing documents: {str(e)}")

@app.delete("/documents")
async def delete_document(
    document_name: str = Form(...),
    authenticated_user: str = Depends(get_authenticated_user)
):
    """Delete the authenticated user's document"""
    try:
        p = _app_path(authenticated_user, document_name)
        if p.exists():
            p.unlink()
            return {"ok": True, "message": f"Document {document_name} deleted for user {authenticated_user}"}
        else:
            raise HTTPException(404, f"Document {document_name} not found for user {authenticated_user}")
    except Exception as e:
        raise HTTPException(500, f"Error deleting document: {str(e)}")

@app.post("/spawn")
async def spawn_user_and_redirect(
    document_name: Optional[str] = Form(None),
    authenticated_user: str = Depends(get_authenticated_user)
):
    """
    Spawn the authenticated user's server and open the Marimo app in JupyterLab
    """
    try:
        # Use the authenticated username from Auth0 token
        username = authenticated_user
        
        # 1) Ensure user + dirs
        await _ensure_user_exists(username)

        # 2) Ensure Marimo file under ~/APP_DIRNAME
        doc = _normalize_notebook_name(document_name or DEFAULT_DOC)
        marimo_path = _app_path(username, doc)
        _ensure_marimo_file(marimo_path)

        # ... (rest of your existing spawn function remains the same)
        
        # 7) Return the JupyterLab URL
        redirect = f"{PUBLIC_HUB_URL}/user/{username}/lab"
        if token:
            redirect = f"{redirect}?token={token}"
        return {
            "ok": True,
            "redirect": redirect,
            "username": username,
            "document": doc,
            "message": "Server ready; opening JupyterLab with Marimo file.",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error spawning server: {str(e)}")

    
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "marimo-api"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Marimo API Server", 
        "version": "1.0",
        "endpoints": {
            "users": "/users",
            "documents": "/documents", 
            "spawn": "/spawn"
        }
    }