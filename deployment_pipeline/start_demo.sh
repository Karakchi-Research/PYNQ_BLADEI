#!/bin/bash
# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script orchestrates local bitstream generation and edge deployment for BLADEI vetting.
#              It builds FPGA bitstreams locally using Vivado v2023.2 on your machine (the cloud), then deploys to a
#              PYNQ-supported FPGA board (the edge) for real-time vetting with BLADEI.
#              All configuration variables can be overridden via environment exports.
#              The script includes robust error handling, user-friendly menus, and ensures proper cleanup of resources on exit.

set -e  # Set strict error handling
sudo -v  # Ask for sudo password upfront to avoid interruptions later

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration variables (user-customizable)
VIVADO_SETTINGS="${VIVADO_SETTINGS:-/opt/Xilinx/Vivado/2023.2/settings64.sh}"
BENCH_ROOT="${BENCH_ROOT:-$SCRIPT_DIR/trusthub_benchmarks}"
PYNQ_HOST="${PYNQ_HOST:-xilinx@192.168.2.99}"
PYNQ_PASS="${PYNQ_PASS:-xilinx}"

# Vivado project paths (fixed)
PROJECT_DIR="$SCRIPT_DIR/bladei_pynq_z1"
PROJECT_XPR="$PROJECT_DIR/bladei_pynq_z1.xpr"

# Derived variables
RUNS_DIR="$(dirname "$PROJECT_XPR")/$(basename "$PROJECT_XPR" .xpr).runs/impl_1"

# PYNQ deployment paths
PYNQ_DEPLOY_DIR="/home/xilinx/jupyter_notebooks/PYNQ_BLADEI/mock_deployment"
PYNQ_SCRIPT="/home/xilinx/jupyter_notebooks/PYNQ_BLADEI/deploy_model.py"

# Constraints
CONSTRAINTS_DIR="$SCRIPT_DIR/Constraints"
XDC_AES="$CONSTRAINTS_DIR/PYNQ-Z1_AES.xdc"
XDC_RS232="$CONSTRAINTS_DIR/PYNQ-Z1_RS232.xdc"
XDC_VHDL="$CONSTRAINTS_DIR/PYNQ-Z1_vhdl.xdc"
ACTIVE_XDC="$CONSTRAINTS_DIR/PYNQ-Z1_C.xdc"

# Output directory
OUT_ROOT="./mock_deployment"

# Global state flags
XDC_BACKUP=""

# Helper function to perform cleanup on exit
cleanup() {
  echo ""
  echo "=== Initializing final cleanup... ==="
  
  # Restore constraint file if backed up
  if [ -n "$XDC_BACKUP" ] && [ -f "$XDC_BACKUP" ]; then
    cp "$XDC_BACKUP" "$ACTIVE_XDC"
    rm -f "$XDC_BACKUP"
    echo "Constraints restored"
  fi
  
  echo "=== Final cleanup complete! ==="
  sudo -k
}

trap cleanup EXIT

# Helper function to discover local benchmarks
discover_benchmarks() {
  if [ ! -d "$BENCH_ROOT" ]; then
    echo "ERROR: Benchmark root directory not found: $BENCH_ROOT"
    return 1
  fi
  
  find "$BENCH_ROOT" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort || true
}

