"""
run.py — Start the HR Management System API server.

Usage:
  python run.py                  # Start on default port 8000
  python run.py --port 9000      # Custom port
  python run.py --reload         # Auto-reload during development
"""

import argparse
import uvicorn

from src.config import API_HOST, API_PORT


def main():
    parser = argparse.ArgumentParser(description="Start the HR Management System API server")
    parser.add_argument("--host", default=API_HOST, help=f"Host to bind to (default: {API_HOST})")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"Port to bind to (default: {API_PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    print(f"""
+==================================================+
|   HR Management System - API Server              |
+==================================================+
|   Server  : http://{args.host}:{args.port}                 |
|   Docs    : http://localhost:{args.port}/docs             |
|   Health  : http://localhost:{args.port}/api/health       |
+==================================================+
    """)


    uvicorn.run(
        "src.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
