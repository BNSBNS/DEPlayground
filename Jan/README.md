# Energy Trading Platform

A production-grade real-time analytics platform for energy trading, featuring Kafka streaming, windowed aggregations, and PostgreSQL storage.

## Architecture Overview

```
┌──────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│    Trade     │────▶│    Kafka    │────▶│    Streaming     │────▶│ PostgreSQL  │
│   Producer   │     │   Cluster   │     │    Consumer      │     │   (OLTP)    │
│              │     │             │     │                  │     │             │
│ • Generates  │     │ • trades    │     │ • 1-min windows  │     │ • Aggregates│
│   trade      │     │   topic     │     │ • VWAP calc      │     │ • Queries   │
│   events     │     │ • DLQ topic │     │ • DLQ handling   │     │ • Indexes   │
└──────────────┘     └─────────────┘     └──────────────────┘     └─────────────┘
```

## Features

- **Real-time Streaming**: Kafka-based trade event ingestion with at-least-once delivery
- **Windowed Aggregation**: 1-minute tumbling windows with VWAP, volume, and price metrics
- **Idempotent Processing**: `INSERT ... ON CONFLICT` ensures correctness during replays
- **Dead Letter Queue**: Malformed messages routed to DLQ for investigation
- **Production-Ready**: Docker, Kubernetes, CI/CD, monitoring documentation

## Quick Start

### Prerequisites

- Docker and Docker Compose (required)
- Python 3.12+ (for local development)
- (Optional) Conda for environment management
- (Optional) Kind for Kubernetes testing

---

### Option 1: Run Everything with Docker (Easiest)

This starts the entire stack including producer, consumer, Kafka, and PostgreSQL:

```bash
# Start the full stack
docker-compose up -d

# Verify all services are running
docker-compose ps

# Watch the logs (producer generating trades, consumer aggregating)
docker-compose logs -f producer consumer

# Query aggregates in the database
docker-compose exec postgres psql -U trading -d trades -c \
  "SELECT symbol, window_start, vwap, trade_count FROM trade_aggregates ORDER BY window_start DESC LIMIT 10;"
```

**Stop everything:**
```bash
docker-compose down          # Stop and remove containers
docker-compose down -v       # Also remove data volumes (fresh start)
```

**Full Stack with Analytics & Monitoring:**

For a complete environment including TimescaleDB, Superset, Kafka UI, Prometheus, Grafana, and the chat interface:

```bash
# Start the full analytics stack
docker-compose -f docker-compose-full.yml up -d

# Services available:
# - API:        http://localhost:8000/docs
# - Chat UI:    http://localhost:7860
# - Kafka UI:   http://localhost:8080
# - Superset:   http://localhost:8088
# - Grafana:    http://localhost:3000
# - Prometheus: http://localhost:9090

# Initialize Superset (first time only)
docker exec superset superset db upgrade
docker exec superset superset fab create-admin --username admin --firstname Admin --lastname User --email admin@local --password admin
docker exec superset superset init
```

---

### Option 2: Local Development (Python + Docker Infrastructure)

Use this when you want to run the Python code locally for debugging/development.

**Step 1: Set up Python environment**

Using Conda (recommended):
```bash
conda env create -f environment.yml
conda activate energy-trading
pip install -e ".[dev]"
```

Or using pip/venv:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**Step 2: Start infrastructure only**
```bash
# Start Zookeeper, Kafka, PostgreSQL (schema auto-initialized via volume mount)
docker-compose up -d zookeeper kafka postgres kafka-init

# Wait for services to be healthy
docker-compose ps
```

**Step 3: Run services locally**
```bash
# Terminal 1: Start producer
python -m src.producer.main

# Terminal 2: Start consumer
python -m src.consumer.main

# Terminal 3 (optional): Start API server
python -m src.api.main
# API docs available at http://localhost:8000/docs
```

**Step 4: Verify data flow**
```bash
# Check aggregates in database
docker-compose exec postgres psql -U trading -d trades -c \
  "SELECT symbol, window_start, vwap, trade_count FROM trade_aggregates ORDER BY window_start DESC LIMIT 5;"
```

## Development

### Running Tests

```bash
# Run unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit -v --cov=src --cov-report=html

# Run integration tests (requires running infrastructure)
POSTGRES_DSN=postgresql://trading:trading@localhost:5432/trades pytest tests/integration -v
```

### Linting and Type Checking

```bash
# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/ --strict

# Format code
ruff format src/ tests/
```

### Full Stack with Docker Compose

