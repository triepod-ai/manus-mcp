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

# Create the MCP server
mcp = FastMCP("manus-mcp")

# Browser instance (will be initialized on first use)
browser = None
browser_context = None
browser_lock = asyncio.Lock()

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
        logger.info(f"Initializing browser (headless: {BROWSER_HEADLESS})...")
        browser = BrowserUseBrowser(BrowserConfig(
            headless=BROWSER_HEADLESS
        ))
    
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

if __name__ == "__main__":
    # Run the server with stdio transport
    mcp.run(transport='stdio') 