$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne 'redesign/dark-corporate') { throw 'Run this preview from the redesign/dark-corporate branch. It does not switch branches or modify an existing checkout.' }
$previewRoot = Join-Path $env:LOCALAPPDATA 'Sevlink\RedesignPreview'
New-Item -ItemType Directory -Force -Path $previewRoot | Out-Null
$python = Join-Path $previewRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
  Write-Host 'Preparing a separate local preview environment. Python 3.12+ is required.'
  if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $previewRoot '.venv') }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv (Join-Path $previewRoot '.venv') }
  else { throw 'Install Python 3.12 or newer (python.org), including the Python launcher, then run this command again.' }
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the preview Python environment.' }
}
& $python (Join-Path $PSScriptRoot 'check-preview-python.py')
if ($LASTEXITCODE -ne 0) { throw 'The preview needs Python 3.12+. Install it and recreate only the preview .venv if needed.' }
$lock = Join-Path $repo 'portal\production\requirements.lock'
$lockHash = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash
$marker = Join-Path $previewRoot 'requirements.sha256'
if (!(Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $lockHash) {
  & $python -m pip install -r $lock
  if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. No preview database was changed.' }
  Set-Content -LiteralPath $marker -Value $lockHash
}
$secretFile = Join-Path $previewRoot 'session-secret.txt'
if (!(Test-Path -LiteralPath $secretFile)) {
  $secret = & $python -c 'import secrets;print(secrets.token_urlsafe(64))'
  if ($LASTEXITCODE -ne 0) { throw 'Unable to prepare the local session secret.' }
  Set-Content -LiteralPath $secretFile -Value $secret
}
# These process-only settings never read an existing production environment file.
$env:DEBUG='1'
$env:DB_HOST=''
$env:DJANGO_SECRET_KEY=(Get-Content -LiteralPath $secretFile -Raw).Trim()
$env:DJANGO_SETTINGS_MODULE='config.redesign_preview'
$env:SEVLINK_LOCAL_PREVIEW='1'
$env:SEVLINK_PREVIEW_ROOT=$previewRoot
$env:SMTP_DELIVERY_ENABLED='0'
$env:OPERATIONS_LIVE_DELIVERY_ENABLED='0'
$env:PRIVILEGED_MFA_REQUIRED='0'
$env:UPLOAD_SCAN_REQUIRED='0'
Set-Location -LiteralPath (Join-Path $repo 'portal\production')
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Preview migrations failed. Existing live/local application databases were not used.' }
& $python manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Preview check failed.' }
& $python manage.py create_redesign_preview
if ($LASTEXITCODE -ne 0) { throw 'Preview setup was not completed. Run Preview-Redesign.cmd again.' }
Write-Host ''
Write-Host 'OPEN http://127.0.0.1:8000/ IN YOUR BROWSER' -ForegroundColor Green
Write-Host 'Keep this CMD window open. Press Ctrl+C to stop. Existing application records and live services are untouched.'
& $python manage.py runserver 127.0.0.1:8000
exit $LASTEXITCODE
