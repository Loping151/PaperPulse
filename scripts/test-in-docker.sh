#!/bin/bash
# Test sources in Docker container
# Usage:
#   ./scripts/test-in-docker.sh           # Test all sources
#   ./scripts/test-in-docker.sh --no-pdf  # Skip PDF tests
#   ./scripts/test-in-docker.sh --source biorxiv  # Test single source

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Build image if needed
echo "Building Docker image..."
docker build -t paper-pulse-test -f Dockerfile .

echo ""
echo "Running tests in Docker..."
echo ""

# Run tests (override entrypoint to run test script directly)
docker run --rm \
    --entrypoint python \
    -v "$PROJECT_DIR/config.yaml:/app/config.yaml:ro" \
    -v "$PROJECT_DIR/scripts:/app/scripts:ro" \
    paper-pulse-test \
    scripts/test_sources.py "$@"
