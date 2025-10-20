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
      notebook \
      python-dotenv \
      jupyterhub-idle-culler \
      fastapi \
      uvicorn \
      httpx \
      python-multipart \
      "marimo>=0.6.21"

# Remove system Python installations to avoid conflicts
RUN /usr/bin/pip uninstall -y jupyterhub notebook jupyterlab || true

# Create a demo user
RUN useradd -ms /bin/bash demo \
 && mkdir -p /home/demo/work \
 && chown -R demo:demo /home/demo

# Create API directory and copy main.py
RUN mkdir -p /srv/jupyterhub/api
COPY /api/main.py /srv/jupyterhub/api/main.py

# Generate API token at build time and set as environment variable
RUN python3 -c "import secrets; print('HUB_API_TOKEN=' + secrets.token_hex(32))" > /etc/jupyterhub_env \
 && chmod 644 /etc/jupyterhub_env

# Create JupyterHub configuration
RUN cat > /srv/jupyterhub/jupyterhub_config.py <<'EOF'
import os
import sys
import pathlib
from jupyterhub.spawner import LocalProcessSpawner
from jupyterhub.utils import new_token

# Load environment variables from file
with open('/etc/jupyterhub_env', 'r') as f:
    for line in f:
        if '=' in line:
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

# Add the API directory to Python path
sys.path.insert(0, '/srv/jupyterhub/api')

class MarimoSpawner(LocalProcessSpawner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marimo_file = None
        self.marimo_port = None
    
    def load_user_options(self, options):
        super().load_user_options(options)
        self.marimo_file = options.get('marimo_file')
        self.marimo_port = options.get('marimo_port')
    
    def get_env(self):
        env = super().get_env()
        if self.marimo_file and self.marimo_port:
            env['MARIMO_APP_FILE'] = self.marimo_file
            env['MARIMO_PORT'] = str(self.marimo_port)
        return env
    
    def start(self):
        if self.marimo_file and self.marimo_port:
            # Set the command to run marimo directly
            self.cmd = ['/opt/conda/bin/marimo', 'edit', '--port', str(self.marimo_port), self.marimo_file]
            # Ensure the file and directory exist
            path = pathlib.Path(self.marimo_file)
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
        else:
            # Fallback to jupyterlab
            self.cmd = ['/opt/conda/bin/jupyter-labhub']
        return super().start()

# Basic configuration
c.JupyterHub.authenticator_class = 'jupyterhub.auth.DummyAuthenticator'
c.DummyAuthenticator.password = 'demo'

# Spawner configuration
c.JupyterHub.spawner_class = MarimoSpawner
c.Spawner.default_url = '/'

# Get API token from environment
_service_token = new_token()

c.JupyterHub.services = [
    {
        "name": "marimo-api",
        'url': 'http://127.0.0.1:9000',
        'api_token': _service_token,
        'oauth_no_confirm': True,   
        "command": [
            "/opt/conda/bin/python",
            "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--app-dir", "/srv/jupyterhub/api",
        ],
        "environment": {
            "HUB_API_TOKEN": _service_token,
            "FILES_ROOT": "/home",
            "APP_DIRNAME": "apps",
            "DEFAULT_DOC": "welcome_app.py",
            "PUBLIC_HUB_URL": "http://localhost:8000",
        },
        "oauth_no_confirm": True,
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
c.JupyterHub.log_level = 'DEBUG'
c.Spawner.debug = True

# Additional settings for better compatibility
c.Authenticator.admin_users = {'admin'}
c.JupyterHub.admin_access = True

# Increase timeout for spawning
c.Spawner.start_timeout = 120
c.Spawner.http_timeout = 60
EOF

# Create home directory structure
RUN mkdir -p /home && chmod 755 /home

# Create apps directory structure for demo user
RUN mkdir -p /home/demo/apps && chown -R demo:demo /home/demo

# Expose ports
EXPOSE 8000 9000

# Source environment variables and start command
CMD ["/bin/bash", "-c", "set -a && source /etc/jupyterhub_env && set +a && /opt/conda/bin/python -m jupyterhub -f /srv/jupyterhub/jupyterhub_config.py"]