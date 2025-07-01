#!/bin/bash

echo "Starting application setup..."

# Ensure Prisma CLI is available
echo "Installing Prisma CLI"
pip install prisma

# Generate Prisma Client
echo "Generating Prisma Client..."
prisma generate

# Fetch Prisma binaries with proper Python path
echo "Fetching Prisma binaries..."
python -m prisma py fetch --force

# Verify binaries exist
echo "Verifying Prisma setup..."
python -c "from prisma import Prisma; print('Prisma import successful')"

# Wait for binaries to settle
sleep 3

# Start the application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}