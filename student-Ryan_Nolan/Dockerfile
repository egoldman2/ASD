FROM nginx:1.27-alpine AS frontend

COPY student-Ryan_Nolan/frontend/ /usr/share/nginx/html/
EXPOSE 80

FROM python:3.11-slim AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY student-Ryan_Nolan/ ./student-Ryan_Nolan/
CMD ["python", "-m", "pytest", "student-Ryan_Nolan/tests", "-q"]