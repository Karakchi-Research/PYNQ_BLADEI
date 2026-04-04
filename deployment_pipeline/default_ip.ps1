# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: Restores Windows network settings to DHCP (default configuration)
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

# Restore DHCP configuration
Write-Host "=== Restoring DHCP configuration (default)... ==="

$interfaceIndex = (Get-NetAdapter -Name $adapterName).InterfaceIndex

try {
    # Get existing IP addresses
    $existingIPs = Get-NetIPAddress -InterfaceIndex $interfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    
    # Remove existing static IP configurations
    foreach ($ip in $existingIPs) {
        Remove-NetIPAddress -IPAddress $ip.IPAddress -InterfaceIndex $interfaceIndex -Confirm:$false -ErrorAction SilentlyContinue
    }
    
    # Remove gateway route if it exists
    $gateway = Get-NetRoute -InterfaceIndex $interfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.RouteMetric -lt 256 }
    foreach ($route in $gateway) {
        Remove-NetRoute -DestinationPrefix $route.DestinationPrefix -InterfaceIndex $interfaceIndex -Confirm:$false -ErrorAction SilentlyContinue
    }
    
    # Enable DHCP on the interface
    Set-NetIPInterface -InterfaceIndex $interfaceIndex -DHCP Enabled
    
    Write-Host "DHCP enabled on: $adapterName"
    Write-Host ""
    Write-Host "Waiting for DHCP to assign an IP address..."
    Start-Sleep -Seconds 3
    
    # Get assigned IP
    $newIP = Get-NetIPAddress -InterfaceIndex $interfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($newIP) {
        Write-Host "[OK] Network restored to default configuration (DHCP)"
        Write-Host "Assigned IP: $($newIP.IPAddress)"
    } else {
        Write-Host "[!] Network restored to DHCP (waiting for IP assignment)"
    }
} catch {
    Write-Host "ERROR: Failed to restore DHCP configuration"
    Write-Host $_.Exception.Message
    exit 1
}
