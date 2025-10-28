# Base Hub image
FROM quay.io/jupyterhub/jupyterhub:4.1

# Create a Hub config file location
RUN mkdir -p /srv/jupyterhub

# Install system dependencies
RUN apt-get update && apt-get install -y curl

# Install Miniforge
RUN set -eux; \
    arch=$(uname -m); \
    case "${arch}" in \
        x86_64) \
            miniforge_url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"; \
            ;; \
        aarch64) \
            miniforge_url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh"; \
            ;; \
        *) \
            echo "Unsupported architecture: ${arch}"; \
            exit 1; \
            ;; \
    esac; \
    curl -fsSL "$miniforge_url" -o /root/miniforge.sh \
 && chmod +x /root/miniforge.sh \
 && bash /root/miniforge.sh -b -p /opt/conda \
 && rm /root/miniforge.sh

# Add conda to PATH
ENV PATH=/opt/conda/bin:$PATH

# Install ALL packages in conda environment (including jupyterhub)
RUN /opt/conda/bin/pip install --no-cache-dir \
      jupyterhub==4.1.* \
      jupyter-marimo-proxy \
      jupyter-server-proxy \
      jupyterlab \
      pyjwt[crypto] \
      notebook \
      python-dotenv \
      jupyterhub-idle-culler \
      fastapi \
      pyjwt \
      uvicorn \
      httpx \
      python-multipart \
      "marimo>=0.6.21"

# Remove system Python installations to avoid conflicts
RUN /usr/bin/pip uninstall -y jupyterhub notebook jupyterlab || true


 

# install passwd tooling
RUN apt-get update && apt-get install -y --no-install-recommends passwd


# Create API directory and copy main.py
RUN mkdir -p /srv/jupyterhub/api
COPY /api/main.py /srv/jupyterhub/api/main.py
COPY /api/authentication.py /srv/jupyterhub/api/authentication.py
# Generate API token at build time and set as environment variable
RUN python3 -c "import secrets; print('HUB_API_TOKEN=' + secrets.token_hex(32))" > /etc/jupyterhub_env \
 && chmod 644 /etc/jupyterhub_env

# Create JupyterHub configuration
RUN cat > /srv/jupyterhub/jupyterhub_config.py <<'EOF'
# jupyterhub_config.py
import os
import sys
import pathlib
import pwd
import subprocess
from jupyterhub.auth import Authenticator
from jupyterhub.spawner import LocalProcessSpawner
from jupyterhub.utils import new_token
import crypt
import jwt
from jwt import PyJWKClient
import datetime
from dotenv import load_dotenv


