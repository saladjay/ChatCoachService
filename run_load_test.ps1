# Load Test Script for ChatCoach API
# Tests local server on port 80 with 100 total requests and 20 concurrent requests

$url = "http://localhost:80"
$imageUrl = "http://192.168.0.96:5000/images/a053f12043934b9aa5e5860a10fdc6f7.png"
$totalRequests = 100
$concurrent = 20

Write-Host "================================" -ForegroundColor Cyan
Write-Host "ChatCoach API Load Test" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Target URL:        $url" -ForegroundColor Yellow
Write-Host "Image URL:         $imageUrl" -ForegroundColor Yellow
Write-Host "Total Requests:    $totalRequests" -ForegroundColor Yellow
Write-Host "Concurrent:        $concurrent" -ForegroundColor Yellow
Write-Host "================================`n" -ForegroundColor Cyan

# Run the load test
python tests/load_test.py `
    --url $url `
    --image-url $imageUrl `
    --requests $totalRequests `
    --concurrent $concurrent `
    --disable-cache

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "Load Test Completed" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
