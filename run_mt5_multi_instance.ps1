param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$botEnvPath = Join-Path $root "bot\.env"
$pidsPath = Join-Path $root "bot\sessions\instance_pids.json"
$logsDir = Join-Path $root "logs\instances"
$sharedLog = Join-Path $root "logs\bot_shared.log"
$py = "C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe"
$showInstanceWindows = (
    [string]::Equals($env:SHOW_INSTANCE_WINDOWS, "1", [System.StringComparison]::OrdinalIgnoreCase) -or
    [string]::Equals($env:SHOW_INSTANCE_WINDOWS, "true", [System.StringComparison]::OrdinalIgnoreCase) -or
    [string]::Equals($env:SHOW_INSTANCE_WINDOWS, "yes", [System.StringComparison]::OrdinalIgnoreCase) -or
    [string]::Equals($env:SHOW_INSTANCE_WINDOWS, "on", [System.StringComparison]::OrdinalIgnoreCase)
)

function Parse-BotEnv {
    param([string]$Path)
    $map = @{}
    foreach ($line in Get-Content -Path $Path) {
        $s = $line.Trim()
        if (-not $s -or $s.StartsWith("#")) { continue }
        $idx = $s.IndexOf("=")
        if ($idx -lt 1) { continue }
        $k = $s.Substring(0, $idx).Trim()
        $v = $s.Substring($idx + 1).Trim().Trim('"').Trim("'")
        $map[$k] = $v
    }
    return $map
}

function Parse-Accounts {
    param([string]$Raw)
    $out = @()
    if (-not $Raw) { return $out }
    foreach ($entry in ($Raw -split ";")) {
        $e = $entry.Trim()
        if (-not $e) { continue }
        $parts = $e -split "\|"
        if ($parts.Count -lt 5) { continue }
        $label = $parts[0].Trim()
        $login = $parts[1].Trim()
        $password = $parts[2].Trim()
        $server = $parts[3].Trim()
        $strategy = $parts[4].Trim()
        $path = if ($parts.Count -ge 6) { $parts[5].Trim() } else { "" }
        $allowed = if ($parts.Count -ge 7) { $parts[6].Trim() } else { "" }
        $safe = (($label -replace "[^A-Za-z0-9]+", "_").Trim("_")).ToLower()
        if (-not $safe) { $safe = "acc_$login" }
        $out += [pscustomobject]@{
            Label = $label
            SafeLabel = $safe
            Login = $login
            Password = $password
            Server = $server
            Strategy = $strategy
            Path = $path
            Allowed = $allowed
            ApiPort = 0
        }
    }
    return $out
}

function Load-Pids {
    if (Test-Path $pidsPath) {
        return (Get-Content $pidsPath -Raw | ConvertFrom-Json)
    }
    return @()
}

