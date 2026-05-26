# register_tunnel_task.ps1
# Run this ONCE as Administrator to register the SSH tunnel as a Windows startup task.
# After registration, the tunnel will start automatically on every Windows login.
#
# HOW TO RUN:
#   Right-click PowerShell → "Run as Administrator"
#   Then run: .\register_tunnel_task.ps1

$TaskName   = "TradingBotSSHTunnel"
$ScriptPath = "$PSScriptRoot\ssh_tunnel.bat"
$LogPath    = "$PSScriptRoot\ssh_tunnel.log"

# Remove old task if it exists
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Old task removed." -ForegroundColor Yellow
}

# Action: run ssh_tunnel.bat via cmd, redirect output to log
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`" >> `"$LogPath`" 2>&1"

# Trigger: at user logon (runs in background)
$Trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings: run whether user is logged on or not, restart on failure
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# Principal: run as current user
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Description "SSH reverse tunnel: Windows localhost:8001 → VPS localhost:2223 (Trading Bot API)" `
    -Force

Write-Host ""
Write-Host "✅ Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "   Tunnel will auto-start on every Windows login." -ForegroundColor Cyan
Write-Host ""
Write-Host "To start it RIGHT NOW without rebooting, run:" -ForegroundColor Yellow
Write-Host "   Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
Write-Host ""
Write-Host "To check status:" -ForegroundColor Yellow
Write-Host "   Get-ScheduledTask -TaskName '$TaskName' | Select-Object State" -ForegroundColor White
