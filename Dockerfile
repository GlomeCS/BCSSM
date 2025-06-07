# Stage 1: Build the React frontend
FROM node:23-slim AS frontend-builder
WORKDIR /app/frontend

ARG CACHEBUST=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend ./
RUN npm run build

# Stage 2: Set up Flask
FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Copy the built React files into Flask's static folder; the trailing '/.' copies all contents.
COPY --from=frontend-builder /app/backend/static/. ./backend/static/

ENV FLASK_APP=backend.app
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 8080

CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]