# Verify the prospective macro collect-due scheduled task. Does not install or collect.
param(
    [string]$TaskName = "ForexMacroProspectiveCollectDue"
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $TaskName
$action = $task.Actions[0]
Write-Host "TASK_NAME=$($task.TaskName)"
Write-Host "STATE=$($task.State)"
Write-Host "EXECUTE=$($action.Execute)"
Write-Host "ARGUMENTS=$($action.Arguments)"
Write-Host "WORKING_DIRECTORY=$($action.WorkingDirectory)"
$rep = $task.Triggers[0].Repetition
Write-Host "REPETITION_INTERVAL=$($rep.Interval)"
Write-Host "LAST_RUN=$($info.LastRunTime)"
Write-Host "NEXT_RUN=$($info.NextRunTime)"
if ($action.WorkingDirectory -notlike "*Forext Trading Bot 1st*") {
    throw "Working directory is not the repository root."
}
if ($action.Arguments -notlike "*macro_prospective_cli collect-due*") {
    throw "Task arguments are not collect-due."
}
Write-Host "VERIFY_OK"
