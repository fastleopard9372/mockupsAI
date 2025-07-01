#!/bin/bash

echo "Starting FastAPI application..."

# Verify binaries are available (should be set up by build.sh)
echo "Checking for Prisma binaries..."
if [ -f "prisma-query-engine-debian-openssl-3.0.x" ]; then
    echo "✓ Binary found: prisma-query-engine-debian-openssl-3.0.x"
elif [ -f "prisma_binaries/prisma-query-engine-debian-openssl-3.0.x" ]; then
    echo "✓ Binary found: prisma_binaries/prisma-query-engine-debian-openssl-3.0.x"
else
    echo "⚠ Warning: Prisma binary not found in expected locations"
    echo "Available files:"
    find . -name "*query-engine*" -type f 2>/dev/null || echo "No query engine binaries found"
fi

# Set environment variables
export PRISMA_SKIP_POSTINSTALL_GENERATE=true

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}