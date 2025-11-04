import os
import sys
import pathlib
import pwd
import subprocess
from jupyterhub.spawner import LocalProcessSpawner
from jupyterhub.utils import new_token
import json
import time
import urllib.request
from jose import jwt
from oauthenticator.auth0 import Auth0OAuthenticator  # CORRECTED IMPORT

c = get_config()

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
# if not os.environ.get('HUB_API_TOKEN'):
#     try:
#         token = new_token()
#         os.environ['HUB_API_TOKEN'] = token
#         # Append to file so the token is persisted in the file for future runs
#         with open('/etc/jupyterhub_env', 'a') as f:
#             f.write(f'HUB_API_TOKEN={token}\n')
#     except Exception:
#         # If token generation or file write fails, fall back to runtime-only value
#         pass

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

###############################
# Auth0 configuration
################################
# Use built-in Auth0 authenticator
c.JupyterHub.authenticator_class = Auth0OAuthenticator

# Auth0 configuration
c.Auth0OAuthenticator.oauth_callback_url = os.environ["AUTH_CALLBACK_URL"]
c.Auth0OAuthenticator.client_id = os.environ["AUTH_CLIENT_ID"]
c.Auth0OAuthenticator.client_secret = os.environ["AUTH_CLIENT_SECRET"]
c.Auth0OAuthenticator.scope = ['openid', 'profile', 'email']
c.Auth0OAuthenticator.audience = os.environ["AUTH_AUDIENCE"]

# The domain from your Auth0 application
c.Auth0OAuthenticator.auth0_subdomain = os.environ["AUTH_DOMAIN"].split('.')[0]


###############################
# Spawner class
###############################
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
            "AUTH_DOMAIN": os.environ.get("AUTH_DOMAIN"),
            "AUTH_AUDIENCE": os.environ.get("AUTH_AUDIENCE"),
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