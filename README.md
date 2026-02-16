# 📚 Book Recommendation System

A production-ready, microservice-based book recommendation platform with hybrid ML models, JWT authentication, full MLOps pipelines, and comprehensive DevOps practices.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 80)                          │
│              Rate Limiting · Security Headers · SSL              │
└──────────────────┬───────────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────────┐
│                    API Service (FastAPI :8000)                    │
│  Auth · RBAC · Books CRUD · Interactions · Recommendations       │
│  Rate Limiting · Prometheus Metrics · Structured Logging         │
└────┬────────────────┬────────────────┬───────────────────────────┘
     │                │                │
┌────▼─────┐  ┌───────▼──────┐  ┌─────▼──────────────────────────┐
│ PostgreSQL│  │    Redis     │  │  Recommendation Engine (:8001) │
│ (Data)    │  │(Cache+Queue) │  │  Content · Collab · Hybrid     │
└───────────┘  └──────┬───────┘  └───────────────┬────────────────┘
                      │                          │
               ┌──────▼──────────────────────────▼───────────────┐
               │        Training Pipeline (Celery Worker)         │
               │  Data Load → Train → Evaluate → Save → Reload   │
               └──────────────────────┬──────────────────────────┘
                                      │
               ┌──────────────────────▼──────────────────────────┐
               │          LocalStack (AWS Emulator :4566)         │
               │         S3 (Model Storage) · Secrets Manager     │
               └─────────────────────────────────────────────────┘
```

## Quick Start

> **No AWS account or credentials required.** The system uses [LocalStack](https://localstack.cloud/) to emulate AWS S3 and Secrets Manager locally. Dummy credentials (`test`/`test`) are pre-configured.

### 1. Clone & Configure

```bash
git clone <repo-url>
cd The-Muggle-Guide
cp .env.example .env   # Works out of the box — no edits needed for local dev
```

### 2. Run with Docker Compose

```bash
docker-compose up --build -d
```

This starts **7 containers**: PostgreSQL, Redis, LocalStack, API Service, Recommendation Engine, Training Worker, and NGINX.

### 3. Seed Sample Data

```bash
docker-compose exec api_service python -m app.seed
```

### 4. Trigger Initial Model Training

```bash
# Login as admin (seeded: admin@bookrec.com / Admin@123456)
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@bookrec.com","password":"Admin@123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost/api/admin/retrain \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Run Tests

```bash
bash tests/smoke_test.sh    # API smoke tests
bash tests/test_cloud.sh    # Cloud integration tests (S3 + Secrets Manager)
```

---

## Cloud Integration (LocalStack)