# Load environment variables from file, but do NOT overwrite existing runtime env vars
if os.path.exists('/etc/jupyterhub_env'):
    with open('/etc/jupyterhub_env', 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                # Only set if the variable is not already present in the environment
                os.environ.setdefault(key, value)

# Ensure HUB_API_TOKEN exists. If its still missing at runtime, generate one and
# append it to /etc/jupyterhub_env so subsequent restarts can reuse it.
if not os.environ.get('HUB_API_TOKEN'):
    try:
        token = new_token()
        os.environ['HUB_API_TOKEN'] = token
        # Append to file so the token is persisted in the file for future runs
        with open('/etc/jupyterhub_env', 'a') as f:
            f.write(f'HUB_API_TOKEN={token}\n')
    except Exception:
        # If token generation or file write fails, fall back to runtime-only value
        pass

# Add the API directory to Python path
sys.path.insert(0, '/srv/jupyterhub/api')
if not os.environ.get('HUB_API_TOKEN'):
    try:
        token = new_token()
        os.environ['HUB_API_TOKEN'] = token
        # Append to file so the token is persisted in the file for future runs
        with open('/etc/jupyterhub_env', 'a') as f:
            f.write(f'HUB_API_TOKEN={token}\n')
    except Exception:
        # If token generation or file write fails, fall back to runtime-only value
        pass

# Add the API directory to Python path
sys.path.insert(0, '/srv/jupyterhub/api')

# Auth0 Configuration - IMPORTANT: Set these in your .env file
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE')
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else None

# Initialize JWKS client for Auth0 token verification
jwks_client = PyJWKClient(JWKS_URL) if JWKS_URL else None

# Authenticator configuration
class Auth0Authenticator(Authenticator):
    """
    Accepts Bearer tokens issued by Auth0 (RS256).
    Fallback: if token == HUB_API_TOKEN, treat as service user.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.issuer = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else None
        self.audience = AUTH0_AUDIENCE

    async def authenticate(self, handler, data=None):
        # Accept a variety of authorization formats (Bearer, Token, raw token)
        auth_header = handler.request.headers.get('Authorization', '')
        token = ''
        if auth_header:
            parts = auth_header.split(None, 1)
            if len(parts) == 2:
                token = parts[1].strip()
            else:
                token = auth_header.strip()
        else:
            # try query param fallback (e.g. ?token=...)
            try:
                token = handler.get_argument('token', '')
            except Exception:
                token = ''

        if not token:
            return None

        # Service token fallback (JupyterHub API token)
        hub_api_token = os.environ.get('HUB_API_TOKEN')
        if hub_api_token and token == hub_api_token:
            return {
                'name': 'service',
                'auth_state': {'access_token': token, 'user': {'role': 'service'}}
            }

        # Validate JWT with Auth0
        try:
            if not jwks_client:
                raise jwt.InvalidTokenError("Auth0 domain not configured")

            signing_key = jwks_client.get_signing_key_from_jwt(token)
            
            # Build verification parameters
            decode_kwargs = {
                'algorithms': ['RS256'],
                'options': {'verify_aud': False}  # Auth0 tokens might have different audience
            }
            
            if self.issuer:
                decode_kwargs['issuer'] = self.issuer

            decoded = jwt.decode(token, signing_key.key, **decode_kwargs)
            
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            print(f"JWT verification error: {e}")
            return None

        # Map claims to username (common Auth0 claim names)
        # Prefer email as username since its consistent
        username = decoded.get('email') or decoded.get('preferred_username') or decoded.get('nickname') or decoded.get('sub')
        if not username:
            print("No username found in token claims")
            return None

        # Sanitize username for system use (remove special characters)
        username = self.sanitize_username(username)
        
        print(f"Authenticated user: {username}")

        return {
            'name': username,
            'auth_state': {
                'access_token': token,
                'user': decoded
            }
        }
    
    def sanitize_username(self, username):
        """Sanitize username for system use"""
        # Replace @ with -at- and remove other special characters
        sanitized = username.replace('@', '-at-').replace('.', '-').lower()
        # Remove any remaining non-alphanumeric characters except hyphens
        import re
        sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)
        return sanitized


# Spawner class
class MarimoSpawner(LocalProcessSpawner):
    marimo_file: str|None = None
    marimo_port: int|None = None
    marimo_proc = None

    def options_from_form(self, formdata):
        return {}

    def load_user_options(self, options):
        super().load_user_options(options)
        self.marimo_file = options.get("marimo_file")
        self.marimo_port = int(options.get("marimo_port")) if options.get("marimo_port") else None

    def ensure_user_exists(self):
        """Ensure system user exists"""
        username = self.user.name
        try:
            pwd.getpwnam(username)
        except KeyError:
            # User doesnt exist, create it
            home_dir = f"/home/{username}"
            subprocess.check_call([
                'useradd',
                '-m',  # Create home directory
                '-d', home_dir,  # Home directory
                '-s', '/bin/bash',  # Shell
                username
            ])
            # Set proper permissions
            subprocess.check_call(['chmod', '755', home_dir])

    def _user_home(self, username: str):
        """Helper function to get user home directory"""
        return pathlib.Path("/home") / username

    async def start(self):
        # Ensure user exists
        self.ensure_user_exists()
        
        # Ensure log dir
        os.makedirs("/var/log/jupyterhub/users", exist_ok=True)

        # If front-end passed a target Marimo notebook, set the default URL to open it in JupyterLab
        if self.marimo_file:
            path = pathlib.Path(self.marimo_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("import marimo as mo\napp = mo.App()\n")

            # Construct URL to open the file in JupyterLab
            file_path_relative = str(path.relative_to(self._user_home(self.user.name)))
            self.default_url = f"/lab/tree/{file_path_relative}"
            
            print(f"DEBUG: Setting default URL to open in JupyterLab: {self.default_url}")

        else:
            # fallback to regular JupyterLab home
            self.default_url = "/lab"

        # now start the real single-user server that JupyterHub manages
        return await super().start()

# Basic configuration
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = 8000

# Authenticator
c.JupyterHub.authenticator_class = TokenAuthenticator

# Allow token authentication
c.TokenAuthenticator.enable_auth_state = True

# Spawner configuration
c.JupyterHub.spawner_class = MarimoSpawner
c.Spawner.default_url = '/'

# Get API token from environment
_service_token = os.environ.get('HUB_API_TOKEN', new_token())

c.JupyterHub.services = [
    {
        "name": "marimo-api",
        'url': 'http://127.0.0.1:9000',
        'api_token': _service_token,
        "command": [
            "/opt/conda/bin/python",
            "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--app-dir", "/srv/jupyterhub/api",
        ],
        "environment": {
            "HUB_API_TOKEN": _service_token,
            "HUB_URL": "http://127.0.0.1:8000",
            "FILES_ROOT": "/home",
            "APP_DIRNAME": "apps",
            "DEFAULT_DOC": "welcome_app.py",
            "PUBLIC_HUB_URL": "http://localhost:8000",
        },
    }
]

# Grant scopes to that service via a role
c.JupyterHub.load_roles = [
    {
        "name": "marimo-api-role",
        "scopes": [
            "read:users",
            "admin:users",
            "read:servers", 
            "admin:servers",
            "servers",
        ],
        "services": ["marimo-api"],
    }
]

# Use conda Python for everything
c.Spawner.cmd = ['/opt/conda/bin/jupyter-labhub']
c.LocalProcessSpawner.shell_cmd = ['/bin/bash', '-l', '-c']

# Allow all origins for development
c.JupyterHub.tornado_settings = {
    'headers': {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': '*',
        'Access-Control-Allow-Headers': '*',
    }
}

# Debug logging
c.JupyterHub.extra_log_file = "/var/log/jupyterhub/jupyterhub.log"
c.JupyterHub.log_level = 'DEBUG'
c.Spawner.debug = True

# Additional settings for better compatibility
c.Authenticator.admin_users = {'admin'}
c.JupyterHub.admin_access = True

# Increase timeout for spawning
c.Spawner.start_timeout = 600
c.Spawner.http_timeout = 300

# Set spawner working directory
c.Spawner.notebook_dir = '~'
EOF

# Create token API endpoint



# Create home directory structure
RUN mkdir -p /home && chmod 755 /home


# Expose ports
EXPOSE 8000 9000

# Source environment variables and start command
CMD ["/bin/bash", "-c", "set -a && source /etc/jupyterhub_env && set +a && /opt/conda/bin/python -m jupyterhub -f /srv/jupyterhub/jupyterhub_config.py &>> /var/log/jupyterhub/jupyterhub.log"]