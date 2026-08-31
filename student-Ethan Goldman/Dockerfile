FROM nginx:1.27-alpine AS frontend

COPY ["student-Ethan Goldman/frontend/", "/usr/share/nginx/html/"]
COPY ["student-Ethan Goldman/support_frontend_nginx.conf", "/etc/nginx/nginx.conf"]

EXPOSE 80

FROM python:3.11-slim AS support-python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM support-python-base AS backend

COPY ["student-Ethan Goldman/support_backend/", "/app/support_backend/"]

ENV APP_HOST=0.0.0.0 \
    APP_PORT=6005 \
    SUPPORT_DATABASE_API_URL=http://customer-support-database:6006 \
    AUTH_SERVICE_URL=http://ethan-backend:6002 \
    OLLAMA_URL=http://ollama:11434 \
    OLLAMA_MODEL=qwen2.5:0.5b

EXPOSE 6005

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:6005/health', timeout=2).read()"

CMD ["python", "support_backend/app.py"]

FROM support-python-base AS database

COPY ["student-Ethan Goldman/database_service/", "/app/database_service/"]

ENV APP_HOST=0.0.0.0 \
    APP_PORT=6006 \
    DATABASE_PATH=/data/support_tickets.db

EXPOSE 6006

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:6006/health', timeout=2).read()"

CMD ["python", "database_service/app.py"]

FROM support-python-base AS test

COPY . .

CMD ["python", "-m", "pytest", "student-Ethan Goldman/tests", "-q"]
