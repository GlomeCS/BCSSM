# Stage 1: Build the React frontend
FROM node:24-slim AS frontend-builder
WORKDIR /app/frontend

ARG CACHEBUST=1
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/. ./
RUN npm install
RUN npm run build

# Stage 2: Set up Flask with Gunicorn
FROM python:3.13-slim
WORKDIR /app

# Update package lists and install dependencies with retry logic
RUN apt-get update && \
    for i in 1 2 3; do \
        apt-get install -y --no-install-recommends --fix-missing \
            gcc build-essential libpq-dev && break || \
        (apt-get clean && apt-get update && sleep 10); \
    done && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Copy built frontend into Flask static directory
RUN rm -rf backend/bcssm_backend/static/*
COPY --from=frontend-builder /app/frontend/dist/. ./backend/bcssm_backend/static/

# Environment config
ENV FLASK_APP=backend.bcssm_backend:create_app

EXPOSE 8080

# Run the app using Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "--timeout", "120", "--keep-alive", "2", "--access-logfile", "-", "--error-logfile", "-", "backend.bcssm_backend:create_app()"]