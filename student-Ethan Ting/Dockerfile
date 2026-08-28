FROM nginx:1.27-alpine AS frontend

COPY ["student-Ethan Ting/frontend/", "/usr/share/nginx/html/"]

EXPOSE 80


FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


FROM python-base AS backend

COPY ["student-Ethan Ting/backend/app.py", "/app/app.py"]

EXPOSE 6002

CMD ["python", "app.py"]


FROM python-base AS database

COPY ["student-Ethan Ting/database/", "/app/"]

EXPOSE 6003

CMD ["python", "app.py"]


FROM python-base AS test

COPY ["student-Ethan Ting/backend/", "/app/backend/"]
COPY ["student-Ethan Ting/database/", "/app/database/"]
COPY ["student-Ethan Ting/tests/", "/app/tests/"]

CMD ["python", "-m", "pytest", "tests", "-q"]
