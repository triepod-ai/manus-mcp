# Manus MCP

A Model Context Protocol (MCP) server implementation that can browse the web, perform search queries, and execute code.

## Features (Planned)

- Web browsing
- Search queries
- Code execution

## Current Features

- Simple "hello_world" tool that returns a greeting message
- "google_search" tool that performs Google searches and returns relevant links

## Getting Started

### Prerequisites

- Python 3.10+
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

1. Copy the `claude_desktop_config.json` file to your Claude for Desktop configuration directory:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

2. Restart Claude for Desktop

3. You should now see the Manus MCP tools available in Claude for Desktop

## API Documentation

The API follows the [Model Context Protocol (MCP) specification](https://modelcontextprotocol.io/).

## Development

To install development dependencies:

```bash
uv pip install -e ".[dev]"
```

## License

[MIT](LICENSE) 