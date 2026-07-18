[CmdletBinding()]
param(
    [switch]$WhatIf,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$taskName = "RiverAlpha-SET-PaperScan-1645"

if ($WhatIf -eq $Uninstall) {
    throw "Choose exactly one mode: -WhatIf to preview or -Uninstall to remove the task."
}

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "Scheduled task '$taskName' is not installed."
    exit 0
}

if ($WhatIf) {
    Write-Host "WHATIF: would remove scheduled task '$taskName'. No changes were made."
    exit 0
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Removed scheduled task '$taskName'."