```bash
# Build and run everything
docker-compose up --build

# View logs
docker-compose logs -f producer consumer

# Stop everything
docker-compose down
```

## Project Structure

```
Jan/
├── src/
│   ├── common/           # Shared modules (models, config, utils)
│   ├── producer/         # Trade event producer (Q3)
│   ├── consumer/         # Streaming consumer with DLQ (Q4, Q5)
│   ├── api/              # FastAPI REST and WebSocket endpoints
│   ├── chat/             # Natural language query interface (Gradio + Ollama)
│   └── analytics/        # Time-series processor (Q8)
├── sql/
│   ├── schema/           # Database DDL (Q6)
│   └── queries/          # Analytical queries (Q7)
├── docker/               # Dockerfiles (Q9)
├── k8s/                  # Kubernetes manifests (Q10)
├── terraform/            # AWS infrastructure (ECS, MSK, RDS)
│   ├── modules/          # Reusable Terraform modules
│   └── environments/     # Environment-specific configs (dev)
├── scripts/              # CD simulation scripts (Q13)
├── docs/                 # Architecture and monitoring docs (Q1, Q2, Q11, Q14)
├── tests/                # Unit and integration tests
└── .github/workflows/    # CI pipeline (Q12)
```

## Key Design Decisions

### Streaming Semantics

- **At-least-once delivery** with manual offset commit after successful DB write
- **Idempotent upserts** via `INSERT ... ON CONFLICT DO UPDATE`
- **Event time** (not processing time) for window assignment

### Database Design

- **NUMERIC(18,8)** for price/volume precision (no floating point errors)
- **Composite PK** `(symbol, window_start)` enables idempotent writes
- **Time partitioning** for efficient range queries
- **BRIN indexes** optimized for time-series access patterns

### Configuration

All configuration via environment variables (12-factor app):

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `localhost:9092` |
| `KAFKA_TOPIC` | Main trades topic | `trades` |
| `KAFKA_DLQ_TOPIC` | Dead Letter Queue topic | `trades-dlq` |
| `POSTGRES_DSN` | PostgreSQL connection string | (see .env.example) |
| `PRODUCER_RATE` | Events per second | `10` |
| `WINDOW_DURATION_SECONDS` | Aggregation window | `60` |

See [.env.example](.env.example) for complete configuration options.

## Documentation

### Core Concepts

