#!/bin/bash

echo "Starting application setup..."

# Ensure we're using Python's Prisma, not Node's
export PRISMA_SKIP_POSTINSTALL_GENERATE=true

# Remove any Node artifacts that might interfere
rm -rf node_modules prisma_binaries/node_modules 2>/dev/null || true

# Create prisma_binaries directory
mkdir -p prisma_binaries

# Generate Prisma Client for Python
echo "Generating Prisma Client for Python..."
python -m prisma generate

# Fetch binaries using Python with explicit download
echo "Fetching Prisma binaries via Python..."
python -m prisma py fetch --force

# Download binaries to prisma_binaries directory
echo "Downloaded binaries to prisma_binaries"
python -c "
import os
from prisma.binaries import platform
from prisma.binaries.binaries import BINARIES

# Ensure binaries are in the expected location
binary_name = f'prisma-query-engine-{platform()}'
source_paths = [
    os.path.expanduser(f'~/.cache/prisma-python/binaries/{platform()}/{binary_name}'),
    f'prisma_binaries/{binary_name}',
]

target_paths = [
    f'prisma-query-engine-debian-openssl-3.0.x',
    f'prisma_binaries/prisma-query-engine-debian-openssl-3.0.x',
]

import shutil
for src in source_paths:
    if os.path.exists(src):
        for target in target_paths:
            try:
                shutil.copy2(src, target)
                os.chmod(target, 0o755)
                print(f'Copied {src} to {target}')
            except Exception as e:
                print(f'Failed to copy to {target}: {e}')
        break
"

# List available binaries for debugging
echo "Available Prisma binaries:"
find . -name "*prisma*engine*" -type f 2>/dev/null || echo "No engine binaries found"
ls -la prisma_binaries/ 2>/dev/null || echo "No prisma_binaries directory"

# Verify binary exists and is executable
if [ -f "prisma-query-engine-debian-openssl-3.0.x" ]; then
    chmod +x prisma-query-engine-debian-openssl-3.0.x
    echo "Binary found and made executable"
elif [ -f "prisma_binaries/prisma-query-engine-debian-openssl-3.0.x" ]; then
    chmod +x prisma_binaries/prisma-query-engine-debian-openssl-3.0.x
    echo "Binary found in prisma_binaries and made executable"
else
    echo "Warning: Binary not found, trying manual fetch..."
    python -m prisma py fetch --force
fi

# Start the application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}