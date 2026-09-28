# Install the prospective macro collect-due Windows Scheduled Task.
# Operator must run this intentionally. Tests must not execute it.
# Does not enable Reuters/FactSet/Dow Jones/Bloomberg/Trading Economics.
# Does not change FORWARD_CONSENSUS_COLLECTION_ENABLED.

param(
    [string]$RepoRoot = "C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st",
    [string]$TaskName = "ForexMacroProspectiveCollectDue",
    [int]$IntervalMinutes = 5
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -ne 5) {
    throw "IntervalMinutes must be 5. Smaller checkpoint spacing is T0-15m to T0-5m."
}

Set-Location -LiteralPath $RepoRoot

$PythonExe = $null
try {
    $PythonExe = (& py -3 -c "import sys; print(sys.executable)").Trim()
} catch {
    $PythonExe = $null
}
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw "Could not resolve an explicit Python executable."
}

$WorkDir = (Resolve-Path -LiteralPath $RepoRoot).Path
$Argument = "-m reports.decision_quality.macro_prospective_cli collect-due"

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Argument -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::FromDays(3650))
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null

$MarkerDir = Join-Path $WorkDir "data\research\macro\consensus_pit\prospective\scheduler"
New-Item -ItemType Directory -Force -Path $MarkerDir | Out-Null
$Marker = @{
    task_name = $TaskName
    python_executable = $PythonExe
    working_directory = $WorkDir
    arguments = $Argument
    interval_minutes = 5
    installed_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json
Set-Content -LiteralPath (Join-Path $MarkerDir "windows_task_installed.json") -Value $Marker -Encoding utf8

Write-Host "INSTALLED $TaskName"
Write-Host "PYTHON $PythonExe"
Write-Host "WORKDIR $WorkDir"
Write-Host "INTERVAL 5 minutes"
Write-Host "COMMAND $PythonExe $Argument"
