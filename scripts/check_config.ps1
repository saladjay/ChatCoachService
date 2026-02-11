# Check Serial vs Parallel Configuration
# This script reads the .env file and shows the current configuration

Write-Host "=" * 80
Write-Host "  SERIAL VS PARALLEL CONFIGURATION CHECK"
Write-Host "=" * 80
Write-Host ""

# Read .env file
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

$envContent = Get-Content $envFile

# Extract configuration values
$useMergeStep = $null
$useMergeStepParallel = $null

foreach ($line in $envContent) {
    if ($line -match "^USE_MERGE_STEP=(.+)") {
        $useMergeStep = $matches[1].Trim()
    }
    if ($line -match "^USE_MERGE_STEP_PARALLEL=(.+)") {
        $useMergeStepParallel = $matches[1].Trim()
    }
}

Write-Host "Current Configuration:"
Write-Host "  USE_MERGE_STEP:          $useMergeStep"
Write-Host "  USE_MERGE_STEP_PARALLEL: $useMergeStepParallel"
Write-Host ""

# Compute derived values
$useMergeStepBool = $useMergeStep -eq "true"
$useMergeStepParallelBool = $useMergeStepParallel -eq "true"
$useParallel = $useMergeStepBool -and $useMergeStepParallelBool

Write-Host "Computed Values:"
Write-Host "  use_merge_step:          $useMergeStepBool"
Write-Host "  use_parallel:            $useParallel"
Write-Host ""

Write-Host "=" * 80
Write-Host "  EXPECTED BEHAVIOR"
Write-Host "=" * 80
Write-Host ""

if (-not $useMergeStepBool) {
    Write-Host "X USE_MERGE_STEP=false" -ForegroundColor Yellow
    Write-Host "   -> All requests use SERIAL traditional flow"
    Write-Host "   -> USE_MERGE_STEP_PARALLEL has no effect"
    Write-Host ""
    Write-Host "To enable parallel processing:" -ForegroundColor Cyan
    Write-Host "  1. Set USE_MERGE_STEP=true in .env"
    Write-Host "  2. Set USE_MERGE_STEP_PARALLEL=true in .env"
    Write-Host "  3. Restart the service"
}
elseif (-not $useParallel) {
    Write-Host "OK USE_MERGE_STEP=true, USE_MERGE_STEP_PARALLEL=false" -ForegroundColor Yellow
    Write-Host "   -> All requests use SERIAL merge_step flow"
    Write-Host "   -> Multiple images processed one by one"
    Write-Host ""
    Write-Host "To enable parallel processing:" -ForegroundColor Cyan
    Write-Host "  1. Set USE_MERGE_STEP_PARALLEL=true in .env"
    Write-Host "  2. Restart the service"
}
else {
    Write-Host "OK USE_MERGE_STEP=true, USE_MERGE_STEP_PARALLEL=true" -ForegroundColor Green
    Write-Host "   -> Requests with images use PARALLEL merge_step flow"
    Write-Host "   -> Multiple images processed concurrently"
    Write-Host "   -> Text-only requests use SERIAL flow"
    Write-Host ""
    Write-Host "Parallel processing is ENABLED! OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "=" * 80
Write-Host "  TEST SCENARIOS"
Write-Host "=" * 80
Write-Host ""

$scenarios = @(
    @{
        Name = "Single image"
        HasImages = $true
        Description = "1 image URL"
    },
    @{
        Name = "Multiple images (3)"
        HasImages = $true
        Description = "3 image URLs"
    },
    @{
        Name = "Text only"
        HasImages = $false
        Description = "No images, just text"
    }
)

foreach ($scenario in $scenarios) {
    $shouldUseParallel = $useParallel -and $scenario.HasImages
    
    Write-Host "$($scenario.Name):"
    Write-Host "  Description: $($scenario.Description)"
    Write-Host "  Has images: $($scenario.HasImages)"
    
    if ($shouldUseParallel) {
        Write-Host "  -> Mode: PARALLEL" -ForegroundColor Green
    }
    else {
        if ($useMergeStepBool) {
            Write-Host "  -> Mode: SERIAL (merge_step)" -ForegroundColor Yellow
        }
        else {
            Write-Host "  -> Mode: SERIAL (traditional)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

Write-Host "=" * 80
Write-Host "  LOG MESSAGES TO LOOK FOR"
Write-Host "=" * 80
Write-Host ""

if ($useMergeStepBool) {
    if ($useParallel) {
        Write-Host "When processing multiple images, you should see:" -ForegroundColor Cyan
        Write-Host '  INFO - Using merge_step optimized flow with PARALLEL processing'
        Write-Host '  INFO - Processing 3 images in PARALLEL'
        Write-Host '  INFO - Parallel processing completed: 3 items processed in original order'
    }
    else {
        Write-Host "When processing multiple images, you should see:" -ForegroundColor Cyan
        Write-Host '  INFO - Using merge_step optimized flow with SERIAL processing'
        Write-Host '  INFO - Processing 3 images in SERIAL (one by one)'
        Write-Host '  INFO - Processing content: https://...'
        Write-Host '  INFO - Screenshot analysis completed in XXXXms for ...'
    }
}
else {
    Write-Host "When processing images, you should see:" -ForegroundColor Cyan
    Write-Host '  INFO - Using traditional separate flow'
    Write-Host '  INFO - Processing 3 images in SERIAL (one by one)'
}

Write-Host ""
Write-Host "=" * 80
Write-Host "  NEXT STEPS"
Write-Host "=" * 80
Write-Host ""

Write-Host "To test the configuration:"
Write-Host "  1. Start the service: .\start_server.ps1"
Write-Host "  2. Send a test request with multiple images"
Write-Host "  3. Check the logs for the mode identifiers above"
Write-Host ""

Write-Host "To run load tests:"
Write-Host "  .\scripts\test_serial_vs_parallel.ps1"
Write-Host ""

Write-Host "For more information:"
Write-Host "  - dev-docs/HOW_SERIAL_PARALLEL_WORKS.md"
Write-Host "  - dev-docs/SERIAL_PARALLEL_FLOW_DIAGRAM.md"
Write-Host "  - dev-docs/SERIAL_VS_PARALLEL_TESTING.md"
Write-Host ""
