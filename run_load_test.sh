#!/bin/bash
# Load Test Script for ChatCoach API
# Tests local server on port 80 with 100 total requests and 20 concurrent requests

URL="http://localhost:80"
IMAGE_URL="http://192.168.0.96:5000/images/a053f12043934b9aa5e5860a10fdc6f7.png"
TOTAL_REQUESTS=100
CONCURRENT=20

echo "================================"
echo "ChatCoach API Load Test"
echo "================================"
echo "Target URL:        $URL"
echo "Image URL:         $IMAGE_URL"
echo "Total Requests:    $TOTAL_REQUESTS"
echo "Concurrent:        $CONCURRENT"
echo "================================"
echo ""

# Run the load test
python tests/load_test.py \
    --url "$URL" \
    --image-url "$IMAGE_URL" \
    --requests $TOTAL_REQUESTS \
    --concurrent $CONCURRENT \
    --disable-cache

echo ""
echo "================================"
echo "Load Test Completed"
echo "================================"
