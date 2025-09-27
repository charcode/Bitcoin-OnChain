# show.ps1 — dump *all* backend files (source + configs) in a readable order
# Usage: .\show.ps1 > dump.txt
# Optional: .\show.ps1 -MaxBytes 1048576

param(
  [int]$MaxBytes = 1048576  # skip printing raw content if a file is larger than this
)

$ErrorActionPreference = 'Stop'

# The backend root is the folder containing this script
$root = $PSScriptRoot

if (-not (Test-Path (Join-Path $root 'btc_onchain'))) {
    Write-Error "Run this from the backend folder (the one containing btc_onchain/)."
    exit 1
}

# Directories to exclude
$excludeDirs = @(
  '__pycache__','.venv','venv','.pytest_cache','.mypy_cache','.git','.idea','.vscode',
  'node_modules','dist','build','.parcel-cache','.vite','.cache'
)
$excludeRegex = [regex]('\\(' + ($excludeDirs -join '|').Replace('.', '\.') + ')(\\|$)')

# Expected key files (shown first, flagged if missing)
$expected = @(
  'btc_onchain\main.py',
  'btc_onchain\config.py',
  'btc_onchain\models.py',
  'btc_onchain\rpc.py',
  'btc_onchain\rnr.py',
  'btc_onchain\api\__init__.py',
  'btc_onchain\api\routes.py',
  'btc_onchain\core\__init__.py',
  'btc_onchain\core\app_state.py',
  'btc_onchain\core\mempool_cache.py',
  'btc_onchain\core\rnr_engine.py',
  '.env',
  'local.env',
  'environment.yaml',
  '.gitignore'
)

function Write-Section {
  param([string]$Rel, [string]$Body)
  "=== $Rel ==="
  ""
  if ($Body -ne $null) { $Body; "" }
}

# 1) Show expected files first (or mark as missing)
$shown = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($rel in $expected) {
  $abs = Join-Path $root $rel
  if (Test-Path $abs) {
    try {
      $len = (Get-Item $abs).Length
      if ($len -gt $MaxBytes) {
        Write-Section $rel ("--- SKIPPED (>{0} bytes). Size: {1} bytes ---" -f $MaxBytes, $len)
      } else {
        $content = Get-Content -Path $abs -Raw -ErrorAction Stop
        Write-Section $rel $content
      }
    } catch {
      Write-Section $rel ("--- UNABLE TO READ: {0} ---" -f $_.Exception.Message)
    }
  } else {
    Write-Section $rel ("--- MISSING: {0} ---" -f $rel)
  }
  $shown.Add(($rel -replace '/', '\')) | Out-Null
}

# 2) Dump all other files under backend (respect excludes; skip very large/binary-looking files)
$all = Get-ChildItem -Path $root -Recurse -File | Where-Object {
  $_.FullName -notmatch $excludeRegex
}

$others = $all | Where-Object {
  $rel = $_.FullName.Replace("$root\", '')
  -not $shown.Contains($rel)
} | Sort-Object FullName

foreach ($f in $others) {
  $rel = $f.FullName.Replace("$root\", '')
  try {
    $len = $f.Length
    if ($len -gt $MaxBytes) {
      Write-Section $rel ("--- SKIPPED (>{0} bytes). Size: {1} bytes ---" -f $MaxBytes, $len)
      continue
    }
    # Try to read as text; if it blows up, flag as binary/unicode issue
    $content = Get-Content -Path $f.FullName -Raw -ErrorAction Stop
    Write-Section $rel $content
  } catch {
    Write-Section $rel ("--- UNABLE TO READ (likely binary). Size: {0} bytes. Error: {1} ---" -f $f.Length, $_.Exception.Message)
  }
}

"=== dump summary ==="
"Files dumped: $($others.Count + $shown.Count)"
