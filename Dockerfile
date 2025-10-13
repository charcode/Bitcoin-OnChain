# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---------- Stage 2: backend ----------
FROM python:3.11-slim AS backend
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy built frontend into static directory (adjust if needed)
COPY --from=frontend-build /app/frontend/dist /app/static

# Expose backend port (FastAPI/Flask)
EXPOSE 8000

# Command to run backend
CMD ["python", "main.py"]
