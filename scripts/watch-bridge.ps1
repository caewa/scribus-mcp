# Watches the bridge discovery file + pings the bridge every 200ms.
# Run this in one terminal, then launch Scribus with -py in another.
# Outputs a timestamped line every state change, so we can see the bridge
# lifecycle: when it appears, when it accepts connections, when it dies.

$ErrorActionPreference = 'SilentlyContinue'

$discoveryPath = Join-Path $env:LOCALAPPDATA 'scribus-mcp\scribus-mcp.json'
$logPath       = Join-Path $env:LOCALAPPDATA 'scribus-mcp\bridge.log'

Write-Host "Watching $discoveryPath"
Write-Host "Watching $logPath"
Write-Host "(Ctrl+C to stop)"
Write-Host ''

$lastState = ''
$lastPort  = $null
$lastLogSize = 0
$pingCount = 0

while ($true) {
    $state = ''
    $port = $null
    $token = $null

    if (Test-Path $discoveryPath) {
        try {
            $info = Get-Content $discoveryPath -Raw | ConvertFrom-Json
            $port = $info.port
            $token = $info.token
            $state = "discovery present (port=$port, pid=$($info.pid))"
        } catch {
            $state = 'discovery file unreadable'
        }
    } else {
        $state = 'discovery missing'
    }

    if ($state -ne $lastState) {
        $ts = (Get-Date).ToString('HH:mm:ss.fff')
        Write-Host "[$ts] STATE: $state"
        $lastState = $state
        $lastPort = $port
    }

    if ($port) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $async = $tcp.BeginConnect('127.0.0.1', $port, $null, $null)
            $ok = $async.AsyncWaitHandle.WaitOne(500)
            if ($ok -and $tcp.Connected) {
                $tcp.EndConnect($async)
                $body = ('{"kind":"ping","token":"' + $token + '"}' + "`n")
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
                $stream = $tcp.GetStream()
                $stream.WriteTimeout = 2000
                $stream.ReadTimeout = 2000
                $stream.Write($bytes, 0, $bytes.Length)
                $buf = New-Object byte[] 1024
                $n = $stream.Read($buf, 0, $buf.Length)
                $resp = [System.Text.Encoding]::UTF8.GetString($buf, 0, $n).Trim()
                $pingCount++
                if ($pingCount -le 3 -or $pingCount % 25 -eq 0) {
                    $ts = (Get-Date).ToString('HH:mm:ss.fff')
                    Write-Host "[$ts] PING #$pingCount -> $resp"
                }
                $tcp.Close()
            } else {
                $tcp.Close()
                $ts = (Get-Date).ToString('HH:mm:ss.fff')
                if ($lastState -ne 'connect-failed') {
                    Write-Host "[$ts] CONNECT FAILED on port $port (no listener)"
                    $lastState = 'connect-failed'
                }
            }
        } catch {
            $ts = (Get-Date).ToString('HH:mm:ss.fff')
            Write-Host "[$ts] PING ERROR: $_"
        }
    }

    if (Test-Path $logPath) {
        $size = (Get-Item $logPath).Length
        if ($size -gt $lastLogSize) {
            $newContent = Get-Content $logPath -Raw
            $delta = $newContent.Substring([Math]::Max(0, $lastLogSize))
            Write-Host "--- bridge.log delta ---"
            Write-Host $delta.TrimEnd()
            Write-Host "------------------------"
            $lastLogSize = $size
        }
    }

    Start-Sleep -Milliseconds 200
}
