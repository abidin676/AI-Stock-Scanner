[CmdletBinding()]
param(
    [switch]$WhatIf,
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$taskName = "RiverAlpha-SET-PaperScan-1645"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runnerPath = (Resolve-Path (Join-Path $PSScriptRoot "run_set_paper_scan.bat")).Path

if ($WhatIf -eq $Install) {
    throw "Choose exactly one mode: -WhatIf to preview or -Install to create the task."
}

$timeZone = Get-TimeZone
if ($timeZone.Id -ne "SE Asia Standard Time") {
    $message = "Windows time zone must be 'SE Asia Standard Time' for 16:45 Asia/Bangkok. Current: $($timeZone.Id)"
    if ($Install) {
        throw $message
    }
    Write-Warning $message
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$actionArguments = '/d /c ""{0}""' -f $runnerPath
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $actionArguments
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At "16:45"
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "River Alpha SET fresh scan to approval-only paper trading queue. No automatic approve or fill."

Write-Host "Task name : $taskName"
Write-Host "Schedule  : Monday-Friday 16:45 Asia/Bangkok"
Write-Host "Runner    : $runnerPath"
Write-Host "Project   : $projectRoot"
Write-Host "User      : $currentUser (runs only while this user is logged on)"

if ($WhatIf) {
    Write-Host "WHATIF: no Task Scheduler changes were made."
    Write-Host "Run this script again with -Install to register the task."
    exit 0
}

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "Installed scheduled task '$taskName'."
Write-Host "The task creates PENDING proposals only; it never approves or fills orders."
