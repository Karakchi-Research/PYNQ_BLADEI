#!/bin/bash
# BLADE-I Phase 0.5B controlled rebuild pilot -- remote driver.
#
# Runs entirely inside an isolated scratch directory. It never writes to the
# canonical corpus repository (/share/ryes/...) and never uses rsync --delete.
#
# Matrix: 3 designs x 2 labels x (1 synthesis + 4 implementation configs).
# Every implementation variant of a label re-opens that label's single
# post-synthesis DCP.

set -u

SCRATCH="${SCRATCH:-$HOME/blade_pilot_phase05b}"
VIVADO_SETTINGS="/share/reconfig/xilinx2/Vivado/2023.2/settings64.sh"
BENCH_ROOT="$SCRATCH/sources/trusthub_benchmarks"
IP_DIR="$SCRATCH/sources/ip"
XDC="$SCRATCH/sources/Constraints/PYNQ-Z1_AES.xdc"
BUILDS="$SCRATCH/builds"
LOGS="$SCRATCH/logs"

mkdir -p "$BUILDS" "$LOGS"

# shellcheck disable=SC1090
source "$VIVADO_SETTINGS" >/dev/null 2>&1 || true

# design | benchmark dir | top(TjFree) | top(TjIn) | ip? | coe dir
DESIGNS=(
  "PIC16F84-T100|PIC16F84-T100|top|top|NONE|NONE"
  "b15-T200|b15-T200|top|top|NONE|NONE"
  "AES-T1000|AES-T1000|aes_128|top|IP|BENCH"
)

# Implementation configurations. Every directive below appears verbatim in the
# installed Vivado 2023.2 help output captured in vivado_env_capture/.
CONFIGS=(
  "C1|Default|Default|NONE"
  "C2|Explore|Explore|Explore"
  "C3|ExtraNetDelay_high|AggressiveExplore|NONE"
  "C4|AltSpreadLogic_high|NoTimingRelaxation|AggressiveExplore"
)

run_one_design() {
  local spec="$1"
  IFS='|' read -r design bench top_free top_in ipflag coeflag <<< "$spec"

  for label in TjFree TjIn; do
    local src_dir="$BENCH_ROOT/$bench/src/$label"
    local top="$top_free"
    [ "$label" = "TjIn" ] && top="$top_in"

    local ip_arg="NONE"
    local coe_arg="NONE"
    if [ "$ipflag" = "IP" ]; then ip_arg="$IP_DIR"; fi
    if [ "$coeflag" = "BENCH" ]; then coe_arg="$BENCH_ROOT/$bench"; fi

    local sdir="$BUILDS/$design/$label"
    mkdir -p "$sdir"

    if [ ! -f "$sdir/post_synth.dcp" ]; then
      echo "[$(date +%H:%M:%S)] SYNTH $design/$label (top=$top)"
      vivado -mode batch -nojournal -log "$LOGS/synth_${design}_${label}.log" \
        -source "$SCRATCH/pilot_synth.tcl" \
        -tclargs "$design" "$label" "$src_dir" "$top" "$XDC" \
                 "$ip_arg" "$coe_arg" "$sdir" \
                 "$SCRATCH/trojan_patterns_${design}.txt" \
        > "$LOGS/synth_${design}_${label}.out" 2>&1
      local rc=$?
      echo "[$(date +%H:%M:%S)] SYNTH $design/$label rc=$rc"
      if [ $rc -ne 0 ] || [ ! -f "$sdir/post_synth.dcp" ]; then
        echo "[FAIL] synthesis $design/$label rc=$rc -- skipping its impl matrix"
        continue
      fi
    else
      echo "[$(date +%H:%M:%S)] SYNTH $design/$label already present, reusing DCP"
    fi

    for cspec in "${CONFIGS[@]}"; do
      IFS='|' read -r cfg pdir rdir fdir <<< "$cspec"
      local odir="$sdir/$cfg"
      if [ -f "$odir/${design}_${label}_${cfg}.bit" ]; then
        echo "[$(date +%H:%M:%S)] IMPL $design/$label/$cfg already present, skipping"
        continue
      fi
      mkdir -p "$odir"
      echo "[$(date +%H:%M:%S)] IMPL $design/$label/$cfg (place=$pdir route=$rdir phys=$fdir)"
      vivado -mode batch -nojournal -log "$LOGS/impl_${design}_${label}_${cfg}.log" \
        -source "$SCRATCH/pilot_impl.tcl" \
        -tclargs "$design" "$label" "$sdir/post_synth.dcp" "$cfg" \
                 "$pdir" "$rdir" "$fdir" "$odir" \
                 "$SCRATCH/trojan_patterns_${design}.txt" \
        > "$LOGS/impl_${design}_${label}_${cfg}.out" 2>&1
      echo "[$(date +%H:%M:%S)] IMPL $design/$label/$cfg rc=$?"
    done
  done
}

echo "=== PILOT START $(date) ==="
vivado -version | head -3
for spec in "${DESIGNS[@]}"; do
  run_one_design "$spec"
done
echo "=== PILOT END $(date) ==="
