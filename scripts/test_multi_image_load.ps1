# Quick test script for multi-image load testing (PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Multi-Image Load Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Default values
$URL = "http://localhost:8000"
$CONCURRENT = 5
$REQUESTS = 20

# Test images
$IMAGE1 = "https://test-r2.zhizitech.org/test_discord_2.png"
$IMAGE2 = "https://test-r2.zhizitech.org/test_discord_3.png"
$IMAGE3 = "https://test-r2.zhizitech.org/test_discord_4.png"

Write-Host "Configuration:"
Write-Host "  URL: $URL"
Write-Host "  Concurrent: $CONCURRENT"
Write-Host "  Requests: $REQUESTS"
Write-Host "  Images: 3"
Write-Host ""

# Test 1: Single image (baseline)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Test 1: Single Image (Baseline)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python tests/load_test.py `
  --url $URL `
  --concurrent $CONCURRENT `
  --requests $REQUESTS `
  --disable-cache

Write-Host ""
Write-Host "Press Enter to continue to Test 2..." -ForegroundColor Green
Read-Host

# Test 2: Multiple images (parallel processing)
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "Test 2: Multiple Images (3 images)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python tests/load_test.py `
  --url $URL `
  --concurrent $CONCURRENT `
  --requests $REQUESTS `
  --disable-cache `
  --multi-images $IMAGE1 $IMAGE2 $IMAGE3

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Tests Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Compare the results:"
Write-Host "  - Single image response time: ~7s"
Write-Host "  - Multi-image response time: ~7s (parallel) or ~21s (serial)"
Write-Host ""
Write-Host "If multi-image time is ~7s, parallel processing is working!" -ForegroundColor Green
Write-Host "If multi-image time is ~21s, parallel processing is NOT working." -ForegroundColor Red