The system uses **real AWS SDK calls** (`boto3`) for S3 and Secrets Manager. In development, these are routed to a local [LocalStack](https://localstack.cloud/) container via a single environment variable:

```
AWS_ENDPOINT_URL=http://localstack:4566   # ← Set this for dev (LocalStack)
                                           # ← Remove for production (real AWS)
```

### What Happens Automatically

On `docker-compose up`, LocalStack starts and its init script (`localstack/init-aws.sh`) automatically:
1. Creates S3 bucket `bookrec-models` for model artifact storage
2. Creates Secrets Manager secret `bookrec/production` with JWT and DB credentials
3. All services connect and use these via the standard AWS SDK

### No Real AWS Credentials Needed

| Setting | Development (LocalStack) | Production (AWS) |
|---------|-------------------------|-------------------|
| `AWS_ENDPOINT_URL` | `http://localstack:4566` | *(remove or leave empty)* |
| `AWS_ACCESS_KEY_ID` | `test` (dummy) | Real IAM key or EC2 IAM role |
| `AWS_SECRET_ACCESS_KEY` | `test` (dummy) | Real IAM secret or EC2 IAM role |
| `MODEL_STORAGE_TYPE` | `s3` | `s3` |

### Cloud Services Exercised

| AWS Service | Usage | Verified By |
|-------------|-------|-------------|
| **S3** | Model artifact upload/download after training | `tests/test_cloud.sh` |
| **Secrets Manager** | JWT secret, DB password, Redis password at startup | API health check |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | Public | Register new user |
| POST | `/api/auth/login` | Public | Login & get tokens |
| POST | `/api/auth/refresh` | Public | Rotate refresh token |
| GET | `/api/books` | User | Paginated book list |
| GET | `/api/books/{id}` | User | Get single book |
| POST | `/api/books` | Admin | Create book |
| PUT | `/api/books/{id}` | Admin | Update book |
| DELETE | `/api/books/{id}` | Admin | Delete book |
| POST | `/api/interactions` | User | Log interaction |
| GET | `/api/interactions/me` | User | List my interactions |
| GET | `/api/recommendations/top` | User | Top-N for me |
| GET | `/api/recommendations/similar/{id}` | User | Similar books |
| POST | `/api/admin/retrain` | Admin | Trigger retraining |
| GET | `/api/admin/model-status` | Admin | Training status |
| GET | `/api/health` | Public | Health check |
| GET | `/api/ready` | Public | Readiness probe |
| GET | `/api/live` | Public | Liveness probe |
| GET | `/api/metrics` | Public | Prometheus metrics |

---

## ML Pipeline

### Recommendation Strategies

| Strategy | Algorithm | Use Case |
|----------|-----------|----------|
| **Content-Based** | TF-IDF + Cosine Similarity | New users, similar books lookup |
| **Collaborative** | ALS (Implicit library) | Users with interaction history |
| **Hybrid** | Weighted blend (α=0.7 collab) | Primary strategy for active users |
| **Cold Start** | Popularity-based | Brand new users, no interactions |

### MLOps Workflow

```
┌─────────┐    ┌───────────┐    ┌────────────┐    ┌──────────┐
│ Ingestion│───▶│ Validation│───▶│Feature Eng.│───▶│ Training │
└─────────┘    └───────────┘    └────────────┘    └────┬─────┘
                                                       │
┌─────────┐    ┌───────────┐    ┌────────────┐    ┌────▼─────┐
│ Reload  │◀───│  Store S3  │◀───│ Versioning │◀───│Evaluation│
└─────────┘    └───────────┘    └────────────┘    └──────────┘
```

- **Scheduled retraining**: Weekly via Celery Beat
- **On-demand retraining**: Admin endpoint `POST /admin/retrain`
- **Evaluation metrics**: Precision@K, Recall@K, NDCG@K, MAP
- **Model versioning**: Timestamped artifacts stored in S3
- **Blue-green loading**: New model loaded only after evaluation passes

---

## Security Checklist ✅

- [x] **No hardcoded secrets** — all via env vars / AWS Secrets Manager
- [x] **`.env` in `.gitignore`** — never committed
- [x] **JWT with rotation** — access (30min) + refresh (7d) tokens
- [x] **Bcrypt password hashing** — via passlib
- [x] **RBAC** — user/admin role enforcement
- [x] **Input validation** — Pydantic schemas on all endpoints
- [x] **SQL injection protection** — SQLAlchemy parameterized queries
- [x] **Rate limiting (dual-layer)** — NGINX IP-based + Redis user-based
- [x] **Security headers** — X-Frame, X-Content-Type, CSP, HSTS via NGINX
- [x] **CORS restrictions** — configurable origins
- [x] **Non-root containers** — all Dockerfiles use `appuser`
- [x] **No secrets in logs** — structlog with sanitized output
- [x] **No secrets in images** — multi-stage builds, .env not copied

---

## EC2 Deployment Guide

### Prerequisites
- AWS EC2 instance (t3.medium+ recommended)
- Docker & Docker Compose installed
- Security groups: allow ports 80, 443
- RDS PostgreSQL instance (optional, can use containerized)
- ElastiCache Redis (optional)

### Step-by-Step

```bash
# 1. SSH into EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# 2. Install Docker
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone the repo
cd /opt
sudo git clone <repo-url> bookrec
cd bookrec

# 5. Create production .env
sudo cp .env.example .env
sudo nano .env
# Key changes for production:
#   ENVIRONMENT=production
#   AWS_ENDPOINT_URL=      ← Remove to use real AWS
#   AWS_ACCESS_KEY_ID=     ← Use real credentials or IAM role
#   AWS_SECRET_ACCESS_KEY= ← Use real credentials or IAM role

# 6. Set up HTTPS (Let's Encrypt)
sudo yum install certbot -y
sudo certbot certonly --standalone -d your-domain.com
# Update nginx config to use the certificates

# 7. Create systemd service
sudo tee /etc/systemd/system/bookrec.service > /dev/null <<EOF
[Unit]
Description=Book Recommendation System
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/opt/bookrec
ExecStart=/usr/local/bin/docker-compose up
ExecStop=/usr/local/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable bookrec
sudo systemctl start bookrec

# 8. Seed data & train models
docker-compose exec api_service python -m app.seed
# Login as admin and trigger retrain via API
```

### Switching from LocalStack to Real AWS

```bash
# 1. Remove or empty AWS_ENDPOINT_URL in .env
AWS_ENDPOINT_URL=

# 2. Either set real credentials:
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# 3. Or (recommended) attach an IAM role to the EC2 instance with:
#    - s3:PutObject, s3:GetObject on arn:aws:s3:::bookrec-models/*
#    - secretsmanager:GetSecretValue on arn:aws:secretsmanager:*:*:secret:bookrec/*

# 4. Create the S3 bucket and secret in real AWS:
aws s3 mb s3://bookrec-models
aws secretsmanager create-secret \
  --name bookrec/production \
  --secret-string '{"jwt_secret_key":"...","postgres_password":"...","redis_password":"..."}'
```

---

## Scaling Strategy

### Horizontal Scaling (Current Architecture)
- **API Service**: Stateless — simply add more containers behind NGINX
- **Recommendation Engine**: Stateless — scale horizontally
- **Training Worker**: Add Celery workers for parallel training

### Kubernetes-Ready Path
```
1. Convert docker-compose to Helm chart
2. Deploy to EKS with:
   - HPA for API/Rec engine pods
   - CronJob for scheduled training
   - PersistentVolume for model artifacts
   - Ingress with cert-manager for TLS
3. Use AWS ALB Ingress Controller
4. Use EFS for shared model storage
5. Use RDS + ElastiCache managed services
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy (async) |
| Cache | Redis 7 |
| ML | scikit-learn, implicit (ALS) |
| Task Queue | Celery + Redis |
| Reverse Proxy | NGINX |
| Cloud (Dev) | LocalStack (S3, Secrets Manager) |
| Cloud (Prod) | AWS S3, Secrets Manager |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Monitoring | Prometheus metrics |
| Logging | structlog (JSON) |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Resilience | tenacity (retry) + circuitbreaker |

---

## Development

```bash
# Run locally (no AWS account needed)
docker-compose up --build

# Run tests
pip install -r api_service/requirements.txt pytest pytest-asyncio httpx
pytest tests/ -v

# Cloud integration tests
bash tests/test_cloud.sh

# Lint
pip install ruff
ruff check .
```

## License

MIT

