# Download, initialize, and start the local PostgreSQL used by npm run dev.
$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
  $PSNativeCommandUseErrorActionPreference = $false
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tools = Join-Path $Root ".tools"
$Bin = Join-Path $Tools "pgsql\bin"
$Data = Join-Path $Tools "pgdata"
$PgCtl = Join-Path $Bin "pg_ctl.exe"
$Zip = Join-Path $Tools "postgresql-16.15-1-windows-x64-binaries.zip"
$Url = "https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip"
$Log = Join-Path $Data "server.log"

New-Item -ItemType Directory -Force -Path $Tools | Out-Null

function Fail([string]$Message) {
  Write-Host $Message
  exit 1
}

if (-not (Test-Path $PgCtl)) {
  $drive = (Get-Item $Root).PSDrive
  $freeGb = [math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 1)
  if ((Get-PSDrive $drive.Name).Free -lt 2GB) {
    Fail "Not enough free disk space on $($drive.Name): ($freeGb GB). Need about 2 GB for local PostgreSQL."
  }

  Write-Host "Downloading PostgreSQL 16.15 binaries (about 320 MB)..."
  if (Test-Path $Zip) {
    Remove-Item $Zip -Force
  }
  & curl.exe -L --fail --retry 5 --retry-all-errors -o $Zip $Url
  if ($LASTEXITCODE -ne 0) {
    Fail "PostgreSQL download failed."
  }

  Write-Host "Extracting PostgreSQL..."
  & tar.exe -xf $Zip -C $Tools
  if ($LASTEXITCODE -ne 0) {
    Fail "PostgreSQL extract failed."
  }
  Remove-Item $Zip -Force
  if (-not (Test-Path $PgCtl)) {
    Fail "pg_ctl.exe was not found after extract. Expected: $PgCtl"
  }
}

if (-not (Test-Path (Join-Path $Data "PG_VERSION"))) {
  Write-Host "Initializing local PostgreSQL data directory..."
  $pwFile = Join-Path $Tools ".pgpass-init"
  [System.IO.File]::WriteAllText($pwFile, "app`n")
  $previousPath = $env:PATH
  $env:PATH = "$Bin;$previousPath"
  try {
    & (Join-Path $Bin "initdb.exe") -D $Data -U app --pwfile=$pwFile -A scram-sha-256 -E UTF8 --no-locale --no-sync
    if ($LASTEXITCODE -ne 0) {
      Fail "initdb failed."
    }
  } finally {
    $env:PATH = $previousPath
    if (Test-Path $pwFile) {
      Remove-Item $pwFile -Force
    }
  }
}

& $PgCtl status -D $Data | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Starting local PostgreSQL..."
  & $PgCtl -D $Data -l $Log -o "-p 5432" start
  if ($LASTEXITCODE -ne 0) {
    if (Test-Path $Log) {
      Write-Host "PostgreSQL log:"
      Get-Content $Log -Tail 40
    }
    Fail "PostgreSQL failed to start."
  }
} else {
  Write-Host "Local PostgreSQL already running."
}

$ready = $false
$pgIsReady = Join-Path $Bin "pg_isready.exe"
for ($i = 0; $i -lt 30; $i++) {
  & $pgIsReady -h 127.0.0.1 -p 5432 -d postgres -U app | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $ready = $true
    break
  }
  Start-Sleep -Seconds 1
}
if (-not $ready) {
  if (Test-Path $Log) {
    Write-Host "PostgreSQL log:"
    Get-Content $Log -Tail 40
  }
  Fail "PostgreSQL did not accept connections on 127.0.0.1:5432."
}

$env:PGPASSWORD = "app"
$psql = Join-Path $Bin "psql.exe"
$existsRaw = & $psql -h 127.0.0.1 -p 5432 -U app -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='client_acquisition'"
if ($LASTEXITCODE -ne 0) {
  Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
  Fail "Could not connect to PostgreSQL as user app."
}
$exists = "$existsRaw".Trim()
if ($exists -ne "1") {
  Write-Host "Creating database client_acquisition..."
  & (Join-Path $Bin "createdb.exe") -h 127.0.0.1 -p 5432 -U app client_acquisition
  if ($LASTEXITCODE -ne 0) {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Fail "Could not create database client_acquisition."
  }
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

$python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  Fail "Backend virtualenv is missing. Expected: $python"
}

Write-Host "Applying database migrations..."
Push-Location (Join-Path $Root "backend")
try {
  & $python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) {
    Fail "Database migrations failed."
  }
} finally {
  Pop-Location
}

Write-Host "PostgreSQL is ready."
exit 0
