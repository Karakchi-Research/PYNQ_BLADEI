# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script orchestrates local bitstream generation and edge deployment for BLADEI vetting.
#              It builds FPGA bitstreams locally using Vivado v2023.2 on your machine, then deploys to a
#              PYNQ-supported FPGA board (the edge) for real-time vetting with BLADEI.
#              All configuration variables can be overridden via environment exports.
#              The script includes robust error handling, user-friendly menus, and ensures proper cleanup of resources on exit.

# Set error handling
$ErrorActionPreference = "Stop"

# Get the directory where this script is located
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

# Configuration variables (user-customizable)
$VIVADO_SETTINGS = $env:VIVADO_SETTINGS -or "$env:ProgramFiles\Xilinx\Vivado\2023.2\settings64.bat"
$BENCH_ROOT = $env:BENCH_ROOT -or "$SCRIPT_DIR\trusthub_benchmarks"
$PYNQ_HOST = $env:PYNQ_HOST -or "xilinx@192.168.2.99"
$PYNQ_PASS = $env:PYNQ_PASS -or "xilinx"

# Vivado project paths (fixed)
$PROJECT_DIR = "$SCRIPT_DIR\trusthub_pynq_z1"
$PROJECT_XPR = "$PROJECT_DIR\trusthub_pynq_z1.xpr"

# Derived variables
$RUNS_DIR = "$PROJECT_DIR\trusthub_pynq_z1.runs\impl_1"

# PYNQ deployment paths
$PYNQ_DEPLOY_DIR = "/home/xilinx/jupyter_notebooks/PYNQ_BLADEI/mock_deployment"
$PYNQ_SCRIPT = "/home/xilinx/jupyter_notebooks/PYNQ_BLADEI/deploy_model.py"

# Constraints
$CONSTRAINTS_DIR = "$SCRIPT_DIR\Constraints"
$XDC_AES = "$CONSTRAINTS_DIR\PYNQ-Z1_AES.xdc"
$XDC_RS232 = "$CONSTRAINTS_DIR\PYNQ-Z1_RS232.xdc"
$XDC_VHDL = "$CONSTRAINTS_DIR\PYNQ-Z1_vhdl.xdc"
$ACTIVE_XDC = "$CONSTRAINTS_DIR\PYNQ-Z1_C.xdc"

# Output directory
$OUT_ROOT = ".\mock_deployment"

# Global state flags
$script:XDC_BACKUP = ""

# Helper function to perform cleanup on exit
function Cleanup {
    Write-Host ""
    Write-Host "=== Initializing final cleanup... ==="
    
    # Restore constraint file if backed up
    if ($script:XDC_BACKUP -and (Test-Path $script:XDC_BACKUP)) {
        Copy-Item $script:XDC_BACKUP $ACTIVE_XDC -Force
        Remove-Item $script:XDC_BACKUP -Force
        Write-Host "Constraints restored"
    }
    
    Write-Host "=== Final cleanup complete! ==="
}

# Register cleanup on exit
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

# Helper function to discover local benchmarks
function Get-Benchmarks {
    if (-not (Test-Path $BENCH_ROOT -PathType Container)) {
        Write-Host "ERROR: Benchmark root directory not found: $BENCH_ROOT"
        return $null
    }
    
    $benchmarks = @()
    Get-ChildItem $BENCH_ROOT -Directory | ForEach-Object { $benchmarks += $_.Name }
    return $benchmarks | Sort-Object
}

# Helper function to display benchmark menu
function Show-Menu {
    Write-Host "=== Discovering available benchmarks... ==="
    Write-Host ""
    
    $script:BENCHMARKS = @(Get-Benchmarks)
    
    if ($script:BENCHMARKS.Count -eq 0) {
        Write-Host "ERROR: No benchmarks found in: $BENCH_ROOT"
        return $false
    }
    
    Write-Host "Available Benchmarks:"
    for ($i = 0; $i -lt $script:BENCHMARKS.Count; $i++) {
        Write-Host "  $($i+1))) $($script:BENCHMARKS[$i])"
    }
    Write-Host "  0) Exit"
    Write-Host ""
    return $true
}

