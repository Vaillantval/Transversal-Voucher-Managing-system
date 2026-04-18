# ── Stage 1 : builder ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Dépendances système pour psycopg2 et Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python dans un dossier isolé
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2 : image finale ────────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Runtime uniquement (pas de gcc etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages installés depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source
COPY . .

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput

EXPOSE 8000