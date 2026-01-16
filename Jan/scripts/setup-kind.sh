#!/bin/bash
# Setup Kind (Kubernetes in Docker) cluster for local development
# Question 10: Kubernetes deployment testing

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-trading-cluster}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Setting up Kind cluster for Energy Trading Platform ==="

# Check prerequisites
command -v kind >/dev/null 2>&1 || {
    echo "Error: kind is not installed. Install from https://kind.sigs.k8s.io/"
    exit 1
}

command -v kubectl >/dev/null 2>&1 || {
    echo "Error: kubectl is not installed."
    exit 1
}

command -v docker >/dev/null 2>&1 || {
    echo "Error: docker is not installed."
    exit 1
}

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster '${CLUSTER_NAME}' already exists."
    read -p "Delete and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kind delete cluster --name "$CLUSTER_NAME"
    else
        echo "Using existing cluster."
        kubectl cluster-info --context "kind-${CLUSTER_NAME}"
        exit 0
    fi
fi

# Create Kind cluster with custom config
echo "Creating Kind cluster '${CLUSTER_NAME}'..."
cat <<EOF | kind create cluster --name "$CLUSTER_NAME" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30080
        hostPort: 30080
        protocol: TCP
      - containerPort: 30443
        hostPort: 30443
        protocol: TCP
  - role: worker
  - role: worker
EOF

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

# Create namespace
echo "Creating trading namespace..."
kubectl apply -f "$PROJECT_DIR/k8s/namespace.yaml"

# Apply ConfigMap
echo "Applying ConfigMap..."
kubectl apply -f "$PROJECT_DIR/k8s/configmap.yaml"

# Create secrets (using template values for local dev)
echo "Creating secrets for local development..."
kubectl create secret generic trading-secrets \
    --namespace=trading \
    --from-literal=POSTGRES_USER=trading \
    --from-literal=POSTGRES_PASSWORD=trading \
    --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "=== Kind cluster setup complete ==="
echo ""
echo "Cluster info:"
kubectl cluster-info --context "kind-${CLUSTER_NAME}"
echo ""
echo "Nodes:"
kubectl get nodes
echo ""
echo "Next steps:"
echo "1. Build and load images: ./scripts/local-cd.sh"
echo "2. Deploy services: kubectl apply -f k8s/"
echo "3. Check pods: kubectl get pods -n trading"
echo ""
echo "To delete cluster: kind delete cluster --name ${CLUSTER_NAME}"
