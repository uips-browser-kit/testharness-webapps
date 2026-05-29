<#
.SYNOPSIS
    Two-phase host setup check for infra/hosts.txt entries.

.PARAMETER HostsFile
    Path to the hosts file listing required entries. Default: infra/hosts.txt

.PARAMETER ExpectedIp
    IP address each hostname must resolve to. Default: 127.0.0.1
    Override for homelab or remote-host setups.

.PARAMETER Phase
    Which phases to run: 1 (DNS only), 2 (HTTP only), or both. Default: both
#>
param(
    [string]$HostsFile  = "infra/hosts.txt",
    [string]$ExpectedIp = "127.0.0.1",
    [ValidateSet("1", "2", "both")]
    [string]$Phase = "both"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $HostsFile)) {
    Write-Host "ERROR  hosts file not found: $HostsFile"
    exit 2
}

$hostnames = Get-Content $HostsFile |
    Where-Object { $_ -match '^\d' } |
    ForEach-Object { ($_ -split '\s+')[1] }

if (-not $hostnames) {
    Write-Host "ERROR  no entries found in $HostsFile"
    exit 2
}

$pass = 0
$fail = 0

# ---------------------------------------------------------------------------
# Phase 1 — DNS resolution + IP assertion
# ---------------------------------------------------------------------------

if ($Phase -eq "1" -or $Phase -eq "both") {
    Write-Host "Phase 1: DNS resolution (expected IP: $ExpectedIp)"
    foreach ($h in $hostnames) {
        try {
            $resolved = [System.Net.Dns]::GetHostAddresses($h) |
                Select-Object -First 1 -ExpandProperty IPAddressToString
            if ($resolved -eq $ExpectedIp) {
                Write-Host "  OK    $h  ($resolved)"
                $pass++
            } else {
                Write-Host "  FAIL  $h  resolves to $resolved, expected $ExpectedIp"
                $fail++
            }
        } catch {
            Write-Host "  FAIL  $h  not resolvable -- add to hosts file: $ExpectedIp  $h"
            $fail++
        }
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Phase 2 — HTTP /health reachability
# ---------------------------------------------------------------------------

if ($Phase -eq "2" -or $Phase -eq "both") {
    # idp.local (Keycloak) and metrics.local (Prometheus) have no /health endpoint
    $healthHosts = $hostnames | Where-Object { $_ -notin @("idp.local", "metrics.local") }

    Write-Host "Phase 2: HTTP /health reachability"
    foreach ($h in $healthHosts) {
        try {
            $r = Invoke-WebRequest -Uri "http://$h/health" -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -eq 200) {
                Write-Host "  OK    $h  (HTTP 200)"
                $pass++
            } else {
                Write-Host "  FAIL  $h  (HTTP $($r.StatusCode))"
                $fail++
            }
        } catch {
            Write-Host "  FAIL  $h  ($_)"
            $fail++
        }
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Host "$pass passed, $fail failed"
if ($fail -gt 0) { exit 1 }
