#!/bin/bash
# Quick fix: Switch to DashScope provider
# 快速修复：切换到 DashScope provider

echo "=========================================="
echo "  Switch to DashScope Provider"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    exit 1
fi

# Backup .env
echo "Creating backup: .env.backup.$(date +%Y%m%d_%H%M%S)"
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Update LLM_DEFAULT_PROVIDER
echo "Updating LLM_DEFAULT_PROVIDER to dashscope..."

if grep -q "^LLM_DEFAULT_PROVIDER=" .env; then
    # Replace existing line
    sed -i.bak 's/^LLM_DEFAULT_PROVIDER=.*/LLM_DEFAULT_PROVIDER=dashscope/' .env
    echo "✓ Updated LLM_DEFAULT_PROVIDER=dashscope"
else
    # Add new line
    echo "LLM_DEFAULT_PROVIDER=dashscope" >> .env
    echo "✓ Added LLM_DEFAULT_PROVIDER=dashscope"
fi

# Verify change
echo ""
echo "Current configuration:"
grep "^LLM_DEFAULT_PROVIDER=" .env
grep "^DASHSCOPE_API_KEY=" .env | sed 's/=.*/=***hidden***/'

echo ""
echo "=========================================="
echo "  Next Steps"
echo "=========================================="
echo ""
echo "1. Restart the service:"
echo "   pkill -f 'uvicorn app.main:app'"
echo "   nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/server.log 2>&1 &"
echo ""
echo "2. Check logs:"
echo "   tail -f logs/server.log"
echo ""
echo "3. Test the service:"
echo "   curl -X POST http://localhost:8000/api/v1/ChatAnalysis/predict ..."
echo ""
