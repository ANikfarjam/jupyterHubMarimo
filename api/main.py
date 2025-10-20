# main.py
import os
import json
import socket
import pathlib
import secrets
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Form, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv
import logging

load_dotenv()

# Environment variables
HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8081")
HUB_API_TOKEN = os.getenv("HUB_API_TOKEN") 
FILES_ROOT = os.getenv("FILES_ROOT", "/home")
APP_DIRNAME = os.getenv("APP_DIRNAME", "apps")
DEFAULT_DOC = os.getenv("DEFAULT_DOC", "welcome_app.py")

app = FastAPI(title="Marimo API", description="API for managing JupyterHub users and Marimo apps")

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _ensure_user_directory(username: str):
    """Ensure user home directory exists and has correct permissions"""
    user_home = _user_home(username)
    apps_dir = user_home / APP_DIRNAME
    
    # Create directories if they don't exist
    user_home.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)
    
    # Set proper permissions (assuming user will be created with same UID)
    # In production, you might want to match UID/GID with system user
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

async def _ensure_user_exists(username: str):
    """Ensure user exists in JupyterHub and directories are setup"""
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
                if r.status_code not in (201, 409):  # 409 = already exists (race condition)
                    raise HTTPException(r.status_code, f"Failed to create user: {r.text}")
            
            # Ensure user directories exist
            _ensure_user_directory(username)
            
    except Exception as e:
        if not isinstance(e, HTTPException):
            raise HTTPException(500, f"Error ensuring user exists: {str(e)}")
        raise e

@app.post("/users")
async def create_user(username: str = Form(...)):
    """Create a new JupyterHub user"""
    try:
        await _ensure_user_exists(username)
        return {"ok": True, "message": f"User {username} created successfully"}
    except Exception as e:
        raise HTTPException(500, f"Error creating user: {str(e)}")

@app.get("/users")
async def list_users() -> List[str]:
    """List all JupyterHub users"""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HUB_URL}/hub/api/users", headers=_hub_headers())
            r.raise_for_status()
            users_data = r.json()
            return [u["name"] for u in users_data]
    except Exception as e:
        raise HTTPException(500, f"Error fetching users: {str(e)}")

@app.delete("/users/{username}")
async def delete_user(username: str):
    """Delete a JupyterHub user"""
    try:
        async with httpx.AsyncClient() as client:
            # Stop server first if running
            await client.delete(
                f"{HUB_URL}/hub/api/users/{username}/server", 
                headers=_hub_headers()
            )
            # Then delete user
            r = await client.delete(
                f"{HUB_URL}/hub/api/users/{username}", 
                headers=_hub_headers()
            )
            
            if r.status_code in (204, 404):
                # Also remove user directory (optional)
                user_home = _user_home(username)
                if user_home.exists():
                    import shutil
                    shutil.rmtree(user_home)
                return {"ok": True, "message": f"User {username} deleted successfully"}
            else:
                raise HTTPException(r.status_code, f"Failed to delete user: {r.text}")
                
    except Exception as e:
        raise HTTPException(500, f"Error deleting user: {str(e)}")

@app.post("/documents")
async def create_document(
    username: str = Form(...), 
    document_name: str = Form(...)
):
    """Create a new Marimo document for a user"""
    try:
        # Ensure user exists first
        await _ensure_user_exists(username)
        
        p = _app_path(username, document_name)
        _ensure_marimo_file(p)
        return {"ok": True, "path": str(p), "message": f"Document {document_name} created for user {username}"}
    except Exception as e:
        raise HTTPException(500, f"Error creating document: {str(e)}")

@app.get("/documents")
async def list_documents(username: str = Query(...)):
    """List all documents for a user"""
    try:
        d = _user_home(username) / APP_DIRNAME
        if not d.exists():
            return []
        return [p.name for p in d.glob("*.py") if p.is_file()]
    except Exception as e:
        raise HTTPException(500, f"Error listing documents: {str(e)}")

@app.delete("/documents")
async def delete_document(
    username: str = Form(...), 
    document_name: str = Form(...)
):
    """Delete a user's document"""
    try:
        p = _app_path(username, document_name)
        if p.exists():
            p.unlink()
            return {"ok": True, "message": f"Document {document_name} deleted for user {username}"}
        else:
            raise HTTPException(404, f"Document {document_name} not found for user {username}")
    except Exception as e:
        raise HTTPException(500, f"Error deleting document: {str(e)}")

@app.post("/spawn")
async def spawn_user_and_redirect(
    username: str = Form(...), 
    document_name: Optional[str] = Form(None)
):
    """Spawn a Marimo notebook for a user"""
    try:
        # Ensure user exists and directories are setup
        await _ensure_user_exists(username)
        
        # Ensure document exists
        doc = document_name or DEFAULT_DOC
        p = _app_path(username, doc)
        _ensure_marimo_file(p)

        # Allocate a marimo port
        marimo_port = _pick_free_port()
        user_options = {
            "marimo_file": str(p),
            "marimo_port": marimo_port,
        }

        async with httpx.AsyncClient() as client:
            # Stop any existing server first
            await client.delete(
                f"{HUB_URL}/hub/api/users/{username}/server",
                headers=_hub_headers(),
            )
            
            # Start the server with marimo options
            r = await client.post(
                f"{HUB_URL}/hub/api/users/{username}/server",
                headers=_hub_headers(),
                json=user_options,
                timeout=30.0  # Add timeout
            )
            
            if r.status_code not in (201, 202):
                raise HTTPException(r.status_code, f"Failed to spawn server: {r.text}")

        # Wait a moment for server to start
        await asyncio.sleep(2)

        # Construct redirect URL
        public_hub = os.getenv("PUBLIC_HUB_URL", "http://localhost:8000")
        target = f"{public_hub}/user/{username}/proxy/{marimo_port}/"
        
        return {
            "ok": True,
            "redirect": target, 
            "username": username, 
            "document": doc, 
            "port": marimo_port,
            "message": f"Marimo notebook spawned successfully for {username}"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error spawning notebook: {str(e)}")

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