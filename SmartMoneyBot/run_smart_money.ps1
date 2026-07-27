param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$botEnvPath = Join-Path $root "bot\.env"
$pidPath = Join-Path $root "bot\sessions\instance_pid.json"
$logsDir = Join-Path $root "logs\instances"
$sharedLog = Join-Path $root "logs\bot_shared.log"
$py = "C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe"
$apiPort = 8301
$label = "Smart Money"
$safeLabel = "smart_money"

function Test-InstanceProcess {
    param([int]$ProcId)
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction Stop
        if (-not $proc) { return $false }
        $cmd = [string]($proc.CommandLine)
        if (-not $cmd) { return $false }
        if ($cmd -notlike "*-m bot.main*") { return $false }
        return $true
    } catch {
        return $false
    }
}

function Save-Pid($row) {
    New-Item -ItemType Directory -Force -Path (Split-Path $pidPath -Parent) | Out-Null
    ($row | ConvertTo-Json -Depth 6) | Set-Content -Path $pidPath -Encoding UTF8
}

function Load-Pid {
    if (Test-Path $pidPath) {
        return (Get-Content $pidPath -Raw | ConvertFrom-Json)
    }
    return $null
}

function Stop-PortOwner {
    param([int]$Port)
    try {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($listener in $listeners) {
            $ownerPid = [int]$listener.OwningProcess
            if ($ownerPid -gt 0) {
                try {
                    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction Stop
                    $parentPid = [int]$proc.ParentProcessId
                    Stop-Process -Id $ownerPid -Force
                    Write-Host "[CLEANUP] Stopped port owner pid=$ownerPid port=$Port"
                    if ($parentPid -gt 0) {
                        try {
                            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid" -ErrorAction Stop
                            if ($parent.Name -ieq "powershell.exe") {
                                Stop-Process -Id $parentPid -Force
                                Write-Host "[CLEANUP] Stopped parent launcher pid=$parentPid"
                            }
                        } catch {}
                    }
                } catch {}
            }
        }
    } catch {}
}

if (-not (Test-Path $py)) { throw "Python not found: $py" }
if (-not (Test-Path $botEnvPath)) { throw "Missing env file: $botEnvPath" }

if ($Action -eq "stop" -or $Action -eq "restart") {
    $row = Load-Pid
    if ($row -and (Test-InstanceProcess -ProcId ([int]$row.pid))) {
        Stop-Process -Id ([int]$row.pid) -Force
        Write-Host "[STOP] $label pid=$($row.pid)"
    } else {
        Write-Host "[STOP] $label stale/not running"
    }
    Stop-PortOwner -Port $apiPort
    Save-Pid $null
    if ($Action -eq "stop") { exit 0 }
}

if ($Action -eq "start" -or $Action -eq "restart") {
    Stop-PortOwner -Port $apiPort
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    $instLog = Join-Path $logsDir ("{0}.log" -f $safeLabel)
    $command = "`$env:API_PORT='$apiPort'; " +
        "`$env:BOT_LOG_FILE='$instLog'; " +
        "`$env:BOT_SHARED_LOG_FILE='$sharedLog'; " +
        "Set-Location '$root'; " +
        "& '$py' -X utf8 -u -m bot.main"
    $p = Start-Process -FilePath "powershell.exe" -ArgumentList @("-Command", $command) -PassThru
    Save-Pid @{ label = $label; safe_label = $safeLabel; login = 109961694; api_port = $apiPort; pid = $p.Id; log = $instLog; started_at = (Get-Date).ToString("s") }
    Write-Host "[START] $label | pid=$($p.Id) | port=$apiPort"
    Write-Host "Log: $instLog"
    exit 0
}

if ($Action -eq "status") {
    $row = Load-Pid
    if (-not $row) {
        Write-Host "No running instance found in pid registry."
        exit 0
    }
    if (Test-InstanceProcess -ProcId ([int]$row.pid)) {
        Write-Host "[RUNNING] $($row.label) | pid=$($row.pid) | port=$($row.api_port) | log=$($row.log)"
    } else {
        Write-Host "[DOWN] $($row.label) | pid=$($row.pid) | last_log=$($row.log)"
    }
}
