#!/bin/bash

# Fetch Prisma binaries at runtime if they don't exist
if [ ! -d "/opt/render/.cache/prisma-python/binaries" ]; then
    echo "Fetching Prisma binaries..."
    prisma py fetch --force
fi

# Start the application
uvicorn app.main:app --host 0.0.0.0 --port $PORT