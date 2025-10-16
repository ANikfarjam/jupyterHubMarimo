#sh
config:
    docker compose build --no-cache hub
    docker compose up -d

#sh    
clean-ports:
    # sudo lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sudo lsof -ti:8001 | xargs kill -9 2>/dev/null || true
    sudo lsof -ti:8082 | xargs kill -9 2>/dev/null || true
    echo "Stopping and removing JupyterHub container..."
    docker compose down
    echo "Cleanup complete."