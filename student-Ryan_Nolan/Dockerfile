FROM nginx:1.27-alpine AS frontend

COPY student-Ryan_Nolan/frontend/ /usr/share/nginx/html/
EXPOSE 80


FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


FROM python-base AS backend

COPY student-Ryan_Nolan/ ./student-Ryan_Nolan/

WORKDIR /app/student-Ryan_Nolan/backend

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8102 \
    AUTH_SERVICE_URL=http://ethan-backend:6002 \
    PRODUCT_DATABASE_API_URL=http://product-database:6001/api/database

EXPOSE 8102

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8102/health', timeout=2)"

CMD ["python", "app.py"]


FROM python-base AS test

COPY . .

RUN python student-Ryan_Nolan/database/ryan_init_db.py

CMD ["python", "-m", "pytest", "student-Ryan_Nolan/tests/inventory_tests.py", "-q"]
