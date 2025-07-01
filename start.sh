#!/bin/bash

echo "Starting application setup..."

# Fetch Prisma binaries at runtime
echo "Fetching Prisma binaries..."
prisma generate
prisma py fetch --force

# Wait a moment for binaries to be properly set up
sleep 2

# Start the application using the PORT environment variable
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}