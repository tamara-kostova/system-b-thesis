FROM node:18-bullseye-slim AS builder
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps

# Build-time proxy targets (overridden via docker-compose build args)
ARG DISCOVERY_API_URL=http://localhost:8003
ARG PERMIT_SERVICE_URL=http://localhost:8002
ARG LLM_GATEWAY_URL=http://localhost:8006
ARG SPE_PROVISIONER_URL=http://localhost:8004

ENV DISCOVERY_API_URL=$DISCOVERY_API_URL
ENV PERMIT_SERVICE_URL=$PERMIT_SERVICE_URL
ENV LLM_GATEWAY_URL=$LLM_GATEWAY_URL
ENV SPE_PROVISIONER_URL=$SPE_PROVISIONER_URL

# Copy source and build
COPY . .
RUN npm run build

FROM node:18-bullseye-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app .
EXPOSE 3001
CMD ["npm", "start"]
