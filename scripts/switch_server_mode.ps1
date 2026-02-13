# Switch server between serial and parallel modes
# 切换服务器串行/并行模式
#
# Usage: .\switch_server_mode.ps1 [serial|parallel]

param(
    [Parameter(Position=0)]
    [ValidateSet("serial", "parallel")]
    [string]$Mode = "parallel"
)

Write-Host "=" * 80
Write-Host "  Switch Server Mode"
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

# Update configuration
$newContent = @()
$found = $false

foreach ($line in $envContent) {
    if ($line -match "^USE_MERGE_STEP_PARALLEL=") {
        if ($Mode -eq "serial") {
            $newContent += "USE_MERGE_STEP_PARALLEL=false"
            Write-Host "Setting USE_MERGE_STEP_PARALLEL=false (SERIAL mode)" -ForegroundColor Yellow
        }
        else {
            $newContent += "USE_MERGE_STEP_PARALLEL=true"
            Write-Host "Setting USE_MERGE_STEP_PARALLEL=true (PARALLEL mode)" -ForegroundColor Green
        }
        $found = $true
    }
    else {
        $newContent += $line
    }
}

# If not found, add it
if (-not $found) {
    if ($Mode -eq "serial") {
        $newContent += "USE_MERGE_STEP_PARALLEL=false"
        Write-Host "Adding USE_MERGE_STEP_PARALLEL=false (SERIAL mode)" -ForegroundColor Yellow
    }
    else {
        $newContent += "USE_MERGE_STEP_PARALLEL=true"
        Write-Host "Adding USE_MERGE_STEP_PARALLEL=true (PARALLEL mode)" -ForegroundColor Green
    }
}

# Write back to .env
$newContent | Set-Content .env

# Verify change
Write-Host ""
Write-Host "Current configuration:"
$envContent = Get-Content .env
$mergeStep = $envContent | Where-Object { $_ -match "^USE_MERGE_STEP=" }
$parallel = $envContent | Where-Object { $_ -match "^USE_MERGE_STEP_PARALLEL=" }
Write-Host "  $mergeStep"
Write-Host "  $parallel"

Write-Host ""
Write-Host "=" * 80
Write-Host "  Next Steps"
Write-Host "=" * 80
Write-Host ""
Write-Host "1. Restart the service:"
Write-Host "   .\start_server.ps1"
Write-Host ""
Write-Host "2. Verify mode in logs:"
if ($Mode -eq "serial") {
    Write-Host "   Get-Content logs\server.log -Tail 50 | Select-String 'SERIAL'"
}
else {
    Write-Host "   Get-Content logs\server.log -Tail 50 | Select-String 'PARALLEL'"
}
Write-Host ""
Write-Host "3. Run test:"
Write-Host "   python tests\load_test.py --disable-cache --multi-images ..."
Write-Host ""
