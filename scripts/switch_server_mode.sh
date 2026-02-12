#!/bin/bash
# Switch server between serial and parallel modes
# 切换服务器串行/并行模式
#
# Usage: ./switch_server_mode.sh [serial|parallel]

MODE="${1:-parallel}"

if [ "$MODE" != "serial" ] && [ "$MODE" != "parallel" ]; then
    echo "Error: Invalid mode. Use 'serial' or 'parallel'"
    echo "Usage: $0 [serial|parallel]"
    exit 1
fi

echo "=========================================="
echo "  Switch Server Mode"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    exit 1
fi

# Backup .env
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE=".env.backup.$TIMESTAMP"
echo "Creating backup: $BACKUP_FILE"
cp .env "$BACKUP_FILE"

# Update configuration
if [ "$MODE" = "serial" ]; then
    echo "Setting USE_MERGE_STEP_PARALLEL=false (SERIAL mode)"
    
    if grep -q "^USE_MERGE_STEP_PARALLEL=" .env; then
        sed -i.bak 's/^USE_MERGE_STEP_PARALLEL=.*/USE_MERGE_STEP_PARALLEL=false/' .env
    else
        echo "USE_MERGE_STEP_PARALLEL=false" >> .env
    fi
else
    echo "Setting USE_MERGE_STEP_PARALLEL=true (PARALLEL mode)"
    
    if grep -q "^USE_MERGE_STEP_PARALLEL=" .env; then
        sed -i.bak 's/^USE_MERGE_STEP_PARALLEL=.*/USE_MERGE_STEP_PARALLEL=true/' .env
    else
        echo "USE_MERGE_STEP_PARALLEL=true" >> .env
    fi
fi

# Verify change
echo ""
echo "Current configuration:"
grep "^USE_MERGE_STEP=" .env
grep "^USE_MERGE_STEP_PARALLEL=" .env

echo ""
echo "=========================================="
echo "  Next Steps"
echo "=========================================="
echo ""
echo "1. Restart the service:"
echo "   pkill -f 'uvicorn app.main:app'"
echo "   ./start_server.sh"
echo ""
echo "2. Verify mode in logs:"
if [ "$MODE" = "serial" ]; then
    echo "   tail -f logs/server.log | grep 'SERIAL'"
else
    echo "   tail -f logs/server.log | grep 'PARALLEL'"
fi
echo ""
echo "3. Run test:"
echo "   python tests/load_test.py --disable-cache --multi-images ..."
echo ""
