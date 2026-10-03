# ==============================================================================
# Multi-stage Dockerfile pour BiblioBot Paris (Python 3.11-slim)
# ==============================================================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runner
FROM python:3.11-slim as runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/home/appuser/.local/bin:$PATH"

# Dépendances système d'exécution (ex: git ou certificats SSL si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Création d'un utilisateur non-root pour la sécurité
RUN useradd -u 1000 -m appuser

# Copie des bibliothèques installées depuis l'étape builder
COPY --from=builder /root/.local /home/appuser/.local

# Copie du code applicatif
COPY --chown=appuser:appuser . /app

USER appuser

EXPOSE 8080

# Démarrage du serveur FastAPI via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
