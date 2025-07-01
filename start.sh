#!/bin/bash

echo "Starting application setup..."

# Create the expected directory structure
echo "Creating prisma binaries directory..."
mkdir -p /opt/render/project/src/prisma_binaries

# Set environment for Prisma
export PRISMA_HOME=/opt/render/project/src/prisma_binaries
export PRISMA_BINARIES_MIRROR=https://binaries.prisma.sh

# Generate Prisma Client
echo "Generating Prisma Client..."
prisma generate

# Fetch binaries to the specific location
echo "Fetching Prisma binaries..."
cd /opt/render/project/src
python -m prisma py fetch --force

# Copy binary to expected location if needed
if [ -f "/opt/render/.cache/prisma-python/binaries/4.15.0/*/prisma-query-engine-debian-openssl-3.0.x" ]; then
    echo "Copying binary to expected location..."
    cp /opt/render/.cache/prisma-python/binaries/4.15.0/*/prisma-query-engine-debian-openssl-3.0.x /opt/render/project/src/
    chmod +x /opt/render/project/src/prisma-query-engine-debian-openssl-3.0.x
fi

# Also try to find and copy from any location
find /opt/render -name "prisma-query-engine-debian-openssl-3.0.x" -type f -exec cp {} /opt/render/project/src/ \; 2>/dev/null || true
find /opt/render -name "prisma-query-engine-debian-openssl-3.0.x" -type f -exec chmod +x {} \; 2>/dev/null || true

# List files to debug
echo "Checking for binaries..."
ls -la /opt/render/project/src/prisma* 2>/dev/null || echo "No binaries in src root"
ls -la /opt/render/project/src/prisma_binaries/ 2>/dev/null || echo "No binaries in prisma_binaries"

# Wait for file system to settle
sleep 2

# Start the application
echo "Starting FastAPI application..."
cd /opt/render/project/src
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}