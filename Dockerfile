# =============================================================================
# Stage 1: Build the React frontend
# =============================================================================
FROM node:20-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Production runtime (Python + nginx)
# =============================================================================
FROM python:3.12-slim

# Install nginx and supervisord (to run nginx + gunicorn together)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy built frontend into nginx's serve directory
COPY --from=frontend-build /build/dist /usr/share/nginx/html

# nginx config
RUN rm /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/conf.d/default.conf

# supervisord config — runs both nginx and gunicorn
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# Cache directory (mount a volume here for persistence)
RUN mkdir -p /app/backend/cache

EXPOSE 80

CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
