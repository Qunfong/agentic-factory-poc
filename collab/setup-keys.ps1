# Sets the factory's model credentials on this PC (user env vars) and, optionally, as GitHub secrets.
# Keys are read hidden, never printed, never written to a file.
# Run:  powershell -ExecutionPolicy Bypass -File collab\setup-keys.ps1 [-GitHub]
param([switch]$GitHub)

$secrets = [ordered]@{
  'CLAUDE_CODE_OAUTH_TOKEN' = 'Claude subscription token (run "claude setup-token" first; Enter to skip)'
  'AZURE_OPENAI_API_KEY'    = 'Azure OpenAI / Foundry key (the NEW key after rotation)'
  'GEMINI_API_KEY'          = 'Gemini key from aistudio.google.com (Enter to skip)'
}
$vars = [ordered]@{
  'AZURE_OPENAI_ENDPOINT'   = 'https://ai-services-qun.openai.azure.com'
}

function Read-Hidden($prompt) {
  $s = Read-Host $prompt -AsSecureString
  [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}

if ($GitHub -and -not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "gh CLI not found; install it or run without -GitHub" }

foreach ($name in $secrets.Keys) {
  $existing = [Environment]::GetEnvironmentVariable($name, 'User')
  $val = Read-Hidden "$name - $($secrets[$name])$(if ($existing) {' [Enter keeps current]'})"
  if (-not $val) { $val = $existing }
  if (-not $val) { Write-Host "  skipped $name"; continue }
  [Environment]::SetEnvironmentVariable($name, $val, 'User')
  Write-Host "  set $name locally (length $($val.Length))"
  if ($GitHub) { $val | gh secret set $name; Write-Host "  set $name in GitHub" }
  $val = $null
}

foreach ($name in $vars.Keys) {
  $val = Read-Host "$name [$($vars[$name])]"
  if (-not $val) { $val = $vars[$name] }
  [Environment]::SetEnvironmentVariable($name, $val, 'User')
  Write-Host "  set $name = $val"
  if ($GitHub) { gh variable set $name --body $val | Out-Null; Write-Host "  set $name as GitHub variable" }
}

Write-Host "`nDone. Open a NEW terminal so the variables are visible."
