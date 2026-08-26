FROM nginx:1.27-alpine AS frontend

COPY ["student-Ethan Goldman/frontend/", "/usr/share/nginx/html/"]

EXPOSE 80

FROM python:3.11-slim AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ["student-Ethan Goldman/", "./student-Ethan Goldman/"]

CMD ["python", "-m", "pytest", "student-Ethan Goldman/tests/test_database.py", "-q"]
