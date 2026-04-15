#!/bin/bash
# Paper Pulse - Build and push Docker image to Docker Hub
# Usage: ./scripts/build-and-push.sh [tag]
# Builds for linux/amd64 (NAS/x86_64 servers)

set -e

IMAGE_NAME="yourname/paper-pulse"
TAG="${1:-latest}"
PLATFORM="linux/amd64"

echo "=============================================="
echo "Building and pushing ${IMAGE_NAME}:${TAG}"
echo "Platform: ${PLATFORM}"
echo "=============================================="

# Navigate to project root
cd "$(dirname "$0")/.."

# Build the image for amd64
echo ""
echo "[1/3] Building Docker image for ${PLATFORM}..."
docker build --platform "${PLATFORM}" -t "${IMAGE_NAME}:${TAG}" .

# Tag as latest if building a versioned tag
if [ "$TAG" != "latest" ]; then
    echo ""
    echo "[2/3] Tagging as latest..."
    docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_NAME}:latest"
fi

# Push to Docker Hub
echo ""
echo "[3/3] Pushing to Docker Hub..."
docker push "${IMAGE_NAME}:${TAG}"

if [ "$TAG" != "latest" ]; then
    docker push "${IMAGE_NAME}:latest"
fi

echo ""
echo "=============================================="
echo "Done! Image pushed to Docker Hub:"
echo "  ${IMAGE_NAME}:${TAG}"
if [ "$TAG" != "latest" ]; then
    echo "  ${IMAGE_NAME}:latest"
fi
echo "=============================================="
