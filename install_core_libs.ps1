# PowerShell script to install core libraries
# This script installs the three core libraries: llm_adapter, moderation-service, and user_profile

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installing Core Libraries" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if uv is available
$uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvAvailable) {
    Write-Host "Warning: 'uv' command not found. Falling back to pip." -ForegroundColor Yellow
    $useUv = $false
} else {
    Write-Host "Using 'uv' for installation" -ForegroundColor Green
    $useUv = $true
}

# Function to install a library
function Install-Library {
    param(
        [string]$Name,
        [string]$Path
    )
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "Installing: $Name" -ForegroundColor Cyan
    Write-Host "Path: $Path" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    
    if (-not (Test-Path $Path)) {
        Write-Host "Error: Directory not found: $Path" -ForegroundColor Red
        return $false
    }
    
    try {
        if ($useUv) {
            # Install using uv in editable mode
            Write-Host "Running: uv pip install -e $Path" -ForegroundColor Gray
            uv pip install -e $Path
        } else {
            # Install using pip in editable mode
            Write-Host "Running: pip install -e $Path" -ForegroundColor Gray
            pip install -e $Path
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Successfully installed $Name" -ForegroundColor Green
            return $true
        } else {
            Write-Host "✗ Failed to install $Name" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "✗ Error installing $Name : $_" -ForegroundColor Red
        return $false
    }
}

# Install each library
$results = @{}

$results['llm_adapter'] = Install-Library -Name "llm_adapter" -Path "core/llm_adapter"
$results['moderation-service'] = Install-Library -Name "moderation-service" -Path "core/moderation-service"
$results['user_profile'] = Install-Library -Name "user_profile" -Path "core/user_profile"

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installation Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$successCount = 0
$failCount = 0

foreach ($lib in $results.Keys) {
    if ($results[$lib]) {
        Write-Host "✓ $lib" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host "✗ $lib" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host "Total: $($results.Count) libraries" -ForegroundColor Cyan
Write-Host "Success: $successCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Gray" })
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "All libraries installed successfully! ✓" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some libraries failed to install. Please check the errors above." -ForegroundColor Yellow
    exit 1
}
