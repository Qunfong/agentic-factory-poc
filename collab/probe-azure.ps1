# Lists which models an Azure OpenAI / Foundry resource has. Prints no secrets.
# Run:  powershell -ExecutionPolicy Bypass -File collab\probe-azure.ps1
param(
  [string]$Endpoint = $(Read-Host "Endpoint (e.g. https://<name>.openai.azure.com or https://<name>.services.ai.azure.com)")
)
$key = $env:AZURE_OPENAI_API_KEY
if (-not $key) {
  $sec = Read-Host "API key (hidden)" -AsSecureString
  $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
$ep  = $Endpoint.TrimEnd('/')
$h   = @{ 'api-key' = $key }

function Try-Get($url) {
  try { Invoke-RestMethod -Uri $url -Headers $h -Method Get -ErrorAction Stop }
  catch { Write-Host "  ! $($_.Exception.Message)" -ForegroundColor Yellow; $null }
}

Write-Host "`n== 1. Deployments (what you can call now) ==" -ForegroundColor Cyan
$d = Try-Get "$ep/openai/deployments?api-version=2022-12-01"
if ($d) { $d.data | Select-Object @{n='deployment';e={$_.id}}, model, status, @{n='sku';e={$_.scale_settings.scale_type}} | Format-Table -AutoSize }

Write-Host "== 2. Models this resource could deploy (catalog for its region) ==" -ForegroundColor Cyan
$m = Try-Get "$ep/openai/models?api-version=2024-10-21"
if ($m) {
  $m.data | Where-Object { $_.capabilities.chat_completion -eq $true -and $_.lifecycle_status -ne 'deprecated' } |
    Select-Object id, lifecycle_status | Sort-Object id -Unique | Format-Table -AutoSize
}

Write-Host "== 3. Smoke test one deployment (optional) ==" -ForegroundColor Cyan
$dep = Read-Host "Deployment name to test (Enter to skip)"
if ($dep) {
  $body = @{ messages = @(@{ role = 'user'; content = 'Reply with the single word: ok' }); max_completion_tokens = 20 } | ConvertTo-Json -Depth 5
  try {
    $r = Invoke-RestMethod -Uri "$ep/openai/deployments/$dep/chat/completions?api-version=2024-10-21" -Headers $h -Method Post -Body $body -ContentType 'application/json'
    Write-Host "  model=$($r.model) reply=$($r.choices[0].message.content)"
  } catch { Write-Host "  ! $($_.Exception.Message)" -ForegroundColor Yellow }
}
$key = $null
