#!/bin/bash
# Test script to compare serial vs parallel processing
# 测试脚本：对比串行与并行处理

URL="${1:-http://localhost:8000}"
CONCURRENT="${2:-5}"
REQUESTS="${3:-20}"

echo "=========================================="
echo "Serial vs Parallel Processing Test"
echo "=========================================="
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

# Test 1: Serial mode
echo "=========================================="
echo "TEST 1: SERIAL MODE"
echo "=========================================="
echo ""

export USE_MERGE_STEP_PARALLEL=false
echo "Setting USE_MERGE_STEP_PARALLEL=false"

python tests/load_test.py \
  --url "$URL" \
  --concurrent "$CONCURRENT" \
  --requests "$REQUESTS" \
  --disable-cache \
  --multi-images "$IMAGE1" "$IMAGE2" "$IMAGE3"

echo ""
echo "Press Enter to continue to parallel mode test..."
read

# Test 2: Parallel mode
echo "=========================================="
echo "TEST 2: PARALLEL MODE"
echo "=========================================="
echo ""

export USE_MERGE_STEP_PARALLEL=true
echo "Setting USE_MERGE_STEP_PARALLEL=true"

python tests/load_test.py \
  --url "$URL" \
  --concurrent "$CONCURRENT" \
  --requests "$REQUESTS" \
  --disable-cache \
  --multi-images "$IMAGE1" "$IMAGE2" "$IMAGE3"

echo ""
echo "=========================================="
echo "Tests Complete!"
echo "=========================================="
echo ""
echo "Compare the results above:"
echo "  - Serial mode: ~21s for 3 images"
echo "  - Parallel mode: ~7s for 3 images"
echo ""
echo "Expected improvement: ~67% faster with parallel processing"
