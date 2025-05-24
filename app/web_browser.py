"""
Web browsing module for Manus MCP.

This module provides tools for browsing the web using Chrome DevTools Protocol.
"""

import asyncio
import json
import os
import websockets
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup


class ChromeBrowser:
    """Chrome browser automation using DevTools Protocol."""
    
    def __init__(self, chrome_host: str = None, chrome_port: int = None):
        self.chrome_host = chrome_host or os.getenv("CHROME_MCP_HOST", "localhost")
        self.chrome_port = chrome_port or int(os.getenv("CHROME_MCP_PORT", "9229"))
        self.ws_url = None
        self.websocket = None
        self.tab_id = None
        self.request_id = 0
    
    async def connect(self) -> bool:
        """Connect to Chrome DevTools."""
        try:
            # Get available tabs
            response = requests.get(f"http://{self.chrome_host}:{self.chrome_port}/json")
            tabs = response.json()
            
            if not tabs:
                return False
            
            # Use first available tab or create new one
            tab = tabs[0]
            self.tab_id = tab['id']
            self.ws_url = tab['webSocketDebuggerUrl']
            
            # Connect via WebSocket
            self.websocket = await websockets.connect(self.ws_url)
            
            # Enable necessary domains
            await self._send_command("Runtime.enable")
            await self._send_command("Page.enable")
            
            return True
        except Exception as e:
            # Don't print to avoid MCP protocol contamination
            return False
    
    async def _send_command(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send command to Chrome DevTools."""
        self.request_id += 1
        command = {
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        await self.websocket.send(json.dumps(command))
        
        while True:
            response = json.loads(await self.websocket.recv())
            if response.get("id") == self.request_id:
                return response
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL."""
        try:
            if not self.websocket:
                if not await self.connect():
                    return {"success": False, "error": "Failed to connect to Chrome"}
            
            response = await self._send_command("Page.navigate", {"url": url})
            
            # Wait for page load
            await asyncio.sleep(2)
            
            return {"success": True, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_content(self) -> Dict[str, Any]:
        """Get page content."""
        try:
            # Get document
            response = await self._send_command("Runtime.evaluate", {
                "expression": "document.documentElement.outerHTML"
            })
            
            # Handle Chrome DevTools Protocol response format
            if ("result" in response and 
                "result" in response["result"] and 
                "value" in response["result"]["result"]):
                html = response["result"]["result"]["value"]
                return {"success": True, "html": html}
            else:
                return {"success": False, "error": "Failed to get page content"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()


# Global browser instance
_browser = None


async def _get_browser() -> ChromeBrowser:
    """Get or create browser instance."""
    global _browser
    if _browser is None:
        _browser = ChromeBrowser()
    return _browser


async def fetch_webpage(url: str) -> Dict[str, Any]:
    """
    Fetches a webpage from the given URL using Chrome DevTools Protocol.
    
    Args:
        url: The URL to fetch
        
    Returns:
        Dict with the page content and metadata
    """
    try:
        browser = await _get_browser()
        
        # Navigate to URL
        nav_result = await browser.navigate(url)
        if not nav_result["success"]:
            return nav_result
        
        # Get page content
        content_result = await browser.get_content()
        if not content_result["success"]:
            return content_result
        
        # Extract metadata
        html = content_result["html"]
        soup = BeautifulSoup(html, 'html.parser')
        
        title = soup.title.string if soup.title else "No title"
        meta_description = ""
        if soup.find("meta", {"name": "description"}):
            meta_description = soup.find("meta", {"name": "description"}).get("content", "")
        
        return {
            "success": True,
            "url": url,
            "title": title,
            "description": meta_description,
            "html": html,
            "text": soup.get_text(strip=True, separator=' ')
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def extract_content(html: str) -> Dict[str, Any]:
    """
    Extracts relevant content from HTML.
    
    Args:
        html: The HTML content to extract from
        
    Returns:
        Dict with extracted content
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text
        text = soup.get_text(strip=True, separator=' ')
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            links.append({
                "text": link.get_text(strip=True),
                "href": link['href']
            })
        
        # Extract images
        images = []
        for img in soup.find_all('img', src=True):
            images.append({
                "alt": img.get('alt', ''),
                "src": img['src']
            })
        
        # Extract title
        title = soup.title.string if soup.title else ""
        
        return {
            "success": True,
            "title": title,
            "text": text,
            "links": links,
            "images": images
        }
    except Exception as e:
        return {"success": False, "error": str(e)} 