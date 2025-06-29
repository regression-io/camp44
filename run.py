#!/usr/bin/env python3
"""
Development runner script for the camp44 application.
This script can be used in PyCharm to run the application with proper environment setup.
"""
import subprocess
import sys
from pathlib import Path


def main():
    """Run the application using uvicorn with uv."""
    project_root = Path(__file__).parent

    # Change to project directory
    import os
    os.chdir(project_root)

    # Run with uv
    cmd = [
        "uv", "run",
        "uvicorn",
        "camp44.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to start the application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Application stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
