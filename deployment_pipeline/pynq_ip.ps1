# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Network Configuration for PYNQ Board Access (Windows)
# March 29th, 2026
# Description: Switches Windows network settings to connect to PYNQ board (192.168.2.0/24 network)
# NOTE: Requires administrator privileges

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: This script requires administrator privileges."
    Write-Host "Please run PowerShell as Administrator and try again."
    exit 1
}

# Find active network adapter (Ethernet preferred over WiFi)
Write-Host "=== Detecting network adapters... ==="
$adapters = Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Where-Object { $_.MediaType -like "*Ethernet*" -or $_.MediaType -like "*Wireless*" }

if ($adapters.Count -eq 0) {
    Write-Host "ERROR: No active network adapters found."
    exit 1
}

# Prefer Ethernet over WiFi
$adapter = ($adapters | Where-Object { $_.MediaType -like "*Ethernet*" } | Select-Object -First 1) -or ($adapters | Select-Object -First 1)

if (-not $adapter) {
    Write-Host "ERROR: Could not select a network adapter."
    exit 1
}

$adapterName = $adapter.Name
Write-Host "Selected adapter: $adapterName"
Write-Host ""

# Configure static IP for PYNQ network access
Write-Host "=== Configuring static IP for PYNQ access (192.168.2.100/24)... ==="

# Get existing IPv4 interface configuration
$interfaceIndex = (Get-NetAdapter -Name $adapterName).InterfaceIndex
$existingIPs = Get-NetIPAddress -InterfaceIndex $interfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue

# Remove existing IP configurations
foreach ($ip in $existingIPs) {
    Remove-NetIPAddress -IPAddress $ip.IPAddress -InterfaceIndex $interfaceIndex -Confirm:$false -ErrorAction SilentlyContinue
}

# Set static IP for PYNQ network
$ipAddress = "192.168.2.100"
$prefixLength = 24
$gateway = "192.168.2.1"

try {
    New-NetIPAddress -InterfaceIndex $interfaceIndex -IPAddress $ipAddress -PrefixLength $prefixLength -DefaultGateway $gateway | Out-Null
    Write-Host "Static IP configured: $ipAddress/$prefixLength"
    Write-Host "Gateway: $gateway"
    Write-Host ""
    Write-Host "✓ Network switched to PYNQ configuration (192.168.2.x)"
    Write-Host ""
    Write-Host "You should now be able to reach the PYNQ board at: xilinx@192.168.2.99"
} catch {
    Write-Host "ERROR: Failed to configure static IP"
    Write-Host $_.Exception.Message
    exit 1
}
