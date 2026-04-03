#!/bin/bash
# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Network Configuration Restoration (Windows)
# March 29th, 2026
# Description: Restores network settings to DHCP (default configuration)
# NOTE: Requires administrator privileges

sudo networksetup -setdhcp "Wi-Fi"
