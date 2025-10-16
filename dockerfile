# Base Hub image (includes configurable-http-proxy & jupyterhub)
FROM quay.io/jupyterhub/jupyterhub:4.1

# Create a Hub config file location
RUN mkdir -p /srv/jupyterhub \
 && jupyterhub --generate-config -f /srv/jupyterhub/jupyterhub_config.py

# Install jupyterlab, notebook, jupyter-server-proxy, jupyter-marimo-proxy
RUN /usr/bin/pip install --no-cache-dir \
      jupyter-marimo-proxy \
      jupyter-server-proxy \
      jupyterlab \
      notebook

# Install Miniforge for the correct architecture
# Detect the architecture and download the appropriate Miniforge
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

# Add conda to PATH for both system and user environments
ENV PATH=/opt/conda/bin:$PATH

# Install Marimo in the user Python environment
RUN /opt/conda/bin/pip install --no-cache-dir "marimo>=0.6.21"

# Create a demo user (works with DummyAuthenticator)
RUN useradd -ms /bin/bash demo \
 && mkdir -p /home/demo/work \
 && chown -R demo:demo /home/demo

# Configure JupyterHub
RUN cat >> /srv/jupyterhub/jupyterhub_config.py <<'EOF'
c.JupyterHub.authenticator_class = 'dummy'
c.DummyAuthenticator.password = 'demo'
c.JupyterHub.spawner_class = 'jupyterhub.spawner.LocalProcessSpawner'
c.Spawner.default_url = '/lab'
c.Spawner.cmd = ['jupyter-labhub']
EOF

# Expose Hub port
EXPOSE 8000