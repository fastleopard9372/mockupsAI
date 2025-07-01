#!/bin/bash

echo "Starting application setup..."

# Ensure we're using Python's Prisma, not Node's
export PRISMA_SKIP_POSTINSTALL_GENERATE=true

# Remove any Node artifacts that might interfere
rm -rf node_modules prisma_binaries/node_modules 2>/dev/null || true

# Generate Prisma Client for Python
echo "Generating Prisma Client for Python..."
python -m prisma generate

# Fetch binaries using Python
echo "Fetching Prisma binaries via Python..."
python -m prisma py fetch --force

# Copy binary to root if needed
if [ -f ~/.cache/prisma-python/binaries/*/prisma-query-engine-debian-openssl-3.0.x ]; then
    cp ~/.cache/prisma-python/binaries/*/prisma-query-engine-debian-openssl-3.0.x ./
    chmod +x ./prisma-query-engine-debian-openssl-3.0.x
fi

# Start the application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}