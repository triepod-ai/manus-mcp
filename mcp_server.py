from typing import Any, Dict, List, Optional
import asyncio
import logging
import os
import json
import sys
from dotenv import load_dotenv
from googlesearch import search
from mcp.server import FastMCP
from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext
from app.code_execution import interpreter, bash_command, SANDBOX_DIR

# Load environment variables
load_dotenv()

# Configure logging to write to a file instead of stdout/stderr
log_dir = os.path.expanduser("~/manus-mcp-logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "manus-mcp.log")

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file,
    filemode="a"
)
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

# Google Search configuration
GOOGLE_SEARCH_MAX_RESULTS = int(os.getenv("GOOGLE_SEARCH_MAX_RESULTS", "10"))

# Browser configuration
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
CHROME_INSTANCE_PATH = os.getenv("CHROME_INSTANCE_PATH", None)

# Log sandbox directory
logger.info(f"Using sandbox directory: {SANDBOX_DIR}")

# Create the MCP server
mcp = FastMCP("manus-mcp")

# Note: auto_invoke=True is not supported in MCP 1.4.1
# To automatically invoke a tool at the start of a conversation,
# you would need to implement a custom handler or upgrade to a newer version of MCP

# Browser instance (will be initialized on first use)
browser = None
browser_context = None
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
    """Ensure browser and context are initialized."""
    global browser, browser_context
    
    if browser is None:
        logger.info(f"Initializing browser (headless: {BROWSER_HEADLESS}, chrome_instance_path: {CHROME_INSTANCE_PATH})...")
        browser_config = BrowserConfig(
            headless=BROWSER_HEADLESS,
            chrome_instance_path=CHROME_INSTANCE_PATH
        )
        browser = BrowserUseBrowser(browser_config)
    
    if browser_context is None:
        logger.info("Creating new browser context...")
        browser_context = await browser.new_context()
    
    return browser_context

# Define the browser tool
@mcp.tool()
async def browse_web(action: str, url: str = None, element_index: int = None, 
                    text: str = None, script: str = None, 
                    scroll_amount: int = None) -> str:
    """
    Interact with a web browser to navigate websites and extract information.
    
    This tool allows you to control a browser to visit websites, click elements,
    input text, take screenshots, and more.
    
    Args:
        action: The browser action to perform. Options include:
            - 'navigate': Go to a specific URL
            - 'click': Click an element by index
            - 'input_text': Input text into an element
            - 'get_content': Get the page content
            - 'execute_js': Execute JavaScript code
            - 'scroll': Scroll the page
            - 'refresh': Refresh the current page
        url: URL for 'navigate' action
        element_index: Element index for 'click' or 'input_text' actions
        text: Text for 'input_text' action
        script: JavaScript code for 'execute_js' action
        scroll_amount: Pixels to scroll (positive for down, negative for up)
    
    Returns:
        A string with the result of the action
    """
    async with browser_lock:
        try:
            context = await ensure_browser_initialized()
            
            if action == "navigate":
                if not url:
                    return "Error: URL is required for 'navigate' action"
                logger.info(f"Navigating to URL: {url}")
                await context.navigate_to(url)
                return f"Successfully navigated to {url}"
            
            elif action == "click":
                if element_index is None:
                    return "Error: Element index is required for 'click' action"
                logger.info(f"Clicking element at index: {element_index}")
                element = await context.get_dom_element_by_index(element_index)
                if not element:
                    return f"Error: Element with index {element_index} not found"
                download_path = await context._click_element_node(element)
                result = f"Clicked element at index {element_index}"
                if download_path:
                    result += f" - Downloaded file to {download_path}"
                return result
            
            elif action == "input_text":
                if element_index is None or not text:
                    return "Error: Element index and text are required for 'input_text' action"
                logger.info(f"Inputting text into element at index: {element_index}")
                element = await context.get_dom_element_by_index(element_index)
                if not element:
                    return f"Error: Element with index {element_index} not found"
                await context._input_text_element_node(element, text)
                return f"Input '{text}' into element at index {element_index}"
            
            elif action == "get_content":
                logger.info("Getting page content")
                state = await context.get_state()
                html = await context.get_page_html()
                
                # Truncate HTML to avoid overwhelming the response
                truncated_html = html[:5000] + "..." if len(html) > 5000 else html
                
                # Get clickable elements
                clickable_elements = state.element_tree.clickable_elements_to_string()
                
                result = {
                    "url": state.url,
                    "title": state.title,
                    "content": truncated_html,
                    "clickable_elements": clickable_elements
                }
                
                return json.dumps(result, indent=2)
            
            elif action == "execute_js":
                if not script:
                    return "Error: Script is required for 'execute_js' action"
                logger.info(f"Executing JavaScript: {script}")
                result = await context.execute_javascript(script)
                return f"JavaScript execution result: {result}"
            
            elif action == "scroll":
                if scroll_amount is None:
                    return "Error: Scroll amount is required for 'scroll' action"
                logger.info(f"Scrolling page by {scroll_amount} pixels")
                await context.execute_javascript(f"window.scrollBy(0, {scroll_amount});")
                direction = "down" if scroll_amount > 0 else "up"
                return f"Scrolled {direction} by {abs(scroll_amount)} pixels"
            
            elif action == "refresh":
                logger.info("Refreshing page")
                await context.refresh_page()
                return "Page refreshed"
            
            else:
                return f"Error: Unknown action '{action}'"
        
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
    # Run the server with stdio transport
    mcp.run(transport='stdio') 