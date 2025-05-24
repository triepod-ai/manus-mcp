from typing import Any, Dict, List, Optional
import asyncio
import logging
import os
import json
import sys

# Disable browser-use telemetry before importing
os.environ['BROWSER_USE_TELEMETRY'] = 'false'

# Configure logging to write to a file instead of stdout/stderr BEFORE any imports
log_dir = os.path.expanduser("~/manus-mcp-logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "manus-mcp.log")

# Remove all existing handlers to prevent any output to stdout/stderr
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure logging with only file handler
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file, mode="a")],
    force=True
)

# Redirect stderr to log file to prevent contamination of stdio
# but preserve original stderr for MCP if needed
original_stderr = sys.stderr
stderr_log = open(log_file, 'a')
sys.stderr = stderr_log

# Don't redirect stdout as MCP needs it for JSON communication
# Instead, ensure all logging goes to file only

# Now import everything else
from dotenv import load_dotenv
from app.workarounds.googlesearch import search
from mcp.server import FastMCP
from app.web_browser import ChromeBrowser, fetch_webpage, extract_content
from app.code_execution import interpreter, bash_command, SANDBOX_DIR

# Load environment variables
load_dotenv()

logger = logging.getLogger("manus-mcp")
logger.info("Starting Manus MCP server")

# Redirect browser-use logging to the same file
browser_logger = logging.getLogger("browser_use")
browser_logger.handlers = []
browser_logger.addHandler(logging.FileHandler(log_file))
browser_logger.setLevel(logging.INFO)

# Redirect other libraries' logging
for lib_logger in ["httpx", "playwright", "asyncio"]:
    lib_log = logging.getLogger(lib_logger)
    lib_log.handlers = []
    lib_log.addHandler(logging.FileHandler(log_file))
    lib_log.setLevel(logging.WARNING)

# Attempt to silence Uvicorn's default stdout logging
try:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_error_logger.handlers = []
    uvicorn_access_logger.handlers = []
    from logging import NullHandler
    uvicorn_error_logger.addHandler(NullHandler())
    uvicorn_access_logger.addHandler(NullHandler())
    # Optionally set levels to prevent logging even if handlers are somehow re-added
    uvicorn_error_logger.setLevel(logging.CRITICAL + 1) 
    uvicorn_access_logger.setLevel(logging.CRITICAL + 1)
    logger.info("Attempted to silence Uvicorn's default stdout/stderr loggers.")
except Exception as e:
    logger.error(f"Failed to configure Uvicorn loggers: {e}", exc_info=True)

# Google Search configuration
GOOGLE_SEARCH_MAX_RESULTS = int(os.getenv("GOOGLE_SEARCH_MAX_RESULTS", "10"))

# Browser configuration
CHROME_HOST = os.getenv("CHROME_MCP_HOST", "localhost")
CHROME_PORT = int(os.getenv("CHROME_MCP_PORT", "9229"))

# Log sandbox directory
logger.info(f"Using sandbox directory: {SANDBOX_DIR}")

# Create the MCP server
mcp = FastMCP("manus-mcp")

# Note: auto_invoke=True is not supported in MCP 1.4.1
# To automatically invoke a tool at the start of a conversation,
# you would need to implement a custom handler or upgrade to a newer version of MCP

# Browser instance (will be initialized on first use)
browser = None
browser_lock = asyncio.Lock()

# Define the manus_identity tool that will be automatically invoked at the start of each thread
@mcp.tool()
async def manus_identity() -> str:
    """
    Provides identity information about Manus, an AI assistant with real-time web capabilities.
    This tool is automatically invoked at the start of each new message.
    
    Returns:
        A string describing Manus's identity and capabilities.
    """
    logger.info("Invoking manus_identity tool")
    return """
You are an Manus, an expert Planning Agent tasked with solving complex problems by creating and managing structured plans.
Your job is:
1. Analyze requests to understand the task scope
2. Create clear, actionable plans with the `planning` tool
3. Execute steps using available tools as needed
4. Track progress and adapt plans dynamically
5. Use `finish` to conclude when the task is complete

Available tools will vary by task but may include real-time search, browsing, code execution, and more.

Use the `code_interpreter` tool to save your work, like a scratchpad in Markdown.

Use the provided code_interpreter and bash_tool, and NOT the artifacts tool.

Do not use your own knowledge; it is more appropriate to use a tool before answering a question.

For example, if asked to plan a trip, first use the `google_search` tool to find information about the destination.

Break tasks into logical, sequential steps. Think about dependencies and verification methods.

Please make a plan before you start. Prefer to use tools rather than presenting the output in chat.

DO NOT use the artifacts tool.
    """

