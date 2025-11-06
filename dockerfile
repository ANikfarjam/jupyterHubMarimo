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
      python-multipart \
      jupyterhub-idle-culler \
      fastapi \
      python-jose[cryptography] \
      uvicorn \
      httpx \
      python-multipart \
      "marimo>=0.6.21" \
      oauthenticator

# Remove system Python installations to avoid conflicts
RUN /usr/bin/pip uninstall -y jupyterhub notebook jupyterlab || true

# install passwd tooling
RUN apt-get update && apt-get install -y --no-install-recommends passwd

# Create necessary directories
RUN mkdir -p /srv/jupyterhub/api /var/log/jupyterhub /home

# Copy API and config files
COPY api/main.py /srv/jupyterhub/api/main.py
COPY config/jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py

# Create initial environment file (token will be generated at runtime)
RUN touch /etc/jupyterhub_env && chmod 644 /etc/jupyterhub_env

# Set proper permissions
RUN chmod 755 /home

# Expose ports
EXPOSE 8000 9000

# Start both JupyterHub and the API service
CMD ["/bin/bash", "-c", "set -a && source /etc/jupyterhub_env && set +a && /opt/conda/bin/python -m jupyterhub -f /srv/jupyterhub/jupyterhub_config.py"]