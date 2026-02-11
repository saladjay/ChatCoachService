# Test script to compare serial vs parallel processing
# 测试脚本：对比串行与并行处理

param(
    [string]$Url = "http://localhost:8000",
    [int]$Concurrent = 5,
    [int]$Requests = 20
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Serial vs Parallel Processing Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test images
$IMAGE1 = "https://test-r2.zhizitech.org/test_discord_2.png"
$IMAGE2 = "https://test-r2.zhizitech.org/test_discord_3.png"
$IMAGE3 = "https://test-r2.zhizitech.org/test_discord_4.png"

Write-Host "Configuration:"
Write-Host "  URL: $Url"
Write-Host "  Concurrent: $Concurrent"
Write-Host "  Requests: $Requests"
Write-Host "  Images: 3"
Write-Host ""

# Test 1: Serial mode
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "TEST 1: SERIAL MODE" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host ""

$env:USE_MERGE_STEP_PARALLEL = "false"
Write-Host "Setting USE_MERGE_STEP_PARALLEL=false" -ForegroundColor Green

python tests/load_test.py `
  --url $Url `
  --concurrent $Concurrent `
  --requests $Requests `
  --disable-cache `
  --multi-images $IMAGE1 $IMAGE2 $IMAGE3

Write-Host ""
Write-Host "Press Enter to continue to parallel mode test..." -ForegroundColor Green
Read-Host

# Test 2: Parallel mode
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "TEST 2: PARALLEL MODE" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host ""

$env:USE_MERGE_STEP_PARALLEL = "true"
Write-Host "Setting USE_MERGE_STEP_PARALLEL=true" -ForegroundColor Green

python tests/load_test.py `
  --url $Url `
  --concurrent $Concurrent `
  --requests $Requests `
  --disable-cache `
  --multi-images $IMAGE1 $IMAGE2 $IMAGE3

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Tests Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Compare the results above:"
Write-Host "  - Serial mode: ~21s for 3 images"
Write-Host "  - Parallel mode: ~7s for 3 images"
Write-Host ""
Write-Host "Expected improvement: ~67% faster with parallel processing" -ForegroundColor Green
