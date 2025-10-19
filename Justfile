#sh
config:
    docker-compose down
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

#sh
test-api username:
    #!/usr/bin/env bash
    set -euo pipefail

    # Name of your Hub container in Docker (adjust if different)
    HUB_CONTAINER="jupyterhub-marimo"

    #test create user
    echo "testing user creation via API..."
    curl -X POST -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username={{username}}" http://localhost:9000/users
    echo
    
    #test marimo spawn
    echo "🧪 Testing marimo spawn via marimo-api..."
    curl -fsS -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=${USERNAME}" \
      http://localhost:9000/spawn || true
    echo

    # Clean up by deleting the test user
    echo "Cleaning up: deleting test user..."
    curl -X DELETE -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username={{username}}" http://localhost:9000/users
    echo "Cleanup completed."


      