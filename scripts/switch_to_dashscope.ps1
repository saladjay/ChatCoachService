# Quick fix: Switch to DashScope provider
# 快速修复：切换到 DashScope provider

Write-Host "=" * 80
Write-Host "  Switch to DashScope Provider"
Write-Host "=" * 80
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

# Backup .env
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = ".env.backup.$timestamp"
Write-Host "Creating backup: $backupFile"
Copy-Item .env $backupFile

# Read .env content
$envContent = Get-Content .env

# Update LLM_DEFAULT_PROVIDER
Write-Host "Updating LLM_DEFAULT_PROVIDER to dashscope..."

$updated = $false
$newContent = @()

foreach ($line in $envContent) {
    if ($line -match "^LLM_DEFAULT_PROVIDER=") {
        $newContent += "LLM_DEFAULT_PROVIDER=dashscope"
        $updated = $true
        Write-Host "OK Updated LLM_DEFAULT_PROVIDER=dashscope" -ForegroundColor Green
    }
    else {
        $newContent += $line
    }
}

# If not found, add it
if (-not $updated) {
    $newContent += "LLM_DEFAULT_PROVIDER=dashscope"
    Write-Host "OK Added LLM_DEFAULT_PROVIDER=dashscope" -ForegroundColor Green
}

# Write back to .env
$newContent | Set-Content .env

# Verify change
Write-Host ""
Write-Host "Current configuration:"
$envContent = Get-Content .env
$provider = $envContent | Where-Object { $_ -match "^LLM_DEFAULT_PROVIDER=" }
$apiKey = $envContent | Where-Object { $_ -match "^DASHSCOPE_API_KEY=" }

Write-Host "  $provider"
if ($apiKey) {
    Write-Host "  DASHSCOPE_API_KEY=***hidden***"
}
else {
    Write-Host "  WARNING: DASHSCOPE_API_KEY not found in .env!" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 80
Write-Host "  Next Steps"
Write-Host "=" * 80
Write-Host ""
Write-Host "1. Restart the service:"
Write-Host "   .\start_server.ps1"
Write-Host ""
Write-Host "2. Check logs:"
Write-Host "   Get-Content logs\server.log -Tail 50 -Wait"
Write-Host ""
Write-Host "3. Test the service:"
Write-Host "   python tests\load_test.py --requests 1"
Write-Host ""
