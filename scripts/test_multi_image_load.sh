#!/bin/bash
# Quick test script for multi-image load testing

echo "=========================================="
echo "Multi-Image Load Test"
echo "=========================================="
echo ""

# Default values
URL="http://localhost:8000"
CONCURRENT=5
REQUESTS=20

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

# Test 1: Single image (baseline)
echo "=========================================="
echo "Test 1: Single Image (Baseline)"
echo "=========================================="
python tests/load_test.py \
  --url "$URL" \
  --concurrent "$CONCURRENT" \
  --requests "$REQUESTS" \
  --disable-cache

echo ""
echo "Press Enter to continue to Test 2..."
read

# Test 2: Multiple images (parallel processing)
echo "=========================================="
echo "Test 2: Multiple Images (3 images)"
echo "=========================================="
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
echo "Compare the results:"
echo "  - Single image response time: ~7s"
echo "  - Multi-image response time: ~7s (parallel) or ~21s (serial)"
echo ""
echo "If multi-image time is ~7s, parallel processing is working!"
echo "If multi-image time is ~21s, parallel processing is NOT working."
