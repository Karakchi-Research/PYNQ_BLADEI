#!/bin/bash
# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Network Configuration for PYNQ Board Access (Windows)
# March 29th, 2026
# Description: Switches network settings to connect to PYNQ board (192.168.2.0/24 network)
# NOTE: Requires administrator privileges

sudo networksetup -setmanual "Wi-Fi" 192.168.2.1 255.255.255.0
