#!/bin/bash
# Manual test script for serial vs parallel processing
# 手动测试脚本：串行与并行处理对比
#
# IMPORTANT: This script requires manual server configuration changes!
# 重要：此脚本需要手动修改服务器配置！

URL="${1:-http://localhost:8000}"
CONCURRENT="${2:-5}"
REQUESTS="${3:-20}"

# Test images
IMAGE1="https://test-r2.zhizitech.org/test_discord_2.png"
IMAGE2="https://test-r2.zhizitech.org/test_discord_3.png"
IMAGE3="https://test-r2.zhizitech.org/test_discord_4.png"

echo "=========================================="
echo "  Serial vs Parallel Processing Test"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT NOTICE"
echo ""
echo "This script CANNOT automatically switch server modes!"
echo ""
echo "Environment variables set in this script only affect the CLIENT,"
echo "not the SERVER. To test both modes, you need to:"
echo ""
echo "1. Test SERIAL mode:"
echo "   - On SERVER: Edit .env, set USE_MERGE_STEP_PARALLEL=false"
echo "   - On SERVER: Restart service (./start_server.sh)"
echo "   - Run this script for serial test"
echo ""
echo "2. Test PARALLEL mode:"
echo "   - On SERVER: Edit .env, set USE_MERGE_STEP_PARALLEL=true"
echo "   - On SERVER: Restart service (./start_server.sh)"
echo "   - Run this script for parallel test"
echo ""
echo "=========================================="
echo ""

echo "Configuration:"
echo "  URL: $URL"
echo "  Concurrent: $CONCURRENT"
echo "  Requests: $REQUESTS"
echo "  Images: 3"
echo ""

echo "Press Enter to run test with CURRENT server configuration..."
read

echo ""
echo "=========================================="
echo "  Running Test"
echo "=========================================="
echo ""

python tests/load_test.py \
  --url "$URL" \
  --concurrent "$CONCURRENT" \
  --requests "$REQUESTS" \
  --disable-cache \
  --multi-images "$IMAGE1" "$IMAGE2" "$IMAGE3"

echo ""
echo "=========================================="
echo "  Test Complete"
echo "=========================================="
echo ""
echo "Check server logs to confirm which mode was used:"
echo "  - Serial: 'Processing X images in SERIAL (one by one)'"
echo "  - Parallel: 'Processing X images in PARALLEL'"
echo ""
echo "Expected performance:"
echo "  - Serial mode: ~21s for 3 images"
echo "  - Parallel mode: ~7s for 3 images"
echo ""
