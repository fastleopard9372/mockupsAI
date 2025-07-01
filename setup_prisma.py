#!/usr/bin/env python3
"""
Setup script to ensure Prisma binaries are available at runtime.
This can be imported and called from your application startup.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def setup_prisma_binaries():
    """Ensure Prisma binaries are available in expected locations."""
    print("Setting up Prisma binaries...")
    
    # Find the binary
    binary_path = find_prisma_binary()
    if not binary_path:
        print("ERROR: Could not find Prisma query engine binary!")
        # Try to fetch again
        try:
            subprocess.run([sys.executable, "-m", "prisma", "py", "fetch", "--force"], check=True)
            binary_path = find_prisma_binary()
        except subprocess.CalledProcessError as e:
            print(f"Failed to fetch Prisma binaries: {e}")
            return False
    
    if not binary_path:
        print("ERROR: Still could not find Prisma binary after fetch!")
        return False
    
    print(f"Found Prisma binary at: {binary_path}")
    
    # Copy to expected locations
    success = copy_binary_to_expected_locations(binary_path)
    
    if success:
        print("✓ Prisma binaries setup completed successfully")
        return True
    else:
        print("✗ Failed to setup Prisma binaries")
        return False


def find_prisma_binary():
    """Find the Prisma query engine binary in common locations."""
    possible_paths = [
        os.path.expanduser("~/.cache/prisma-python/binaries/"),
        ".venv/lib/python3.11/site-packages/prisma/binaries/",
        "/opt/render/project/src/.venv/lib/python3.11/site-packages/prisma/binaries/",
        "venv/lib/python3.11/site-packages/prisma/binaries/",
    ]
    
    for base_path in possible_paths:
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if "query-engine" in file and ("debian" in file or "linux" in file):
                        full_path = os.path.join(root, file)
                        if os.access(full_path, os.X_OK):
                            return full_path
    
    return None


def copy_binary_to_expected_locations(source_binary):
    """Copy binary to all expected locations."""
    target_locations = [
        "prisma-query-engine-debian-openssl-3.0.x",
        "prisma_binaries/prisma-query-engine-debian-openssl-3.0.x",
    ]
    
    success_count = 0
    
    for target in target_locations:
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(target), exist_ok=True)
            
            # Copy binary
            shutil.copy2(source_binary, target)
            
            # Make executable
            os.chmod(target, 0o755)
            
            print(f"✓ Copied binary to: {target}")
            success_count += 1
        except Exception as e:
            print(f"✗ Failed to copy to {target}: {e}")
    
    return success_count > 0


if __name__ == "__main__":
    success = setup_prisma_binaries()
    sys.exit(0 if success else 1)