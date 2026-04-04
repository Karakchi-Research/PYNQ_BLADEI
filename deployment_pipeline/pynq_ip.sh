#!/bin/bash
# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: Switches macOS/Linux network settings to connect to PYNQ board (192.168.2.0/24 network)
# NOTE: Requires administrator privileges

echo "=== Configuring static IP for PYNQ access (192.168.2.100/24)... ==="
sudo networksetup -setmanual "Wi-Fi" 192.168.2.100 255.255.255.0
sudo networksetup -setrouter "Wi-Fi" 192.168.2.1

echo "Static IP configured: 192.168.2.100/24"
echo "Gateway: 192.168.2.1"
echo ""
echo "[OK] Network switched to PYNQ configuration (192.168.2.x)"
echo ""
echo "You should now be able to reach the PYNQ board at: xilinx@192.168.2.99"
