# .\soft-link-venv.ps1 -MainBranchPath "D:\project\chatcoach-dev-main" -Force
param(
  [Parameter(Mandatory = $true)]
  [string]$MainBranchPath,

  [switch]$Force
)

$repoRoot = (Get-Location).Path
$targetPath = Join-Path $MainBranchPath ".venv"
$linkPath = Join-Path $repoRoot ".venv"

if (-not (Test-Path $targetPath)) {
  throw "目标不存在：$targetPath"
}

if (Test-Path $linkPath) {
  if (-not $Force) {
    throw "链接/目录已存在：$linkPath 。如需覆盖请加 -Force"
  }
  Remove-Item $linkPath -Recurse -Force
}

$resolvedTarget = (Resolve-Path $targetPath).Path

try {
  New-Item -ItemType SymbolicLink -Path $linkPath -Target $resolvedTarget | Out-Null
  Write-Host "已创建 SymbolicLink：$linkPath -> $resolvedTarget"
}
catch {
  New-Item -ItemType Junction -Path $linkPath -Target $resolvedTarget | Out-Null
  Write-Host "SymbolicLink 创建失败，已改用 Junction：$linkPath -> $resolvedTarget"
}