# backend/show-code.ps1

$files = @(
  "btc_onchain\main.py",
  "btc_onchain\rpc.py",
  "btc_onchain\workers.py",
  "btc_onchain\api\routes.py",
  "btc_onchain\config.py"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "`n=== $f ===" -ForegroundColor Cyan
        Get-Content $f | ForEach-Object { $_ }
    }
    else {
        Write-Host "`n--- $f not found ---" -ForegroundColor Yellow
    }
}
