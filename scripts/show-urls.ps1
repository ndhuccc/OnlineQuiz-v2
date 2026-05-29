param(
    [int]$Port = 3080,
    [string]$Path = "/teacher",
    [string]$LocalLabel = "Local",
    [string]$NetworkLabel = "Network"
)

Write-Host "[INFO] ${LocalLabel}: http://localhost:${Port}${Path}"

$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -ExpandProperty IPAddress

foreach ($ip in $ips) {
    Write-Host "[INFO] ${NetworkLabel}: http://${ip}:${Port}${Path}"
}
