#!/bin/bash
# Bash script to start the FastAPI server
# Usage: ./start_server.sh

echo "========================================"
echo "Starting ChatCoach API Server"
echo "========================================"
echo ""

script_args=()
log_prompt=false
for arg in "$@"; do
  if [ "$arg" = "--log-prompt" ]; then
    log_prompt=true
  else
    script_args+=("$arg")
  fi
done

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

# Load .env into current process environment (avoid sourcing to keep syntax-agnostic)
if [ -f ".env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    trimmed="${line#${line%%[![:space:]]*}}"
    trimmed="${trimmed%${trimmed##*[![:space:]]}}"
    [ -z "$trimmed" ] && continue
    case "$trimmed" in
      \#*) continue ;;
    esac
    case "$trimmed" in
      *=*) ;; 
      *) continue ;;
    esac

    key="${trimmed%%=*}"
    val="${trimmed#*=}"
    key="${key#${key%%[![:space:]]*}}"
    key="${key%${key##*[![:space:]]}}"
    val="${val#${val%%[![:space:]]*}}"
    val="${val%${val##*[![:space:]]}}"

    if [ ${#val} -ge 2 ]; then
      first="${val:0:1}"
      last="${val: -1}"
      if { [ "$first" = "\"" ] && [ "$last" = "\"" ]; } || { [ "$first" = "'" ] && [ "$last" = "'" ]; }; then
        val="${val:1:${#val}-2}"
      fi
    fi

    export "$key=$val"
  done < ".env"
fi

if [ "$log_prompt" = true ]; then
  export TRACE_ENABLED=true
  export TRACE_LOG_LLM_PROMPT=true
  if [ -z "$TRACE_LEVEL" ]; then
    export TRACE_LEVEL=debug
  fi
  echo "✓ LLM prompt logging enabled (TRACE_ENABLED=true, TRACE_LOG_LLM_PROMPT=true)"
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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload "${script_args[@]}"
