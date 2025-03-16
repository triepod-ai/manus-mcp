# Manus MCP

<p align="center">
  <img src="meme.jpeg" alt="Manus MCP" width="50%">
  <img src="meme.jpg" alt="Manus MCP" width="50%">
</p>

A Model Context Protocol (MCP) server implementation that can browse the web, perform search queries, and execute code.

## Features (Planned)

- Web browsing
- Search queries
- Code execution

## Current Features

- Simple "hello_world" tool that returns a greeting message
- "google_search" tool that performs Google searches and returns relevant links
- "browse_web" tool that allows browsing websites, clicking elements, and extracting content

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

### Installation

#### Using Setup Script (Recommended)

```bash
./setup.sh
```

#### Manual Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/manus-mcp.git
   cd manus-mcp
   ```

2. Create a virtual environment and install dependencies
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e .        # Install the project and its dependencies
   ```

3. Run the server
   ```bash
   # Make sure your virtual environment is activated
   source .venv/bin/activate
   ./run.py
   # or
   uvicorn app.main:app --reload
   ```

4. Visit `http://localhost:8000/docs` to see the API documentation

## Using with Claude for Desktop

To use Manus MCP with Claude for Desktop:

1. Create or edit the Claude for Desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

2. Add the following configuration:
   ```json
   {
     "mcpServers": {
       "manus-mcp": {
         "command": "uv",
         "args": [
           "--directory",
           "/ABSOLUTE/PATH/TO/manus-mcp",
           "run",
           "mcp_server.py"
         ]
       }
     }
   }
   ```

3. Restart Claude for Desktop

4. You should now see the Manus MCP tools available in Claude for Desktop

## Available Tools

### hello_world

A simple greeting tool that returns a welcome message.

### google_search

Performs Google searches and returns a list of relevant links.

### browse_web

Interacts with a web browser to navigate websites and extract information. Supported actions:
- `navigate`: Go to a specific URL
- `click`: Click an element by index
- `input_text`: Input text into an element
- `get_content`: Get the page content
- `execute_js`: Execute JavaScript code
- `scroll`: Scroll the page
- `refresh`: Refresh the current page

## API Documentation

The API follows the [Model Context Protocol (MCP) specification](https://modelcontextprotocol.io/).

## Development

To install development dependencies:

```bash
uv pip install -e ".[dev]"
```

## License

[MIT](LICENSE) 