# Multi-stage build for Vite React app served on Cloud Run

# 1) Build stage: install deps and build static assets
FROM node:18-alpine AS build
WORKDIR /app

# Install dependencies (use npm ci for reproducible installs)
COPY package*.json ./
RUN npm ci

# Copy the rest of the source and build
COPY . .
RUN npm run build

# 2) Runtime stage: serve static files with `serve`
FROM node:18-alpine AS runner
WORKDIR /app

# Install a lightweight static server with SPA support
RUN npm i -g serve@14

# Copy built assets from the previous stage
COPY --from=build /app/dist ./dist

# Cloud Run provides PORT env var
ENV PORT=8080
EXPOSE 8080

# Bind to 0.0.0.0 and respect Cloud Run PORT
CMD ["sh","-c","serve -s dist -l tcp://0.0.0.0:${PORT:-8080}"]
