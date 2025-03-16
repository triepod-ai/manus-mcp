#!/usr/bin/env python3
"""
Manus MCP Server Runner

This script runs the Manus MCP server.
"""

import os
import sys
import logging
from dotenv import load_dotenv
import uvicorn

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("manus-mcp")

def main():
    """Run the Manus MCP server."""
    try:
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        
        logger.info(f"Starting Manus MCP server on {host}:{port}")
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=True,
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 