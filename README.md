# Marsh AI

Flask-based AI application for generating insurance marketing pitches grounded in policy documents. The backend uses document extraction, text chunking, embeddings, FAISS retrieval, pitch generation, auditing, and PowerPoint generation.

## Prerequisites

- Python 3.11 recommended
- pip
- An OpenRouter API key

## Local setup

```bash
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Add your own `OPENROUTER_API_KEY` to `.env`. Do not commit `.env` or share API keys.

## Run

```bash
python app.py
```

Open the local URL printed by Flask. The application currently exposes the web interface at `/`, pitch generation at `/generate-pitch`, PowerPoint generation at `/generate-ppt`, and a health endpoint at `/health`.

## Health check

```bash
curl http://127.0.0.1:5000/health
```

Expected response: `{"status":"healthy"}`. This endpoint is intended for container and Kubernetes liveness/readiness checks.

## Tests

```bash
python -m pip install pytest
python -m pytest tests/ -v
```

## Project structure

- `app.py` – Flask routes and application orchestration
- `src/` – retrieval, embeddings, policy processing, pitch generation, auditing, and presentation generation
- `data/policies/` – source policy PDFs
- `data/processed/` – extracted policy text
- `templates/` – Flask frontend
- `tests/` – automated tests
- `output/` – generated files (kept out of version control)

## MLOps work planned

The next implementation stages will add GitHub Actions CI/CD, Docker packaging, Kubernetes manifests, Terraform infrastructure provisioning, and Prometheus/Grafana monitoring.
