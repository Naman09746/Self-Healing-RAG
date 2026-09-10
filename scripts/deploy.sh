#!/bin/bash

# Production Deployment Script
set -e

echo "🚀 Starting Deployment of Self-Healing RAG Pipeline..."

# 1. Validation
echo "🔍 Running pre-deployment validation..."
make lint
make test

# 2. Infrastructure
echo "🏗️ Ensuring infrastructure is healthy..."
docker compose up -d postgres ollama

# 3. Model Provisioning
echo "🧠 Checking LLM models..."
docker-compose exec -T ollama ollama pull mistral:7b
docker-compose exec -T ollama ollama pull nomic-embed-text

# 4. Build & Restart API
echo "🔨 Building API container..."
docker-compose build api
docker-compose up -d api

echo "✅ Deployment Successful!"
echo "📍 API is live at http://localhost:8000"
echo "📊 Monitoring available via OpenTelemetry"
