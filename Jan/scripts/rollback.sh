#!/bin/bash
# Rollback Script for Energy Trading Platform
# Question 13: Demonstrate rollback mechanics
#
# Usage:
#   ./scripts/rollback.sh              # Rollback to previous version
#   ./scripts/rollback.sh 2            # Rollback to specific revision

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-trading-cluster}"
REVISION="${1:-}"

echo "=== Rollback for Energy Trading Platform ==="

# Set kubectl context
kubectl config use-context "kind-${CLUSTER_NAME}" 2>/dev/null || {
    echo "Error: Cannot connect to cluster '${CLUSTER_NAME}'"
    exit 1
}

# Show current status
echo ""
echo "Current deployment status:"
kubectl get deployments -n trading

echo ""
echo "Current pods:"
kubectl get pods -n trading

# Show rollout history
echo ""
echo "=== Rollout History ==="

echo ""
echo "Producer history:"
kubectl rollout history deployment/trade-producer -n trading || true

echo ""
echo "Consumer history:"
kubectl rollout history deployment/trade-consumer -n trading || true

# Confirm rollback
echo ""
if [ -n "$REVISION" ]; then
    echo "Will rollback to revision: $REVISION"
else
    echo "Will rollback to previous version"
fi
read -p "Proceed with rollback? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 0
fi

# Perform rollback
echo ""
echo "=== Performing Rollback ==="

if [ -n "$REVISION" ]; then
    echo "Rolling back producer to revision $REVISION..."
    kubectl rollout undo deployment/trade-producer -n trading --to-revision="$REVISION"

    echo "Rolling back consumer to revision $REVISION..."
    kubectl rollout undo deployment/trade-consumer -n trading --to-revision="$REVISION"
else
    echo "Rolling back producer to previous version..."
    kubectl rollout undo deployment/trade-producer -n trading

    echo "Rolling back consumer to previous version..."
    kubectl rollout undo deployment/trade-consumer -n trading
fi

# Wait for rollback to complete
echo ""
echo "Waiting for rollback to complete..."

kubectl rollout status deployment/trade-producer -n trading --timeout=120s || true
kubectl rollout status deployment/trade-consumer -n trading --timeout=120s || true

# Show final status
echo ""
echo "=== Rollback Complete ==="

echo ""
echo "Deployment status:"
kubectl get deployments -n trading

echo ""
echo "Pod status:"
kubectl get pods -n trading
