# ==============================================================================
# MetaStudio Frontend — Multi-stage React/Vite Build + Nginx Reverse Proxy
# ==============================================================================
FROM node:26-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty by default so the SPA sends /api/v1/* requests through the same-origin Nginx proxy
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ------------------------------------------------------------------------------
# Runtime Stage — Minimal Nginx serving SPA static assets + proxying /api/
# ------------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1/healthz"]

CMD ["nginx", "-g", "daemon off;"]
