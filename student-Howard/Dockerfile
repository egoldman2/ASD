FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole student folder (backend, database, frontend)
COPY . .

# Seed the database at build time
RUN cd database && python seed.py

EXPOSE 5001

CMD ["python", "backend/app.py"]