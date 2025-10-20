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
test-api username docname:
    #!/usr/bin/env bash
    set -euo pipefail

    HUB_CONTAINER="jupyterhub-marimo"
    USERNAME="{{username}}"
    DOCNAME="{{docname}}"

    echo "Testing user creation via marimo-api..."
    curl -fsS -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=${USERNAME}" \
      http://localhost:9000/users || true
    echo

    echo "Creating Marimo document '${DOCNAME}' for user '${USERNAME}'..."
    curl -fsS -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=${USERNAME}&document_name=${DOCNAME}" \
      http://localhost:9000/documents || true
    echo

    echo "Getting Marimo document '${DOCNAME}' for user '${USERNAME}'..."
    curl -fsS -X GET \
      -H "Content-Type: application/x-www-form-urlencoded" \
      "http://localhost:9000/documents?username=${USERNAME}" || true
    echo

    echo "✅ Test completed for user '${USERNAME}' and document '${DOCNAME}'."

    echo "Cleaning up: deleting test document..."
    curl -fsS -X DELETE \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-urlencode "username=${USERNAME}" \
      --data-urlencode "document_name=${DOCNAME}" \
      http://localhost:9000/documents || true
    echo

    echo "Cleaning up: deleting test user..."
    curl -fsS -X DELETE \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-urlencode "username=${USERNAME}" \
      "http://localhost:9000/users/${USERNAME}" || true
    echo

    echo "Cleanup completed."