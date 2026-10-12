#!/usr/bin/env bash
# deploy/mirror/setup-mirror.sh — Setup and populate air-gapped image mirror
set -euo pipefail

REGISTRY_NAME="${REGISTRY_NAME:-argus-mirror-registry}"
REGISTRY_PORT="${REGISTRY_PORT:-5001}"
REGISTRY_HOST="${REGISTRY_HOST:-localhost}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-${REGISTRY_HOST}:${REGISTRY_PORT}}"
IMAGES_FILE="${1:-deploy/mirror/images.txt}"

echo "=== [setup-mirror] Setting up internal registry mirror on ${MIRROR_REGISTRY} ==="

# 1. Start internal registry if not already running
if ! docker ps --filter "name=^/${REGISTRY_NAME}$" --format '{{.Names}}' | grep -q "^${REGISTRY_NAME}$"; then
  if docker ps -a --filter "name=^/${REGISTRY_NAME}$" --format '{{.Names}}' | grep -q "^${REGISTRY_NAME}$"; then
    echo "Starting existing registry container ${REGISTRY_NAME}..."
    docker start "${REGISTRY_NAME}" >/dev/null
  else
    echo "Creating and starting registry container ${REGISTRY_NAME} on port ${REGISTRY_PORT}..."
    docker run -d --name "${REGISTRY_NAME}" --restart=always -p "${REGISTRY_PORT}:5000" registry:2.8.3 >/dev/null
  fi
fi

# 2. Wait for registry to be responsive
echo "Checking registry connectivity..."
READY=false
for i in $(seq 1 15); do
  if curl -s -f "http://${REGISTRY_HOST}:${REGISTRY_PORT}/v2/" >/dev/null 2>&1; then
    READY=true
    break
  fi
  sleep 1
done

if [ "$READY" != "true" ]; then
  echo "ERROR: Internal registry at http://${REGISTRY_HOST}:${REGISTRY_PORT}/v2/ is not responding." >&2
  exit 1
fi
echo "Internal registry is healthy."

# 3. Process image list
if [ ! -f "$IMAGES_FILE" ]; then
  echo "ERROR: Images file ${IMAGES_FILE} not found." >&2
  exit 1
fi

echo "Mirroring images from ${IMAGES_FILE} to ${MIRROR_REGISTRY}/argus/..."
while IFS= read -r line || [ -n "$line" ]; do
  # Skip comments and empty lines
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue

  SRC_IMAGE="$line"
  # Extract image name and tag
  # e.g., ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.160.0 -> opentelemetry-operator:0.160.0
  IMG_NAME_TAG="${SRC_IMAGE##*/}"
  DST_IMAGE="${MIRROR_REGISTRY}/argus/${IMG_NAME_TAG}"

  echo "--> Mirroring: ${SRC_IMAGE} -> ${DST_IMAGE}"
  if ! docker image inspect "${SRC_IMAGE}" >/dev/null 2>&1; then
    echo "    Pulling upstream: ${SRC_IMAGE}"
    docker pull "${SRC_IMAGE}"
  fi

  docker tag "${SRC_IMAGE}" "${DST_IMAGE}"
  docker push "${DST_IMAGE}"
done < "$IMAGES_FILE"

echo "=== [setup-mirror] Mirror populated successfully ==="
echo "Catalog in mirror:"
curl -s "http://${REGISTRY_HOST}:${REGISTRY_PORT}/v2/_catalog" | jq . 2>/dev/null || curl -s "http://${REGISTRY_HOST}:${REGISTRY_PORT}/v2/_catalog"
echo ""
