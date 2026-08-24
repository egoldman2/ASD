# ---- Frontend stage (served by nginx on port 80 -> mapped to 8004) ----
FROM nginx:1.27-alpine AS frontend
COPY student-Howard/frontend/ /usr/share/nginx/html/
EXPOSE 80

# ---- Backend stage (Flask API) ----
FROM python:3.11-slim AS backend
WORKDIR /app
COPY student-Howard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY student-Howard/ ./student-Howard/
RUN cd student-Howard/database && python seed.py
EXPOSE 5001
CMD ["python", "student-Howard/backend/app.py"]