# Helper function to display menu and handle user selection
function Show-MainMenu {
    Write-Host "=============== FPGA-AAS Demonstration - Local Build & Edge Deployment ==============="
    
    while ($true) {
        if (-not (Show-Menu)) { exit 1 }
        
        $choice = Read-Host "Select benchmark (0 to exit)"
        
        # Validate input
        if ($choice -notmatch '^\d+$') {
            Write-Host "ERROR: Invalid input. Please enter a number."
            continue
        }
        
        $choice = [int]$choice
        
        # Exit option
        if ($choice -eq 0) {
            Write-Host "Exiting demo."
            break
        }
        
        # Valid benchmark selection
        if ($choice -ge 1 -and $choice -le $script:BENCHMARKS.Count) {
            $SELECTED_BENCH = $script:BENCHMARKS[$choice - 1]
            Run-Pipeline $SELECTED_BENCH
            break
        } else {
            Write-Host "ERROR: Invalid selection. Please try again."
        }
    }
}

# Helper function to verify Vivado installation
function Test-VivadoInstall {
    if (-not (Test-Path $VIVADO_SETTINGS)) {
        Write-Host "ERROR: Vivado settings script not found: $VIVADO_SETTINGS"
        Write-Host ""
        Write-Host "Please set VIVADO_SETTINGS environment variable to your Vivado installation path."
        Write-Host "Example: `$env:VIVADO_SETTINGS=`"C:\Xilinx\Vivado\2023.2\settings64.bat`""
        return $false
    }
    
    if (-not (Test-Path $PROJECT_XPR)) {
        Write-Host "ERROR: Vivado project file not found: $PROJECT_XPR"
        Write-Host ""
        Write-Host "Please ensure the Vivado project is located at: $PROJECT_DIR"
        return $false
    }
    
    return $true
}

# Function that runs the full pipeline for a selected benchmark
function Run-Pipeline {
    param([string]$SELECTED_BENCH)
    
    Write-Host ""
    Write-Host "========================================"
    Write-Host "Building: $SELECTED_BENCH"
    Write-Host "========================================"
    Write-Host ""
    
    # Verify Vivado is available
    if (-not (Test-VivadoInstall)) { return }
    
    # ----- Determine benchmark variant and structure -----
    Write-Host "=== Analyzing benchmark structure... ==="
    
    $BENCH_DIR = "$BENCH_ROOT\$SELECTED_BENCH"
    if (-not (Test-Path $BENCH_DIR)) {
        Write-Host "ERROR: Benchmark directory not found: $BENCH_DIR"
        return
    }
    
    # Check if this is an ISCAS85 benchmark (starts with 'c')
    $IS_ISCAS85 = $SELECTED_BENCH -match '^c\d'
    $VARIANT = if ($IS_ISCAS85) { "malicious" } else { "benign" }
    
    # Determine source directory based on benchmark type
    if ($IS_ISCAS85) {
        $SRC_DIR = $BENCH_DIR
    } else {
        $SRC_DIR = "$BENCH_DIR\src\TjFree"
        
        if (-not (Test-Path $SRC_DIR)) {
            Write-Host "WARNING: Benign variant not found, attempting malicious variant..."
            $SRC_DIR = "$BENCH_DIR\src\TjIn"
            $VARIANT = "malicious"
        }
        
        if (-not (Test-Path $SRC_DIR)) {
            Write-Host "ERROR: Could not find variant directory in: $BENCH_DIR"
            return
        }
    }
    
    Write-Host "Benchmark: $SELECTED_BENCH"
    Write-Host "Variant:   $VARIANT"
    Write-Host "Source:    $SRC_DIR"
    Write-Host ""
    
    # ----- Determine top-level module -----
    Write-Host "=== Determining top-level module... ==="
    
    $TOP = ""
    if (Test-Path "$SRC_DIR\aes_128.v") {
        $TOP = "aes_128"
    } elseif (Test-Path "$SRC_DIR\top_benign.v") {
        $TOP = "top_benign"
    } elseif (Test-Path "$SRC_DIR\top.v") {
        $TOP = "top"
    } elseif (Test-Path "$SRC_DIR\top.vhd") {
        $TOP = "top"
    } else {
        $hdlFiles = @(Get-ChildItem $SRC_DIR -Filter "*.v", "*.sv", "*.vhd", "*.vhdl" | Select-Object -First 1)
        if ($hdlFiles.Count -gt 0) {
            $content = Get-Content $hdlFiles[0].FullName | Select-String -Pattern '^\s*(module|entity)\s+([A-Za-z_][A-Za-z0-9_]*)' -List
            if ($content) {
                $TOP = $content.Matches[0].Groups[2].Value
            }
        }
    }
    
    if (-not $TOP) {
        Write-Host "ERROR: Could not determine top-level module in: $SRC_DIR"
        return
    }
    
    Write-Host "Top-level module: $TOP"
    Write-Host ""
    
    $STAMP = Get-Date -Format "yyyyMMdd_HHmmss"
    $LABEL = "${SELECTED_BENCH}_${VARIANT}_${STAMP}"
    
    # ----- Select and prepare constraint file -----
    Write-Host "=== Selecting constraint file... ==="
    
    $XDC_SRC = ""
    
    if ($SELECTED_BENCH -match '[Aa][Ee][Ss]') {
        $XDC_SRC = $XDC_AES
        Write-Host "Selected: AES constraints"
    } elseif ($SELECTED_BENCH -match '[Rr][Ss]232') {
        $XDC_SRC = $XDC_RS232
        Write-Host "Selected: RS232 constraints"
    } elseif ($SELECTED_BENCH -match '^b19-T' -or $SELECTED_BENCH -match '^BasicRSA') {
        $XDC_SRC = $XDC_VHDL
        Write-Host "Selected: VHDL constraints"
    } else {
        $XDC_SRC = $XDC_AES
        Write-Host "Selected: Default (AES) constraints"
    }
    
    if (-not (Test-Path $XDC_SRC)) {
        Write-Host "ERROR: Constraint template not found: $XDC_SRC"
        return
    }
    
    # Backup and swap the active XDC file
    $script:XDC_BACKUP = "$ACTIVE_XDC.bak_$STAMP"
    Copy-Item $ACTIVE_XDC $script:XDC_BACKUP
    Copy-Item $XDC_SRC $ACTIVE_XDC -Force
    Write-Host "Constraints prepared"
    Write-Host ""
    
    # ----- Generate bitstream locally via Vivado -----
    Write-Host "=== Generating bitstream locally (Vivado)... ==="
    
    # Source Vivado settings (Windows batch file)
    cmd /c "call `"$VIVADO_SETTINGS`" && vivado -mode tcl -source run_random_build.tcl -tclargs `"$PROJECT_XPR`" `"$SRC_DIR`" $TOP"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Vivado build failed"
        return
    }
    
    # ----- Locate and copy generated bitstream -----
    Write-Host ""
    Write-Host "=== Locating bitstream... ==="
    
    $bitFiles = @(Get-ChildItem "$RUNS_DIR\*.bit" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($bitFiles.Count -eq 0) {
        Write-Host "ERROR: No .bit file found in: $RUNS_DIR"
        return
    }
    
    $NEWEST_BIT = $bitFiles[0].FullName
    
    if (-not (Test-Path $OUT_ROOT)) {
        New-Item -ItemType Directory -Path $OUT_ROOT -Force | Out-Null
    }
    $LOCAL_BITSTREAM = "$OUT_ROOT\${LABEL}.bit"
    Copy-Item $NEWEST_BIT $LOCAL_BITSTREAM
    
    $bitSize = (Get-Item $LOCAL_BITSTREAM).Length / 1MB
    Write-Host "Bitstream generated: $LABEL"
    Write-Host "Size: $([Math]::Round($bitSize, 2)) MB"
    Write-Host ""
    
    # ----- Upload bitstream to PYNQ board -----
    Write-Host "=== Uploading the bitstream to the edge device... ==="
    Write-Host "Target: $PYNQ_HOST"
    Write-Host ""
    
    # Create deployment directory
    ssh $PYNQ_HOST "mkdir -p '$PYNQ_DEPLOY_DIR'" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not connect to PYNQ board at $PYNQ_HOST"
        Remove-Item $LOCAL_BITSTREAM -Force
        return
    }
    
    # Upload bitstream
    $BITSTREAM_NAME = Split-Path $LOCAL_BITSTREAM -Leaf
    scp $LOCAL_BITSTREAM "$PYNQ_HOST:$PYNQ_DEPLOY_DIR/$BITSTREAM_NAME" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to transfer bitstream to PYNQ board"
        Remove-Item $LOCAL_BITSTREAM -Force
        return
    }
    
    Write-Host "Bitstream transferred: $BITSTREAM_NAME"
    Write-Host ""
    
    # ----- Run BLADEI vetting on PYNQ board -----
    Write-Host "=== Vetting the bitstream via BLADEI... ==="
    ssh $PYNQ_HOST "python3 '$PYNQ_SCRIPT' '$PYNQ_DEPLOY_DIR/$BITSTREAM_NAME'" 2>$null
    
    Write-Host ""
    
    # ----- Cleanup -----
    Write-Host "=== Cleaning up local copy of bitstream... ==="
    Remove-Item $LOCAL_BITSTREAM -Force
    Write-Host "Deleted local copy: $LOCAL_BITSTREAM"
    Write-Host ""
    
    Write-Host "=== Local build and edge deployment complete! ==="
}

# Main execution
Show-MainMenu
