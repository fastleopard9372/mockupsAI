#!/bin/bash
set -e

echo "Starting build process..."

# Install Python dependencies
pip install -r requirements.txt

echo "Setting up Prisma..."

# Generate Prisma client
python -m prisma generate

# Force fetch binaries
python -m prisma py fetch --force

# Create directories
mkdir -p prisma_binaries

echo "Copying Prisma binaries to expected locations..."

# Use Python to handle binary placement
python3 << 'EOF'
import os
import shutil
import subprocess
from pathlib import Path

def find_binary():
    """Find the Prisma query engine binary"""
    possible_paths = [
        os.path.expanduser("~/.cache/prisma-python/binaries/"),
        ".venv/lib/python3.11/site-packages/prisma/binaries/",
        "/opt/render/project/src/.venv/lib/python3.11/site-packages/prisma/binaries/",
    ]
    
    for base_path in possible_paths:
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if "query-engine" in file and ("debian" in file or "linux" in file):
                        return os.path.join(root, file)
    return None

def copy_binary_to_locations(source_binary):
    """Copy binary to all expected locations"""
    target_locations = [
        "prisma-query-engine-debian-openssl-3.0.x",
        "prisma_binaries/prisma-query-engine-debian-openssl-3.0.x",
        "/opt/render/project/src/prisma-query-engine-debian-openssl-3.0.x",
        "/opt/render/project/src/prisma_binaries/prisma-query-engine-debian-openssl-3.0.x"
    ]
    
    for target in target_locations:
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(target), exist_ok=True)
            
            # Copy binary
            shutil.copy2(source_binary, target)
            
            # Make executable
            os.chmod(target, 0o755)
            
            print(f"✓ Copied binary to: {target}")
        except Exception as e:
            print(f"✗ Failed to copy to {target}: {e}")

# Find and copy binary
binary_path = find_binary()
if binary_path:
    print(f"Found binary at: {binary_path}")
    copy_binary_to_locations(binary_path)
    
    # Verify it's executable
    try:
        result = subprocess.run([binary_path, "--version"], capture_output=True, text=True, timeout=10)
        print(f"Binary version check: {result.stdout.strip()}")
    except Exception as e:
        print(f"Binary verification failed: {e}")
else:
    print("ERROR: Could not find Prisma query engine binary!")
    exit(1)

EOF

echo "Listing final binary locations:"
find . -name "*query-engine*" -type f 2>/dev/null || echo "No binaries found"

echo "Build completed successfully!"