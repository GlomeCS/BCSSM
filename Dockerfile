# Stage 1: Build the React frontend
FROM node:23-slim AS frontend-builder
WORKDIR /app/frontend

ARG CACHEBUST=1
COPY frontend/package.json frontend/package-lock.json ./
# Copy all frontend source files into the working directory
COPY frontend/. ./
RUN npm install
RUN npm run build

# Stage 2: Set up Flask
FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

RUN rm -rf backend/bcssm_backend/static/*
COPY --from=frontend-builder /app/frontend/dist/. ./backend/bcssm_backend/static/

ENV FLASK_APP=backend.bcssm_backend:create_app
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 8080

CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]