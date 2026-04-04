#!/bin/bash
# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: Restores macOS/Linux network settings to DHCP (default configuration)
# NOTE: Requires administrator privileges

echo "=== Restoring DHCP configuration (default)... ==="
sudo networksetup -setdhcp "Wi-Fi"

echo "DHCP enabled on: Wi-Fi"
echo ""
echo "Waiting for DHCP to assign an IP address..."
sleep 3

echo "[OK] Network restored to default configuration (DHCP)"
echo ""
