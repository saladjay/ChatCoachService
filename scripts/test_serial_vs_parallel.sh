#!/bin/bash
# Test script to compare serial vs parallel processing
# 测试脚本：对比串行与并行处理
#
# ⚠️  WARNING: This script does NOT automatically switch server modes!
# ⚠️  警告：此脚本不会自动切换服务器模式！
#
# Client-side environment variables do NOT affect the server.
# You must manually change the server configuration and restart it.
#
# See: dev-docs/WHY_CLIENT_ENV_VARS_DONT_WORK.md
#
# For automatic mode switching, use:
#   ./scripts/switch_server_mode.sh [serial|parallel]
#   ./start_server.sh

URL="${1:-http://localhost:8000}"
CONCURRENT="${2:-5}"
REQUESTS="${3:-20}"

echo "=========================================="
echo "Serial vs Parallel Processing Test"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT NOTICE"
echo ""
echo "This script tests the CURRENT server configuration."
echo "It does NOT change the server mode automatically."
echo ""
echo "To test both modes:"
echo "  1. On SERVER: ./scripts/switch_server_mode.sh serial"
echo "  2. On SERVER: ./start_server.sh"
echo "  3. Run this script"
echo "  4. On SERVER: ./scripts/switch_server_mode.sh parallel"
echo "  5. On SERVER: ./start_server.sh"
echo "  6. Run this script again"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read
echo ""

# Test images
IMAGE1="https://test-r2.zhizitech.org/test_discord_2.png"
IMAGE2="https://test-r2.zhizitech.org/test_discord_3.png"
IMAGE3="https://test-r2.zhizitech.org/test_discord_4.png"

echo "Configuration:"
echo "  URL: $URL"
echo "  Concurrent: $CONCURRENT"
echo "  Requests: $REQUESTS"
echo "  Images: 3"
echo ""

# Test 1: Current server mode
echo "=========================================="
echo "TEST: CURRENT SERVER MODE"
echo "=========================================="
echo ""
echo "Testing with whatever mode the server is currently using..."
echo "Check server logs to see: SERIAL or PARALLEL"
echo ""

python tests/load_test.py \
  --url "$URL" \
  --concurrent "$CONCURRENT" \
  --requests "$REQUESTS" \
  --disable-cache \
  --multi-images "$IMAGE1" "$IMAGE2" "$IMAGE3"

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Check server logs to confirm which mode was used:"
echo "  tail -f logs/server.log | grep 'SERIAL\\|PARALLEL'"
echo ""
echo "Expected performance:"
echo "  - Serial mode: ~21s for 3 images"
echo "  - Parallel mode: ~7s for 3 images"
echo ""
echo "To test the other mode:"
echo "  1. On SERVER: ./scripts/switch_server_mode.sh [serial|parallel]"
echo "  2. On SERVER: ./start_server.sh"
echo "  3. Run this script again"
echo ""
