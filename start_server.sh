#!/bin/bash
# Bash script to start the FastAPI server
# Usage: ./start_server.sh

echo "========================================"
echo "Starting ChatCoach API Server"
echo "========================================"
echo ""

# Check if uvicorn is installed
echo "Checking dependencies..."
if ! python -m pip show uvicorn > /dev/null 2>&1; then
    echo "Error: uvicorn is not installed"
    echo "Please run: pip install uvicorn"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found"
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "Please edit .env file and add your API keys"
    fi
fi

echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""
echo "Available endpoints:"
echo "  - Health check: http://localhost:8000/health"
echo "  - API docs: http://localhost:8000/docs"
echo "  - Screenshot parse: http://localhost:8000/api/v1/chat_screenshot/parse"
echo ""

# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
