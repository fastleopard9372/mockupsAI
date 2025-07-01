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

#!/usr/bin/env bash# 
# pip install -r requirements.txt
# prisma generate 
# # Store/pull Prisma cache with build cache
# if [[! -d $PRISMA_BINARY_CACHE_DIR]]; 
# then echo "...Copying Prisma Binary Cache from Build Cache" 
#     cp -R $XDG_CACHE_HOME/prisma/binaries $PRISMA_BINARY_CACHE_DIR
# else 
#     echo "...Storing Prisma Binary Cache in Build Cache" 
#     cp -R $PRISMA_BINARY_CACHE_DIR $XDG_CACHE_HOME
# fi