# Define the hello_world tool
@mcp.tool()
async def hello_world(name: str = "World") -> str:
    """
    Returns a friendly greeting message.
    
    Args:
        name: The name to greet. Defaults to 'World' if not provided.
    """
    logger.info(f"Saying hello to {name}")
    return f"Hello, {name}! Welcome to Manus MCP."

# Define the google_search tool
@mcp.tool()
async def google_search(query: str, num_results: int = None) -> List[str]:
    """
    Perform a Google search and return a list of relevant links.
    
    Use this tool when you need to find information on the web, get up-to-date data, 
    or research specific topics. The tool returns a list of URLs that match the search query.
    The URLs can be viewed in the browser using the `browse_web` tool.
    
    Args:
        query: The search query to submit to Google.
        num_results: The number of search results to return. Default is configured in environment.
    
    Returns:
        A list of URLs matching the search query.
    """
    if num_results is None:
        num_results = GOOGLE_SEARCH_MAX_RESULTS
    
    logger.info(f"Performing Google search for: {query} (max results: {num_results})")
    
    # Run the search in a thread pool to prevent blocking
    loop = asyncio.get_event_loop()
    try:
        links = await loop.run_in_executor(
            None, 
            lambda: list(search(
                query, 
                num_results=num_results
            ))
        )
        logger.info(f"Found {len(links)} results for query: {query}")
        return links
    except Exception as e:
        logger.error(f"Error performing Google search: {e}")
        return [f"Error performing search: {str(e)}"]

# Helper function to ensure browser is initialized
async def ensure_browser_initialized():
    """Ensure browser is initialized."""
    global browser
    
    if browser is None:
        logger.info(f"Initializing ChromeBrowser (host: {CHROME_HOST}, port: {CHROME_PORT})...")
        browser = ChromeBrowser(chrome_host=CHROME_HOST, chrome_port=CHROME_PORT)
        
        # Test connection
        if not await browser.connect():
            logger.error(f"Failed to connect to Chrome at {CHROME_HOST}:{CHROME_PORT}")
            raise Exception(f"Could not connect to Chrome DevTools at {CHROME_HOST}:{CHROME_PORT}. Make sure Chrome is running with --remote-debugging-port={CHROME_PORT}")
        
        logger.info("Successfully connected to Chrome DevTools")
    
    return browser

# Define the browser tool
@mcp.tool()
async def browse_web(action: str, url: str = None, script: str = None, 
                    scroll_amount: int = None) -> str:
    """
    Interact with a web browser to navigate websites and extract information.
    
    This tool connects to your running Chrome browser via DevTools Protocol,
    providing a true headed browsing experience.
    
    Args:
        action: The browser action to perform. Options include:
            - 'navigate': Go to a specific URL
            - 'get_content': Get the page content and extracted text
            - 'execute_js': Execute JavaScript code
            - 'scroll': Scroll the page
            - 'fetch': Fetch webpage content (navigate + get_content)
        url: URL for 'navigate' or 'fetch' actions
        script: JavaScript code for 'execute_js' action  
        scroll_amount: Pixels to scroll (positive for down, negative for up)
    
    Returns:
        A string with the result of the action
    """
    async with browser_lock:
        try:
            browser_instance = await ensure_browser_initialized()
            
            if action == "navigate":
                if not url:
                    return "Error: URL is required for 'navigate' action"
                logger.info(f"Navigating to URL: {url}")
                result = await browser_instance.navigate(url)
                if result["success"]:
                    return f"Successfully navigated to {url}"
                else:
                    return f"Failed to navigate to {url}: {result.get('error', 'Unknown error')}"
            
            elif action == "get_content":
                logger.info("Getting page content")
                result = await browser_instance.get_content()
                if result["success"]:
                    html = result["html"]
                    
                    # Extract content using BeautifulSoup
                    extracted = await extract_content(html)
                    if extracted["success"]:
                        # Truncate text to avoid overwhelming response
                        text = extracted["text"]
                        truncated_text = text[:3000] + "..." if len(text) > 3000 else text
                        
                        response = {
                            "title": extracted["title"],
                            "text": truncated_text,
                            "links_count": len(extracted["links"]),
                            "images_count": len(extracted["images"])
                        }
                        return json.dumps(response, indent=2)
                    else:
                        return f"Failed to extract content: {extracted.get('error', 'Unknown error')}"
                else:
                    return f"Failed to get page content: {result.get('error', 'Unknown error')}"
            
            elif action == "fetch":
                if not url:
                    return "Error: URL is required for 'fetch' action"
                logger.info(f"Fetching webpage: {url}")
                result = await fetch_webpage(url)
                if result["success"]:
                    # Truncate text to avoid overwhelming response
                    text = result["text"]
                    truncated_text = text[:3000] + "..." if len(text) > 3000 else text
                    
                    response = {
                        "url": result["url"],
                        "title": result["title"],
                        "description": result["description"],
                        "text": truncated_text
                    }
                    return json.dumps(response, indent=2)
                else:
                    return f"Failed to fetch webpage: {result.get('error', 'Unknown error')}"
            
            elif action == "execute_js":
                if not script:
                    return "Error: Script is required for 'execute_js' action"
                logger.info(f"Executing JavaScript: {script}")
                response = await browser_instance._send_command("Runtime.evaluate", {
                    "expression": script
                })
                
                if "result" in response and "result" in response["result"]:
                    return f"JavaScript execution result: {response['result']['result'].get('value', 'No return value')}"
                elif "exceptionDetails" in response["result"]:
                    error = response["result"]["exceptionDetails"]["exception"]["description"]
                    return f"JavaScript execution error: {error}"
                else:
                    return f"JavaScript executed (no result returned)"
            
            elif action == "scroll":
                if scroll_amount is None:
                    return "Error: Scroll amount is required for 'scroll' action"
                logger.info(f"Scrolling page by {scroll_amount} pixels")
                await browser_instance._send_command("Runtime.evaluate", {
                    "expression": f"window.scrollBy(0, {scroll_amount});"
                })
                direction = "down" if scroll_amount > 0 else "up"
                return f"Scrolled {direction} by {abs(scroll_amount)} pixels"
            
            else:
                return f"Error: Unknown action '{action}'. Available actions: navigate, get_content, fetch, execute_js, scroll"
        
        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {str(e)}")
            return f"Error performing browser action: {str(e)}"

