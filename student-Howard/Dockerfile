FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY student-Howard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole student folder
COPY student-Howard/ ./student-Howard/

# Seed the database at build time
RUN cd student-Howard/database && python seed.py

EXPOSE 5001

CMD ["python", "student-Howard/backend/app.py"]