| Document | Description |
|----------|-------------|
| [ASSESSMENT.md](docs/ASSESSMENT.md) | Original assessment questions and senior engineer guidance |
| [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | End-to-end system design (Q1) |
| [STREAMING_SEMANTICS.md](docs/STREAMING_SEMANTICS.md) | Delivery guarantees, CAP/ACID, upsert patterns (Q2, Q5-6, Q8-10) |
| [FAILURE_SCENARIOS.md](docs/FAILURE_SCENARIOS.md) | Failure modes and recovery (Q11) |
| [MONITORING_STRATEGY.md](docs/MONITORING_STRATEGY.md) | Metrics and alerts (Q14) |
| [VISUALIZATION_INTEGRATION.md](docs/VISUALIZATION_INTEGRATION.md) | PowerBI, Grafana, web frontend integration |

### Operations

| Document | Description |
|----------|-------------|
| [K8S_AUTOSCALING_HA.md](docs/K8S_AUTOSCALING_HA.md) | Autoscaling, HA, recovery validation (Q1) |
| [CDC_SCD_CACHING.md](docs/CDC_SCD_CACHING.md) | CDC, SCD, caching strategies (Q4, Q7) |
| [terraform/](terraform/) | AWS deployment with ECS, MSK, RDS |

### SQL Queries

| Query | Description |
|-------|-------------|
| [vwap_last_60_minutes.sql](sql/queries/vwap_last_60_minutes.sql) | VWAP per symbol (Q7) |
| [data_freshness_check.sql](sql/queries/data_freshness_check.sql) | Data freshness validation (Q3) |

### Monitoring Stack

| File | Description |
|------|-------------|
| [k8s/monitoring/](k8s/monitoring/) | Prometheus + Grafana stack (Q1a, Q2) |
| [src/common/metrics.py](src/common/metrics.py) | Prometheus metrics implementation (Q2) |

## Kubernetes Deployment

```bash
# Create Kind cluster
./scripts/setup-kind.sh

# Build and load images
./scripts/local-cd.sh

# Deploy
kubectl apply -f k8s/

# Check status
kubectl get pods -n trading
```

See [k8s/](k8s/) for deployment manifests including:
- Resource requests/limits (Guaranteed QoS)
- Liveness and readiness probes
- HPA for auto-scaling based on consumer lag

## Terraform Deployment (AWS)

Deploy the full stack to AWS using Terraform with ECS Fargate, MSK (Kafka), and RDS PostgreSQL.

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- AWS CLI configured with appropriate credentials
- An ECR repository for Docker images

### Infrastructure Overview

The Terraform configuration creates:

| Resource | Service | Description |
|----------|---------|-------------|
| VPC | Networking | 3-AZ VPC with public/private subnets, NAT gateways |
| MSK | Kafka | 3-broker managed Kafka cluster |
| RDS | PostgreSQL | PostgreSQL 16 with performance insights |
| ECS Fargate | Compute | API and Consumer services with ALB |
| CloudWatch | Logging | Log groups for all services |

### Step 1: Create ECR Repository

```bash
# Create ECR repository for images
aws ecr create-repository --repository-name trading --region us-east-1

# Get the repository URL (save this for terraform.tfvars)
aws ecr describe-repositories --repository-names trading --query 'repositories[0].repositoryUri' --output text
```

### Step 2: Build and Push Docker Images

```bash
# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push images (from Jan/ directory)
docker build -f docker/api/Dockerfile -t <ecr-url>:api-latest .
docker build -f docker/consumer/Dockerfile -t <ecr-url>:consumer-latest .

docker push <ecr-url>:api-latest
docker push <ecr-url>:consumer-latest
```

### Step 3: Configure Terraform Variables

```bash
cd terraform/environments/dev

# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
```

**terraform.tfvars:**
```hcl
aws_region         = "us-east-1"
environment        = "dev"
db_password        = "YourSecurePassword123!"  # Use a strong password
ecr_repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/trading"
```

### Step 4: Deploy Infrastructure

```bash
cd terraform/environments/dev

# Initialize Terraform
terraform init

# Review the execution plan
terraform plan

# Apply the configuration
terraform apply
```

### Step 5: Verify Deployment

```bash
# Get outputs
terraform output

# Test the API
curl http://$(terraform output -raw api_url)/health

# View API docs
echo "API Docs: http://$(terraform output -raw api_url)/docs"
```

### Terraform Outputs

After deployment, Terraform outputs these values:

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC identifier |
| `kafka_bootstrap_servers` | MSK broker connection string |
| `rds_endpoint` | PostgreSQL endpoint |
| `api_url` | Public API URL (ALB DNS) |
| `ecs_cluster_arn` | ECS cluster ARN |

### Tear Down

```bash
# Destroy all resources (WARNING: deletes everything)
terraform destroy
```

### Remote State (Recommended for Teams)

For team environments, enable S3 backend for state management:

```bash
# Create S3 bucket for state
aws s3 mb s3://trading-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket trading-terraform-state --versioning-configuration Status=Enabled

# Create DynamoDB table for locking
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Then uncomment the backend block in `terraform/environments/dev/main.tf`.

### Notes and Limitations

- **TimescaleDB**: The RDS parameter group includes TimescaleDB settings, but standard AWS RDS does not support TimescaleDB as a native extension. For TimescaleDB support, use [Timescale Cloud](https://www.timescale.com/cloud) or remove the `shared_preload_libraries` parameter from `modules/rds/main.tf`.
- **Cost**: MSK and RDS incur significant AWS charges. For development, consider using Docker Compose locally instead.
- **Multi-AZ**: Dev environment uses single-AZ RDS by default. Enable `multi_az = true` for production.

## Trade-offs and Assumptions

### Trade-offs

| Decision | Trade-off |
|----------|-----------|
| In-memory windows | Simplicity over durability (state lost on crash, recovered via replay) |
| PostgreSQL (not OLAP) | Easier operations vs. sub-second queries on large datasets |
| At-least-once + idempotency | Simpler than true exactly-once transactions |

### Assumptions

- Single Kafka cluster (no cross-region replication)
- UTC timestamps for all events
- Market hours not considered for rate limiting
- Schema evolution via compatible changes only

## CI/CD

### CI Pipeline (.github/workflows/ci.yml)

1. **Lint** (ruff) - Fast fail on style issues
2. **Type Check** (mypy) - Catch type errors
3. **Unit Tests** (pytest) - Core logic validation
4. **Build** (Docker) - Multi-stage images
5. **Security Scan** (Trivy) - CVE detection
6. **Integration Tests** - End-to-end validation

### Local CD Simulation

```bash
# Rolling update simulation
./scripts/local-cd.sh

# Rollback if needed
./scripts/rollback.sh
```

## License

MIT
