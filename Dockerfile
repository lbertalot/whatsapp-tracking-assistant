# WhatsApp Tracking Assistant — imagen única para web + worker (paridad Heroku)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint-web.sh

EXPOSE 8000

# Comando por defecto: web (Compose sobreescribe el worker)
CMD ["./docker/entrypoint-web.sh"]
