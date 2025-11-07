#sh
config:
    docker-compose down
    docker compose build hub
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

#sh
testDoc:
  curl -i -X POST 'http://localhost:9000/documents' \
    -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldyVWZzelA3YlF5RGZscWEyTEl5ViJ9.eyJpc3MiOiJodHRwczovL2Rldi1tdG1qYzRyd3pqcTRlcnlmLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJhdXRoMHw2OTAxMDM2YzNiOWIxZTIxNDE1MDYzZDUiLCJhdWQiOlsiaHR0cHM6Ly9kZXYtbXRtamM0cnd6anE0ZXJ5Zi51cy5hdXRoMC5jb20vYXBpL3YyLyIsImh0dHBzOi8vZGV2LW10bWpjNHJ3empxNGVyeWYudXMuYXV0aDAuY29tL3VzZXJpbmZvIl0sImlhdCI6MTc2MjAyNTQ5MSwiZXhwIjoxNzYyMTExODkxLCJzY29wZSI6Im9wZW5pZCByZWFkOmN1cnJlbnRfdXNlciB1cGRhdGU6Y3VycmVudF91c2VyX21ldGFkYXRhIiwiYXpwIjoiSkduOURIZ2ZNWlNDdUFOamppSEg4ZEdBM2Q5Wm5GaVcifQ.ZgYR5MSzX9sK0x_x1LekJx7qRpUlmUlC4BXTNkxiqceeqw6mmtMzE550sHOLK5BHBzKaGBSYLAgA3DaR7toifkqZpxyGH71QfD1dofwo4KDXpVoe6DaFx6MOktDC5bKC6dVAsHfR0MwAxvdyE1YnqmD5aFaiXirR84UPkNMg0CiLjdYFilDLGKzRmHIVNWt0w8OMLgXm-TSnkf_HMF_SDalHByhSTf5Qayn3FPMUgVTOnucN6RYA1hnoSIwtGJLM-MSDFQXiNqKTW_v-agfvoUJ_9HTcyOJvblLmnM9E-Mmf1fNhm7JwcgxmmqyBW448LE2naGbpB82FjYd2vUjPEA" \
    -F 'document_name=test.py'

#sh
testSpawn:
  curl -i -X POST 'http://localhost:9000/spawn' \
    -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldyVWZzelA3YlF5RGZscWEyTEl5ViJ9.eyJpc3MiOiJodHRwczovL2Rldi1tdG1qYzRyd3pqcTRlcnlmLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJhdXRoMHw2OTAxMDM2YzNiOWIxZTIxNDE1MDYzZDUiLCJhdWQiOlsiaHR0cHM6Ly9kZXYtbXRtamM0cnd6anE0ZXJ5Zi51cy5hdXRoMC5jb20vYXBpL3YyLyIsImh0dHBzOi8vZGV2LW10bWpjNHJ3empxNGVyeWYudXMuYXV0aDAuY29tL3VzZXJpbmZvIl0sImlhdCI6MTc2MjAyNTQ5MSwiZXhwIjoxNzYyMTExODkxLCJzY29wZSI6Im9wZW5pZCByZWFkOmN1cnJlbnRfdXNlciB1cGRhdGU6Y3VycmVudF91c2VyX21ldGFkYXRhIiwiYXpwIjoiSkduOURIZ2ZNWlNDdUFOamppSEg4ZEdBM2Q5Wm5GaVcifQ.ZgYR5MSzX9sK0x_x1LekJx7qRpUlmUlC4BXTNkxiqceeqw6mmtMzE550sHOLK5BHBzKaGBSYLAgA3DaR7toifkqZpxyGH71QfD1dofwo4KDXpVoe6DaFx6MOktDC5bKC6dVAsHfR0MwAxvdyE1YnqmD5aFaiXirR84UPkNMg0CiLjdYFilDLGKzRmHIVNWt0w8OMLgXm-TSnkf_HMF_SDalHByhSTf5Qayn3FPMUgVTOnucN6RYA1hnoSIwtGJLM-MSDFQXiNqKTW_v-agfvoUJ_9HTcyOJvblLmnM9E-Mmf1fNhm7JwcgxmmqyBW448LE2naGbpB82FjYd2vUjPEA" \
    