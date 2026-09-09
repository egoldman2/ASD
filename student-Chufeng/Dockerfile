FROM nginx:1.27-alpine AS frontend

COPY student-Chufeng/frontend/ /usr/share/nginx/html/

EXPOSE 80


FROM python:3.11-slim AS database

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=6001 \
    DATABASE_PATH=/data/products.db

WORKDIR /app/student-Chufeng/database

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY student-Chufeng/database/ ./

EXPOSE 6001

CMD ["python", "api.py"]


FROM python:3.11-slim AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY student-Chufeng/ ./student-Chufeng/

CMD ["python", "-m", "pytest", "student-Chufeng/tests", "-q"]
