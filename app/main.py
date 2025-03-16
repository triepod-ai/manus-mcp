from typing import Any, Dict
import logging
from fastapi import FastAPI
from mcp.server import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("manus-mcp")

# Create the FastAPI app
app = FastAPI(title="Manus MCP Server")

# Create the MCP server
mcp_server = FastMCP(app=app, name="manus-mcp")

# Define the hello_world tool
@mcp_server.tool()
async def hello_world(name: str = "World") -> str:
    """
    Returns a friendly greeting message.
    
    Args:
        name: The name to greet. Defaults to 'World' if not provided.
    """
    logger.info(f"Saying hello to {name}")
    return f"Hello, {name}! Welcome to Manus MCP."

# Create a simple root endpoint for the API
@app.get("/")
async def root():
    """Root endpoint that returns basic server information."""
    return {
        "name": "Manus MCP Server",
        "version": "0.1.0",
        "description": "An MCP server that can browse the web, perform search queries, and execute code.",
        "capabilities": [
            "hello_world"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 