function Test-InstanceProcess {
    param(
        [int]$ProcId,
        [int]$ApiPort
    )
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction Stop
        if (-not $proc) { return $false }
        $cmd = [string]($proc.CommandLine)
        if (-not $cmd) { return $false }
        if ($cmd -notlike "*-m bot.main*") { return $false }
        if ($ApiPort -gt 0 -and $cmd -notlike "*API_PORT='$ApiPort'*" -and $cmd -notlike "*API_PORT=$ApiPort*") {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Save-Pids($rows) {
    New-Item -ItemType Directory -Force -Path (Split-Path $pidsPath -Parent) | Out-Null
    ($rows | ConvertTo-Json -Depth 6) | Set-Content -Path $pidsPath -Encoding UTF8
}

function Stop-OrphanBotMainProcesses {
    param([object[]]$KnownPowerShellPids)
    $known = @{}
    foreach ($kp in $KnownPowerShellPids) {
        try { $known[[int]$kp] = $true } catch {}
    }

    # Kill any extra launcher PowerShell that runs `-m bot.main` outside pid registry.
    $psOrphans = Get-CimInstance Win32_Process -Filter "name='powershell.exe'" |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like "*-m bot.main*" -and
            -not $known.ContainsKey([int]$_.ProcessId)
        }
    foreach ($p in $psOrphans) {
        try {
            Stop-Process -Id ([int]$p.ProcessId) -Force
            Write-Host "[CLEANUP] Stopped orphan launcher pid=$($p.ProcessId)"
        } catch {}
    }

    # Also kill any standalone python `-m bot.main` process (e.g., manually launched old process).
    $pyOrphans = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*-m bot.main*" }
    foreach ($p in $pyOrphans) {
        try {
            Stop-Process -Id ([int]$p.ProcessId) -Force
            Write-Host "[CLEANUP] Stopped orphan bot.main python pid=$($p.ProcessId)"
        } catch {}
    }
}

if (-not (Test-Path $py)) {
    throw "Python not found: $py"
}
if (-not (Test-Path $botEnvPath)) {
    throw "Missing env file: $botEnvPath"
}

$envMap = Parse-BotEnv -Path $botEnvPath
$raw = $envMap["MT5_EXTRA_ACCOUNTS"]
$accounts = Parse-Accounts -Raw $raw
if ($accounts.Count -eq 0) {
    throw "No accounts found in MT5_EXTRA_ACCOUNTS"
}

$basePort = 8101
for ($i = 0; $i -lt $accounts.Count; $i++) {
    $accounts[$i].ApiPort = $basePort + $i
}

if ($Action -eq "stop" -or $Action -eq "restart") {
    $rows = Load-Pids
    foreach ($r in $rows) {
        try {
            $pid = [int]$r.pid
            if (Test-InstanceProcess -ProcId $pid -ApiPort ([int]$r.api_port)) {
                Stop-Process -Id $pid -Force
                Write-Host "[STOP] $($r.label) pid=$pid"
            } else {
                Write-Host "[STOP] $($r.label) stale/non-bot pid=$pid skipped"
            }
        } catch {
            Write-Host "[STOP] $($r.label) already stopped"
        }
    }
    Stop-OrphanBotMainProcesses -KnownPowerShellPids ($rows | ForEach-Object { $_.pid })
    Save-Pids @()
    if ($Action -eq "stop") { exit 0 }
}

if ($Action -eq "start" -or $Action -eq "restart") {
    Stop-OrphanBotMainProcesses -KnownPowerShellPids @()
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    $started = @()
    foreach ($a in $accounts) {
        $instLog = Join-Path $logsDir ("{0}.log" -f $a.SafeLabel)
        $argList = @(
            "-Command",
            "`$env:MT5_LOGIN='$($a.Login)'; " +
            "`$env:MT5_PASSWORD='$($a.Password)'; " +
            "`$env:MT5_SERVER='$($a.Server)'; " +
            "`$env:MT5_PATH='$($a.Path)'; " +
            "`$env:MT5_PORTABLE='1'; " +
            "`$env:MT5_PRIMARY_STRATEGY='$($a.Strategy)'; " +
            "`$env:MT5_PRIMARY_ALLOWED_SYMBOLS='$($a.Allowed)'; " +
            "`$env:MT5_EXTRA_ACCOUNTS=''; " +
            "`$env:BOT_SINGLE_ACCOUNT_MODE='1'; " +
            "`$env:API_PORT='$($a.ApiPort)'; " +
            "`$env:BOT_LOG_FILE='$instLog'; " +
            "`$env:BOT_SHARED_LOG_FILE='$sharedLog'; " +
            "Set-Location '$root'; " +
            "& '$py' -X utf8 -u -m bot.main"
        )
        if ($showInstanceWindows) {
            $p = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -PassThru
        } else {
            $p = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -WindowStyle Hidden -PassThru
        }
        $started += [pscustomobject]@{
            label = $a.Label
            safe_label = $a.SafeLabel
            login = $a.Login
            strategy = $a.Strategy
            api_port = $a.ApiPort
            pid = $p.Id
            log = $instLog
            started_at = (Get-Date).ToString("s")
        }
        Write-Host "[START] $($a.Label) | pid=$($p.Id) | port=$($a.ApiPort)"
    }
    Save-Pids $started
    Write-Host ""
    Write-Host "Shared log: $sharedLog"
    exit 0
}

if ($Action -eq "status") {
    $rows = Load-Pids
    if (-not $rows -or $rows.Count -eq 0) {
        Write-Host "No running instances found in pid registry."
        exit 0
    }
    foreach ($r in $rows) {
        if (Test-InstanceProcess -ProcId ([int]$r.pid) -ApiPort ([int]$r.api_port)) {
            Write-Host "[RUNNING] $($r.label) | pid=$($r.pid) | port=$($r.api_port) | log=$($r.log)"
        } else {
            Write-Host "[DOWN] $($r.label) | pid=$($r.pid) | last_log=$($r.log)"
        }
    }
}
