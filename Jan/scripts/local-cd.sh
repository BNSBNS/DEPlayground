#!/bin/bash
# Local CD Simulation Script
# Question 13: Demonstrate zero-downtime deployment
#
# This script simulates a CD flow:
# 1. Build new Docker images
# 2. Load images into Kind cluster
# 3. Perform rolling update
# 4. Verify deployment health

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CLUSTER_NAME="${CLUSTER_NAME:-trading-cluster}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"

echo "=== Local CD Simulation for Energy Trading Platform ==="
echo "Image tag: ${IMAGE_TAG}"
echo ""

# Check prerequisites
command -v kind >/dev/null 2>&1 || {
    echo "Error: kind is not installed."
    exit 1
}

command -v docker >/dev/null 2>&1 || {
    echo "Error: docker is not installed."
    exit 1
}

# Verify cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Error: Kind cluster '${CLUSTER_NAME}' not found."
    echo "Run ./scripts/setup-kind.sh first."
    exit 1
fi

# Set kubectl context
kubectl config use-context "kind-${CLUSTER_NAME}"

cd "$PROJECT_DIR"

# ==========================================================================
# Step 1: Build Docker Images
# ==========================================================================
echo ""
echo "=== Step 1: Building Docker Images ==="

echo "Building producer image..."
docker build \
    -t "energy-trading-platform/producer:${IMAGE_TAG}" \
    -f docker/producer/Dockerfile \
    .

echo "Building consumer image..."
docker build \
    -t "energy-trading-platform/consumer:${IMAGE_TAG}" \
    -f docker/consumer/Dockerfile \
    .

echo "Images built successfully."

# ==========================================================================
# Step 2: Load Images into Kind
# ==========================================================================
echo ""
echo "=== Step 2: Loading Images into Kind Cluster ==="

kind load docker-image "energy-trading-platform/producer:${IMAGE_TAG}" --name "$CLUSTER_NAME"
kind load docker-image "energy-trading-platform/consumer:${IMAGE_TAG}" --name "$CLUSTER_NAME"

echo "Images loaded into cluster."

# ==========================================================================
# Step 3: Perform Rolling Update
# ==========================================================================
echo ""
echo "=== Step 3: Performing Rolling Update ==="

# Update producer deployment
echo "Updating producer deployment..."
kubectl set image deployment/trade-producer \
    producer="energy-trading-platform/producer:${IMAGE_TAG}" \
    -n trading \
    --record || {
        echo "Producer deployment not found. Applying manifests..."
        kubectl apply -f k8s/producer/
    }

# Update consumer deployment
echo "Updating consumer deployment..."
kubectl set image deployment/trade-consumer \
    consumer="energy-trading-platform/consumer:${IMAGE_TAG}" \
    -n trading \
    --record || {
        echo "Consumer deployment not found. Applying manifests..."
        kubectl apply -f k8s/consumer/
    }

# ==========================================================================
# Step 4: Wait for Rollout
# ==========================================================================
echo ""
echo "=== Step 4: Waiting for Rollout to Complete ==="

echo "Waiting for producer rollout..."
kubectl rollout status deployment/trade-producer -n trading --timeout=120s || true

echo "Waiting for consumer rollout..."
kubectl rollout status deployment/trade-consumer -n trading --timeout=120s || true

# ==========================================================================
# Step 5: Verify Deployment
# ==========================================================================
echo ""
echo "=== Step 5: Verifying Deployment ==="

echo ""
echo "Deployment status:"
kubectl get deployments -n trading

echo ""
echo "Pod status:"
kubectl get pods -n trading -o wide

echo ""
echo "Rollout history (producer):"
kubectl rollout history deployment/trade-producer -n trading || true

echo ""
echo "Rollout history (consumer):"
kubectl rollout history deployment/trade-consumer -n trading || true

# ==========================================================================
# Summary
# ==========================================================================
echo ""
echo "=== CD Simulation Complete ==="
echo ""
echo "Deployed version: ${IMAGE_TAG}"
echo ""
echo "Useful commands:"
echo "  View logs:       kubectl logs -f deployment/trade-consumer -n trading"
echo "  Rollback:        ./scripts/rollback.sh"
echo "  Scale consumer:  kubectl scale deployment/trade-consumer --replicas=3 -n trading"
echo "  Port forward:    kubectl port-forward svc/postgres 5432:5432 -n trading"
