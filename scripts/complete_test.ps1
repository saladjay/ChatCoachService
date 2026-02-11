# Complete test script for serial vs parallel processing
# 完整的串行 vs 并行处理测试脚本

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Complete Serial vs Parallel Test Suite" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify configuration
Write-Host "Step 1: Verifying Configuration" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python scripts/verify_serial_parallel.py

Write-Host ""
Write-Host "Press Enter to continue to load tests..." -ForegroundColor Green
Read-Host

# Step 2: Test serial mode
Write-Host ""
Write-Host "Step 2: Testing SERIAL Mode" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Setting USE_MERGE_STEP_PARALLEL=false" -ForegroundColor Cyan

# Update .env file
$envContent = Get-Content .env
$envContent = $envContent -replace "USE_MERGE_STEP_PARALLEL=true", "USE_MERGE_STEP_PARALLEL=false"
$envContent | Set-Content .env

Write-Host "✓ Updated .env file" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  Please restart the server now!" -ForegroundColor Red
Write-Host "   Windows: .\start_server.ps1" -ForegroundColor Yellow
Write-Host "   Then press Enter to continue..." -ForegroundColor Yellow
Read-Host

# Run serial test
python tests/load_test.py `
  --url http://localhost:8000 `
  --concurrent 5 `
  --requests 20 `
  --disable-cache `
  --multi-images `
    https://test-r2.zhizitech.org/test_discord_2.png `
    https://test-r2.zhizitech.org/test_discord_3.png `
    https://test-r2.zhizitech.org/test_discord_4.png

Write-Host ""
Write-Host "Serial mode test completed!" -ForegroundColor Green
Write-Host "Press Enter to continue to parallel mode test..." -ForegroundColor Green
Read-Host

# Step 3: Test parallel mode
Write-Host ""
Write-Host "Step 3: Testing PARALLEL Mode" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Setting USE_MERGE_STEP_PARALLEL=true" -ForegroundColor Cyan

# Update .env file
$envContent = Get-Content .env
$envContent = $envContent -replace "USE_MERGE_STEP_PARALLEL=false", "USE_MERGE_STEP_PARALLEL=true"
$envContent | Set-Content .env

Write-Host "✓ Updated .env file" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  Please restart the server now!" -ForegroundColor Red
Write-Host "   Windows: .\start_server.ps1" -ForegroundColor Yellow
Write-Host "   Then press Enter to continue..." -ForegroundColor Yellow
Read-Host

# Run parallel test
python tests/load_test.py `
  --url http://localhost:8000 `
  --concurrent 5 `
  --requests 20 `
  --disable-cache `
  --multi-images `
    https://test-r2.zhizitech.org/test_discord_2.png `
    https://test-r2.zhizitech.org/test_discord_3.png `
    https://test-r2.zhizitech.org/test_discord_4.png

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All Tests Completed!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Compare the results above:" -ForegroundColor White
Write-Host "  - Serial mode: ~21s for 3 images" -ForegroundColor Yellow
Write-Host "  - Parallel mode: ~7s for 3 images" -ForegroundColor Green
Write-Host ""
Write-Host "Expected improvement: ~67% faster with parallel processing" -ForegroundColor Green
