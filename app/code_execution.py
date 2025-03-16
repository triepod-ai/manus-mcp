"""
Code execution module for Manus MCP.

This module will provide tools for executing code in various languages, including:
- Python
- JavaScript
- Shell commands
"""

from typing import Dict, Any
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
import subprocess

# Configure logger
logger = logging.getLogger("manus-mcp")

# Sandbox configuration
SANDBOX_DIR = os.path.expanduser(os.getenv("SANDBOX_DIR", "~/manus-sandbox"))
os.makedirs(SANDBOX_DIR, exist_ok=True)
logger.info(f"Using sandbox directory: {SANDBOX_DIR}")

def resolve_sandbox_path(filename: str) -> Path:
    """
    Resolve a filename to a path within the sandbox directory.
    
    Args:
        filename: The name of the file within the sandbox.
        
    Returns:
        A Path object pointing to the file within the sandbox.
        
    Raises:
        ValueError: If the filename tries to escape the sandbox.
    """
    # Convert to Path object and resolve to absolute path
    sandbox_path = Path(SANDBOX_DIR).resolve()
    file_path = (sandbox_path / filename).resolve()
    
    # Check if the resolved path is within the sandbox
    if not str(file_path).startswith(str(sandbox_path)):
        raise ValueError(f"File path {filename} attempts to escape the sandbox")
    
    return file_path

async def interpreter(action: str, filename: str = None, content: str = None, 
                     language: str = None, timeout: int = 10) -> str:
    """
    Read, write, and execute files in a local sandbox environment.
    
    This tool allows you to create, read, and execute code files in various programming languages
    within a secure sandbox environment.
    
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
    try:
        if action == "list":
            logger.info("Listing files in sandbox")
            sandbox_path = Path(SANDBOX_DIR)
            files = [f.name for f in sandbox_path.iterdir() if f.is_file()]
            return json.dumps({"files": files})
        
        elif action == "read":
            if not filename:
                return "Error: Filename is required for 'read' action"
            
            file_path = resolve_sandbox_path(filename)
            logger.info(f"Reading file: {file_path}")
            
            if not file_path.exists():
                return f"Error: File '{filename}' does not exist"
            
            with open(file_path, "r") as f:
                content = f.read()
            
            return content
        
        elif action == "write":
            if not filename or content is None:
                return "Error: Filename and content are required for 'write' action"
            
            file_path = resolve_sandbox_path(filename)
            logger.info(f"Writing to file: {file_path}")
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w") as f:
                f.write(content)
            
            return f"Successfully wrote {len(content)} bytes to {filename}"
        
        elif action == "execute":
            if (not filename and not content) or not language:
                return "Error: Either filename or content, and language are required for 'execute' action"
            
            # Determine the command to run based on the language
            cmd = None
            temp_file = None
            
            if filename:
                file_path = resolve_sandbox_path(filename)
                if not file_path.exists():
                    return f"Error: File '{filename}' does not exist"
            else:
                # Create a temporary file with the content
                suffix_map = {
                    "python": ".py",
                    "javascript": ".js",
                    "node": ".js",
                    "bash": ".sh",
                    "sh": ".sh",
                    "ruby": ".rb",
                    "perl": ".pl",
                    "r": ".r"
                }
                suffix = suffix_map.get(language.lower(), ".txt")
                
                temp_file = tempfile.NamedTemporaryFile(suffix=suffix, dir=SANDBOX_DIR, delete=False)
                temp_file.write(content.encode())
                temp_file.close()
                file_path = Path(temp_file.name)
            
            # Set up the command based on the language
            if language.lower() in ["python", "py"]:
                cmd = ["python", str(file_path)]
            elif language.lower() in ["javascript", "js", "node"]:
                cmd = ["node", str(file_path)]
            elif language.lower() in ["bash", "sh"]:
                cmd = ["bash", str(file_path)]
            elif language.lower() == "ruby":
                cmd = ["ruby", str(file_path)]
            elif language.lower() == "perl":
                cmd = ["perl", str(file_path)]
            elif language.lower() == "r":
                cmd = ["Rscript", str(file_path)]
            else:
                if temp_file:
                    os.unlink(temp_file.name)
                return f"Error: Unsupported language '{language}'"
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            try:
                # Run the command with a timeout
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=SANDBOX_DIR
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
                    stdout = stdout.decode()
                    stderr = stderr.decode()
                    
                    result = {
                        "exit_code": process.returncode,
                        "stdout": stdout,
                        "stderr": stderr
                    }
                    
                    return json.dumps(result, indent=2)
                
                except asyncio.TimeoutError:
                    # Kill the process if it times out
                    process.kill()
                    return f"Error: Execution timed out after {timeout} seconds"
            
            finally:
                # Clean up temporary file if created
                if temp_file:
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
        
        else:
            return f"Error: Unknown action '{action}'"
    
    except ValueError as e:
        logger.error(f"Sandbox path validation error: {str(e)}")
        return f"Error: {str(e)}"
    
    except Exception as e:
        logger.error(f"Interpreter action '{action}' failed: {str(e)}")
        return f"Error performing interpreter action: {str(e)}"


async def execute_python(code: str) -> Dict[str, Any]:
    """
    Executes Python code safely in a sandbox.
    
    Args:
        code: The Python code to execute
        
    Returns:
        Dict with execution results, output, and errors
    """
    # TODO: Implement Python code execution
    raise NotImplementedError("Python code execution is not yet implemented.")


async def execute_javascript(code: str) -> Dict[str, Any]:
    """
    Executes JavaScript code safely in a sandbox.
    
    Args:
        code: The JavaScript code to execute
        
    Returns:
        Dict with execution results, output, and errors
    """
    # TODO: Implement JavaScript code execution
    raise NotImplementedError("JavaScript code execution is not yet implemented.")


async def execute_shell(command: str) -> Dict[str, Any]:
    """
    Executes a shell command safely.
    
    Args:
        command: The shell command to execute
        
    Returns:
        Dict with execution results, output, and errors
    """
    # TODO: Implement shell command execution
    raise NotImplementedError("Shell command execution is not yet implemented.") 