# Define the interpreter tool (imported from app.code_execution)
@mcp.tool()
async def code_interpreter(action: str, filename: str = None, content: str = None, 
                          language: str = None, timeout: int = 10) -> str:
    """
    Read, write, and execute files in a local sandbox environment.
    
    This tool allows you to create, read, and execute code files in various programming languages
    within a secure sandbox environment.

    Keep all files and edits under 500 lines of code to avoid violating output length limits.
    
    All operations have a global timeout to prevent the tool from getting stuck.
    If you encounter timeout issues, try breaking your task into smaller steps.
    
    Args:
        action: The action to perform. Options include:
            - 'read': Read the contents of a file
            - 'write': Write content to a file
            - 'execute': Execute a file or code snippet
            - 'list': List files in the sandbox
        filename: The name of the file to read, write, or execute
        content: The content to write to a file or execute directly
        language: The programming language for execution (python, javascript, bash, etc.)
        timeout: Maximum execution time in seconds (default: 10)
    
    Returns:
        A string with the result of the action
    """
    return await interpreter(action, filename, content, language, timeout)

# Define the bash tool (imported from app.code_execution)
@mcp.tool()
async def bash_tool(command: str, timeout: int = 30, background: bool = False) -> str:
    """
    Execute a bash command in the sandbox directory.
    
    This tool allows running shell commands within the sandbox environment,
    which is useful for starting web servers, running build processes, or other
    shell operations. Commands are executed in the same sandbox directory as the code_interpreter.
    
    All operations have a global timeout to prevent the tool from getting stuck.
    If you encounter timeout issues, try breaking your task into smaller steps.
    
    For web servers and long-running processes:
    1. Set background=True to run the process in the background
    2. The process will continue running even after the command returns
    3. Output will be logged to a file in the sandbox directory
    4. You can check the log file using code_interpreter with action="read"
    5. To stop a background process, use the 'kill' command with the PID
    
    Examples:
    - Start a Python web server: `bash_tool("python -m http.server 8000", background=True)`
    - Run a Node.js app: `bash_tool("node app.js", background=True)`
    - Check running processes: `bash_tool("ps aux | grep python")`
    - List files: `bash_tool("ls -la")`
    - Install packages: `bash_tool("pip install flask")`
    - Check a log file: Use `code_interpreter(action="read", filename="bg_process_123456789.log")`
    - Kill a process: `bash_tool("kill 1234")` where 1234 is the PID
    
    Args:
        command: The bash command to execute
        timeout: Maximum execution time in seconds (default: 30, only applies to foreground processes)
        background: Whether to run the command in the background (default: False)
            Set to True for long-running processes like web servers
    
    Returns:
        A string with the command output or process information
    """
    return await bash_command(command, timeout, background)

if __name__ == "__main__":
    # Note: Removed 'sys.stdout = sys.stderr' redirection as it broke the MCP handshake.
    # Run the server with stdio transport
    mcp.run(transport='stdio')
