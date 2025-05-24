#!/bin/bash
# Script to rebuild the virtual environment for manus-mcp
# This script should be run from the project root directory

set -e  # Exit on any error

echo "Rebuilding virtual environment for manus-mcp..."

# Remove existing venv
echo "Removing existing .venv directory..."
rm -rf .venv

# Create new virtual environment
echo "Creating new virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install project dependencies
echo "Installing project dependencies..."
pip install -e .

# Install MCP directly (in case it wasn't installed properly)
echo "Installing MCP..."
pip install mcp==1.4.1

# Test imports
echo "Testing imports..."
python -c "import mcp; print('✓ MCP available')"
python -c "from app.workarounds.googlesearch import search; print('✓ Google search available')"
python -c "from app.web_browser import ChromeBrowser; print('✓ ChromeBrowser available')"

echo "✅ Virtual environment rebuilt successfully!"
echo ""
echo "To activate the environment manually, run:"
echo "source .venv/bin/activate"