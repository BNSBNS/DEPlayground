# Security Guide

This document covers security practices for the Energy Trading Platform.

## Current Implementation

### Secret Management

Secrets are managed through a layered approach:

1. **Development**: `.env.secrets` file (gitignored)
2. **Docker**: Docker secrets mount
3. **Kubernetes**: K8s Secrets

**Usage**:
```python
from src.common.secrets import get_secret, require_secrets

# Get a secret with fallback
password = get_secret("POSTGRES_PASSWORD", default="trading")

# Require secrets at startup (fail fast)
require_secrets("POSTGRES_PASSWORD", "FINNHUB_API_KEY")
```

**Secret sources (in order of precedence)**:
1. Kubernetes secrets (`/run/secrets/<name>`)
2. Docker secrets (`/run/secrets/<name>`)
3. `.env.secrets` file
4. Environment variables
5. Default values

### Setup for Development

```bash
# Copy the example file
cp .env.secrets.example .env.secrets

# Edit with your actual secrets
nano .env.secrets

# The file is gitignored - never commit it!
```

---

## Kafka Security (Documentation Only)

> **Note**: SSL/TLS is not enabled in the current learning setup.
> This section documents the configuration for production use.

### Option 1: SSL/TLS (Encryption in Transit)

```yaml
# docker-compose-ssl.yml (reference only)
kafka:
  environment:
    # SSL Listener
    KAFKA_LISTENERS: SSL://kafka:9093,PLAINTEXT://kafka:29092
    KAFKA_ADVERTISED_LISTENERS: SSL://localhost:9093,PLAINTEXT://kafka:29092
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: SSL:SSL,PLAINTEXT:PLAINTEXT

    # SSL Configuration
    KAFKA_SSL_KEYSTORE_LOCATION: /etc/kafka/secrets/kafka.keystore.jks
    KAFKA_SSL_KEYSTORE_PASSWORD_FILE: /run/secrets/keystore_password
    KAFKA_SSL_KEY_PASSWORD_FILE: /run/secrets/key_password
    KAFKA_SSL_TRUSTSTORE_LOCATION: /etc/kafka/secrets/kafka.truststore.jks
    KAFKA_SSL_TRUSTSTORE_PASSWORD_FILE: /run/secrets/truststore_password

    # Client authentication
    KAFKA_SSL_CLIENT_AUTH: required  # or 'requested' or 'none'
```

### Option 2: SASL Authentication

```yaml
kafka:
  environment:
    KAFKA_LISTENERS: SASL_SSL://kafka:9093
    KAFKA_SASL_ENABLED_MECHANISMS: SCRAM-SHA-512
    KAFKA_SASL_MECHANISM_INTER_BROKER_PROTOCOL: SCRAM-SHA-512
```

### Certificate Generation Script

```bash
#!/bin/bash
# kafka/ssl/generate-certs.sh
# Run manually when setting up SSL

# Variables
PASSWORD="changeit"
VALIDITY=365
CA_CN="Kafka-CA"
BROKER_CN="kafka"

# 1. Create CA
openssl req -new -x509 -keyout ca-key -out ca-cert -days $VALIDITY \
    -subj "/CN=$CA_CN" -passout pass:$PASSWORD

# 2. Create broker keystore
keytool -keystore kafka.server.keystore.jks -alias localhost \
    -validity $VALIDITY -genkey -keyalg RSA \
    -dname "CN=$BROKER_CN" -storepass $PASSWORD -keypass $PASSWORD

# 3. Create CSR
keytool -keystore kafka.server.keystore.jks -alias localhost \
    -certreq -file cert-request -storepass $PASSWORD

# 4. Sign certificate with CA
openssl x509 -req -CA ca-cert -CAkey ca-key -in cert-request \
    -out cert-signed -days $VALIDITY -CAcreateserial -passin pass:$PASSWORD

# 5. Import CA and signed cert into keystore
keytool -keystore kafka.server.keystore.jks -alias CARoot \
    -import -file ca-cert -storepass $PASSWORD -noprompt
keytool -keystore kafka.server.keystore.jks -alias localhost \
    -import -file cert-signed -storepass $PASSWORD -noprompt

# 6. Create truststore
keytool -keystore kafka.server.truststore.jks -alias CARoot \
    -import -file ca-cert -storepass $PASSWORD -noprompt

echo "Certificates generated in current directory"
```

### Python Client Configuration

```python
# src/common/kafka_utils.py
from src.common.secrets import get_secret

def create_ssl_producer():
    return Producer({
        'bootstrap.servers': 'kafka:9093',
        'security.protocol': 'SSL',
        'ssl.ca.location': '/etc/kafka/certs/ca-cert.pem',
        'ssl.certificate.location': '/etc/kafka/certs/client-cert.pem',
        'ssl.key.location': '/etc/kafka/certs/client-key.pem',
        'ssl.key.password': get_secret('KAFKA_SSL_KEY_PASSWORD'),
    })
```

---

## Database Security

### Current Setup

- Default credentials in development
- Passwords externalized to `.env.secrets`

### Production Recommendations

```yaml
# docker-compose-secure.yml
timescaledb:
  environment:
    POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
  secrets:
    - postgres_password

secrets:
  postgres_password:
    file: ./.secrets/postgres_password
```

### SSL Connections

```python
# Enable SSL for PostgreSQL
POSTGRES_DSN = "postgresql://user:pass@host:5432/db?sslmode=require"
```

### Row-Level Security (Future)

```sql
-- For multi-tenant scenarios
ALTER TABLE trade_aggregates ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON trade_aggregates
    USING (tenant_id = current_setting('app.tenant_id')::int);
```

---

## Kubernetes Security

### Secrets Template

```yaml
# k8s/secrets.yaml.template
apiVersion: v1
kind: Secret
metadata:
  name: trading-secrets
  namespace: trading
type: Opaque
stringData:
  POSTGRES_PASSWORD: "<your-password>"
  FINNHUB_API_KEY: "<your-api-key>"
  ENTSOE_API_KEY: "<your-api-key>"
  SUPERSET_SECRET_KEY: "<generate-with-openssl>"
```

### Using SOPS for Encrypted Secrets

```bash
# Encrypt secrets
sops --encrypt --age $(cat ~/.sops/age.txt) k8s/secrets.yaml > k8s/secrets.yaml.encrypted

# Decrypt secrets
sops --decrypt k8s/secrets.yaml.encrypted > k8s/secrets.yaml
```

### External Secrets Operator

For production, use External Secrets Operator with AWS Secrets Manager or HashiCorp Vault:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: trading-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: trading-secrets
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: trading/postgres
        property: password
```

---

## Security Checklist

### Development
- [ ] `.env.secrets` is in `.gitignore`
- [ ] No secrets in code or docker-compose files
- [ ] Default passwords only in development

### Staging/Production
- [ ] SSL/TLS enabled for Kafka
- [ ] SSL enabled for PostgreSQL
- [ ] Secrets managed via K8s Secrets or Vault
- [ ] Network policies restrict service access
- [ ] Non-root container users (already done)
- [ ] Resource limits set (already done)

### API Security
- [ ] CORS configured for specific origins
- [ ] Rate limiting enabled
- [ ] API authentication (future)

---

## Files Reference

| File | Purpose |
|------|---------|
| `.env.secrets.example` | Template for secrets |
| `src/common/secrets.py` | Secret management code |
| `k8s/secrets.yaml.template` | K8s secrets template |
| `kafka/ssl/generate-certs.sh` | Certificate generation (docs) |
| `docker-compose-ssl.yml` | SSL reference config (docs) |