# Helper function to display benchmark menu
show_menu() {
  echo "=== Discovering available benchmarks... ==="
  echo ""
  
  # Discover benchmarks into array
  BENCHMARKS=()
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    BENCHMARKS+=("$line")
  done < <(discover_benchmarks)
  
  if [ ${#BENCHMARKS[@]} -eq 0 ]; then
    echo "ERROR: No benchmarks found in: $BENCH_ROOT"
    return 1
  fi
  
  # Display available benchmarks to user
  echo "Available Benchmarks:"
  for i in "${!BENCHMARKS[@]}"; do
    echo "  $((i+1))) ${BENCHMARKS[$i]}"
  done
  echo "  0) Exit"
  echo ""
}

# Helper function to display menu and handle user selection
main_menu() {
  echo "=============== FPGA-AAS Demonstration - Local Build & Edge Deployment ==============="

  while true; do
    show_menu || exit 1
    
    read -p "Select benchmark (0 to exit): " choice
    
    # Validate input
    if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
      echo "ERROR: Invalid input. Please enter a number."
      continue
    fi
    
    # Exit option
    if [ "$choice" -eq 0 ]; then
      echo "Exiting demo."
      break
    fi
    
    # Valid benchmark selection
    if [ "$choice" -ge 1 ] && [ "$choice" -le ${#BENCHMARKS[@]} ]; then
      SELECTED_BENCH="${BENCHMARKS[$((choice-1))]}"
      run_pipeline "$SELECTED_BENCH"
      break
    else
      echo "ERROR: Invalid selection. Please try again."
    fi
  done
}

# Helper function to verify Vivado installation
verify_vivado() {
  if [ ! -f "$VIVADO_SETTINGS" ]; then
    echo "ERROR: Vivado settings script not found: $VIVADO_SETTINGS"
    echo ""
    echo "Please set VIVADO_SETTINGS environment variable to your Vivado installation path."
    echo "Example: export VIVADO_SETTINGS=/opt/Xilinx/Vivado/2023.2/settings64.sh"
    return 1
  fi
  
  if [ ! -f "$PROJECT_XPR" ]; then
    echo "ERROR: Vivado project file not found: $PROJECT_XPR"
    echo ""
    echo "Please set PROJECT_DIR environment variable to your project directory."
    echo "Example: export PROJECT_DIR=/path/to/vivado/project"
    return 1
  fi
}

# Function that runs the full pipeline for a selected benchmark
run_pipeline() {
  local SELECTED_BENCH="$1"
  
  echo ""
  echo "========================================"
  echo "Building: $SELECTED_BENCH"
  echo "========================================"
  echo ""
  
  # Verify Vivado is available
  verify_vivado || return 1
  
  # ----- Determine benchmark variant and structure -----
  echo "=== Analyzing benchmark structure... ==="
  
  BENCH_DIR="$BENCH_ROOT/$SELECTED_BENCH"
  if [ ! -d "$BENCH_DIR" ]; then
    echo "ERROR: Benchmark directory not found: $BENCH_DIR"
    return 1
  fi
  
  # Check if this is an ISCAS85 benchmark (starts with 'c')
  IS_ISCAS85=0
  if [[ "$SELECTED_BENCH" =~ ^c[0-9] ]]; then
    IS_ISCAS85=1
    VARIANT="malicious"
    SRC_DIR="$BENCH_DIR"
  else
    # For non-ISCAS85, randomly choose between benign and malicious
    RANDOM_CHOICE=$((RANDOM % 2))
    if [ $RANDOM_CHOICE -eq 0 ]; then
      VARIANT="benign"
      SRC_DIR="$BENCH_DIR/src/TjFree"
    else
      VARIANT="malicious"
      SRC_DIR="$BENCH_DIR/src/TjIn"
    fi
  fi
  
  echo "Benchmark: $SELECTED_BENCH"
  echo "Variant:   $VARIANT"
  echo "Source:    $SRC_DIR"
  echo ""
  
  # ----- Determine top-level module -----
  echo "=== Determining top-level module... ==="
  
  TOP=""
  if [ -f "$SRC_DIR/aes_128.v" ]; then
    TOP="aes_128"
  elif [ -f "$SRC_DIR/top_benign.v" ]; then
    TOP="top_benign"
  elif [ -f "$SRC_DIR/top.v" ]; then
    TOP="top"
  elif [ -f "$SRC_DIR/top.vhd" ]; then
    TOP="top"
  else
    FIRST_HDL="$(find "$SRC_DIR" -maxdepth 1 -type f \( -name "*.v" -o -name "*.sv" -o -name "*.vhd" -o -name "*.vhdl" \) | head -n 1)"
    if [ -n "$FIRST_HDL" ]; then
      TOP="$(grep -m1 -E '^[[:space:]]*(module|entity)[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' "$FIRST_HDL" | \
             sed -E 's/^[[:space:]]*(module|entity)[[:space:]]+([A-Za-z_][A-Za-z0-9_]*).*/\2/')"
    fi
  fi
  
  if [ -z "$TOP" ]; then
    echo "ERROR: Could not determine top-level module in: $SRC_DIR"
    return 1
  fi
  
  echo "Top-level module: $TOP"
  echo ""
  
  # ----- Copy .coe files for AES benchmarks -----
  if [[ "$SELECTED_BENCH" =~ [Aa][Ee][Ss] ]]; then
    echo "=== Preparing memory initialization files... ==="
    
    if [ -f "$SRC_DIR/key_memory.coe" ]; then
      cp "$SRC_DIR/key_memory.coe" "$BENCH_DIR/key_memory.coe"
      echo "Copied: key_memory.coe"
    fi
    
    if [ -f "$SRC_DIR/state_memory.coe" ]; then
      cp "$SRC_DIR/state_memory.coe" "$BENCH_DIR/state_memory.coe"
      echo "Copied: state_memory.coe"
    fi
    
    echo ""
  fi
  
  STAMP="$(date +%Y%m%d_%H%M%S)"
  LABEL="${SELECTED_BENCH}_${VARIANT}_${STAMP}"
  
  # ----- Select and prepare constraint file -----
  echo "=== Selecting constraint file... ==="
  
  XDC_SRC=""
  
  if [[ "$SELECTED_BENCH" =~ [Aa][Ee][Ss] ]]; then
    XDC_SRC="$XDC_AES"
    echo "Selected: AES constraints"
  elif [[ "$SELECTED_BENCH" =~ [Rr][Ss][232] ]]; then
    XDC_SRC="$XDC_RS232"
    echo "Selected: RS232 constraints"
  elif [[ "$SELECTED_BENCH" == b19-T* ]] || [[ "$SELECTED_BENCH" == BasicRSA* ]]; then
    XDC_SRC="$XDC_VHDL"
    echo "Selected: VHDL constraints"
  else
    XDC_SRC="$XDC_AES"
    echo "Selected: Default (AES) constraints"
  fi
  
  if [ ! -f "$XDC_SRC" ]; then
    echo "ERROR: Constraint template not found: $XDC_SRC"
    return 1
  fi
  
  # Backup and swap the active XDC file
  XDC_BACKUP="${ACTIVE_XDC}.bak_${STAMP}"
  cp "$ACTIVE_XDC" "$XDC_BACKUP"
  cp "$XDC_SRC" "$ACTIVE_XDC"
  echo "Constraints prepared"
  echo ""
  
  # ----- Generate bitstream locally via Vivado -----
  echo "=== Generating bitstream locally (Vivado)... ==="
  
  source "$VIVADO_SETTINGS"
  vivado -mode tcl -source run_random_build.tcl -tclargs "$PROJECT_XPR" "$SRC_DIR" "$TOP" || {
    echo "ERROR: Vivado build failed"
    return 1
  }
  
  # ----- Locate and copy generated bitstream -----
  echo ""
  echo "=== Locating bitstream... ==="
  
  NEWEST_BIT="$(ls -t "$RUNS_DIR"/*.bit 2>/dev/null | head -n 1 || true)"
  if [ -z "$NEWEST_BIT" ]; then
    echo "ERROR: No .bit file found in: $RUNS_DIR"
    return 1
  fi
  
  mkdir -p "$OUT_ROOT"
  LOCAL_BITSTREAM="$OUT_ROOT/${LABEL}.bit"
  cp "$NEWEST_BIT" "$LOCAL_BITSTREAM"
  
  echo "Bitstream generated: $LABEL"
  echo "Size: $(du -h "$LOCAL_BITSTREAM" | awk '{print $1}')"
  echo ""
  
  # ----- Upload bitstream to PYNQ board -----
  echo "=== Uploading the bitstream to the edge device... ==="
  echo "Target: $PYNQ_HOST"
  echo ""
  
  # Upload bitstream to temp location (scp cannot sudo)
  BITSTREAM_NAME="$(basename "$LOCAL_BITSTREAM")"
  TMP_REMOTE="/tmp/$BITSTREAM_NAME"
  sshpass -p "$PYNQ_PASS" scp "$LOCAL_BITSTREAM" "$PYNQ_HOST:$TMP_REMOTE" || {
    echo "ERROR: Failed to transfer bitstream to PYNQ board"
    rm -f "$LOCAL_BITSTREAM"
    return 1
  }
  
  # Move bitstream into deploy dir (as sudo), then hand ownership back to xilinx
  sshpass -p "$PYNQ_PASS" ssh "$PYNQ_HOST" \
    "printf '%s\n' '$PYNQ_PASS' | sudo -S -p '' mv '$TMP_REMOTE' '$PYNQ_DEPLOY_DIR/$BITSTREAM_NAME' 2>/dev/null && \
     printf '%s\n' '$PYNQ_PASS' | sudo -S -p '' chown xilinx:xilinx '$PYNQ_DEPLOY_DIR/$BITSTREAM_NAME' 2>/dev/null" || {
      echo "ERROR: Failed to place bitstream into deploy directory with sudo"
      rm -f "$LOCAL_BITSTREAM"
      return 1
    }
  
  echo "Bitstream transferred: $BITSTREAM_NAME"
  echo ""
  
  # ----- Run BLADEI vetting on PYNQ board -----
  echo "=== Vetting the bitstream via BLADEI... ==="
  sshpass -p "$PYNQ_PASS" ssh "$PYNQ_HOST" \
    "printf '%s\n' '$PYNQ_PASS' | sudo -S -p '' python3 '$PYNQ_SCRIPT' '$PYNQ_DEPLOY_DIR/$BITSTREAM_NAME' 2>/dev/null" || true
  
  echo ""
  
  # ----- Cleanup -----
  echo "=== Cleaning up local copy of bitstream... ==="
  rm -f "$LOCAL_BITSTREAM"
  echo "Deleted local copy: $LOCAL_BITSTREAM"
  echo ""
  
  echo "=== Local build and edge deployment complete! ==="
}

main_menu
