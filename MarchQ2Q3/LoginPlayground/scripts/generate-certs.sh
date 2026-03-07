#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

KEYS_DIR="$PROJECT_DIR/shared/keys"
CERTS_DIR="$PROJECT_DIR/shared/certs"

mkdir -p "$KEYS_DIR" "$CERTS_DIR"

# ── RSA keypair for JWT RS256 signing ──
if [ ! -f "$KEYS_DIR/private.pem" ]; then
  echo "Generating RSA keypair for JWT..."
  openssl genrsa -out "$KEYS_DIR/private.pem" 2048
  openssl rsa -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem"
  echo "  -> $KEYS_DIR/private.pem"
  echo "  -> $KEYS_DIR/public.pem"
else
  echo "RSA keypair already exists, skipping."
fi

# ── Self-signed CA for mTLS ──
if [ ! -f "$CERTS_DIR/ca.pem" ]; then
  echo "Generating self-signed CA..."
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$CERTS_DIR/ca-key.pem" -out "$CERTS_DIR/ca.pem" \
    -days 365 -nodes -subj "/CN=Auth Lab CA"
  echo "  -> $CERTS_DIR/ca.pem"
else
  echo "CA cert already exists, skipping."
fi

# ── Server cert signed by CA ──
if [ ! -f "$CERTS_DIR/server.pem" ]; then
  echo "Generating server certificate..."
  openssl req -newkey rsa:2048 \
    -keyout "$CERTS_DIR/server-key.pem" -out "$CERTS_DIR/server.csr" \
    -nodes -subj "/CN=localhost"
  openssl x509 -req -in "$CERTS_DIR/server.csr" \
    -CA "$CERTS_DIR/ca.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -CAcreateserial -out "$CERTS_DIR/server.pem" -days 365
  rm -f "$CERTS_DIR/server.csr"
  echo "  -> $CERTS_DIR/server.pem"
else
  echo "Server cert already exists, skipping."
fi

# ── Client cert signed by CA ──
if [ ! -f "$CERTS_DIR/client.pem" ]; then
  echo "Generating client certificate..."
  openssl req -newkey rsa:2048 \
    -keyout "$CERTS_DIR/client-key.pem" -out "$CERTS_DIR/client.csr" \
    -nodes -subj "/CN=client"
  openssl x509 -req -in "$CERTS_DIR/client.csr" \
    -CA "$CERTS_DIR/ca.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -CAcreateserial -out "$CERTS_DIR/client.pem" -days 365
  rm -f "$CERTS_DIR/client.csr"
  echo "  -> $CERTS_DIR/client.pem"
else
  echo "Client cert already exists, skipping."
fi

echo ""
echo "Done! All keys and certs are in:"
echo "  JWT keys:   $KEYS_DIR/"
echo "  mTLS certs: $CERTS_DIR/"
