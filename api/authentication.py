# authentication.py (UPDATED)
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import os
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

app = FastAPI()
security = HTTPBearer()

class TokenResponse(BaseModel):
    token: str
    username: str
    expires_at: str

# Auth0 Configuration
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE')
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else None

# Initialize JWKS client for Auth0 token verification
jwks_client = PyJWKClient(JWKS_URL) if JWKS_URL else None

def verify_auth0_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Auth0 JWT tokens"""
    token = credentials.credentials
    
    if not AUTH0_DOMAIN:
        raise HTTPException(status_code=500, detail="Auth0 domain not configured")
    
    try:
        # Verify token using Auth0's public keys
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        
        # Extract user information from Auth0 token
        username = payload.get('email') or payload.get('sub') or payload.get('preferred_username')
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token: no user identifier")
            
        return {
            'username': username,
            'email': payload.get('email'),
            'name': payload.get('name'),
            'payload': payload
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

# Service token fallback (for internal API calls)
def verify_service_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    hub_token = os.environ.get('HUB_API_TOKEN')
    if not hub_token:
        raise HTTPException(status_code=500, detail="Service token not configured")
    if credentials.credentials != hub_token:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return True

@app.get("/verify-token")
async def verify_token(user_info: dict = Depends(verify_auth0_token)):
    """Verify Auth0 token and return user info"""
    return {
        "authenticated": True,
        "user": user_info['username'],
        "email": user_info.get('email'),
        "name": user_info.get('name')
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}