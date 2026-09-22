#!/bin/bash
# BLADE-I Phase 0.5C -- trojan-retention screen, synthesis stage (meson).
#
# The Vivado half of the retention screen. For each (design, label) it runs
# the pilot's proven `pilot_synth.tcl` -- one synthesis, then enumerate the
# design's trojan name-patterns in the post-synthesis netlist against the
# benign control -- emitting exactly the `trojan_post_synth.txt` evidence
# `retention_screen.py` consumes (via `assemble_retention.py`).
#
# SYNTHESIS-ONLY on purpose. The PRIMARY, strictest test in the taxonomy is
# NO_TRACE_AFTER_SYNTHESIS -- did the trojan ever enter the hardware -- and it
# is decided from the post-synthesis netlists alone (stage 1 of
# classify_design). A synthesis-only screen therefore settles every design the
# static tie-off audit nominated as TROJAN_STATE_FROZEN, at one synthesis per
# label instead of a full implementation.
#
# This run targets the tie-off audit's nominated worklist (default: the three
# PIC16F84 designs not yet Vivado-confirmed -- T100 was confirmed in the
# 0.5B pilot). Pass design tags as arguments to screen others; each must ship
# a TjFree/TjIn Verilog pair whose top module is `top`.
#
# USAGE (on meson):
#   ./screen_trojan_retention.sh [DESIGN ...]
#   ./screen_trojan_retention.sh PIC16F84-T200 PIC16F84-T300 PIC16F84-T400
#
# Not for designs needing IP (AES) or VHDL (BasicRSA) without a matching
# pattern file and top; those are out of this targeted screen's scope.

set -eu

DESIGNS=("$@")
if [ ${#DESIGNS[@]} -eq 0 ]; then
  DESIGNS=(PIC16F84-T200 PIC16F84-T300 PIC16F84-T400)
fi

SCRATCH="${SCRATCH:-$HOME/blade_pilot_phase05b}"
VIVADO_SETTINGS="${VIVADO_SETTINGS:-/share/reconfig/xilinx2/Vivado/2023.2/settings64.sh}"
BENCH="${BENCH:-$SCRATCH/sources/trusthub_benchmarks}"
XDC="${XDC:-$SCRATCH/sources/Constraints/PYNQ-Z1_AES.xdc}"
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
OUT="$SCRATCH/retention_screen"
TCL="$SCRIPTS/pilot_synth.tcl"

# shellcheck disable=SC1090
source "$VIVADO_SETTINGS" >/dev/null 2>&1 || true
command -v vivado >/dev/null || { echo "vivado not on PATH" >&2; exit 1; }
[ -f "$TCL" ] || { echo "missing $TCL" >&2; exit 1; }
[ -f "$XDC" ] || { echo "missing XDC $XDC" >&2; exit 1; }

mkdir -p "$OUT"
echo "=== retention screen (synthesis-only) ==="
echo "=== designs: ${DESIGNS[*]} ==="

for D in "${DESIGNS[@]}"; do
  # Pattern file: <design-family>.txt if present, else the exact-tag file.
  fam="${D%%-*}"
  PAT="$SCRIPTS/trojan_patterns_${fam}.txt"
  [ -f "$PAT" ] || PAT="$SCRIPTS/trojan_patterns_${D}.txt"
  if [ ! -f "$PAT" ]; then
    echo "SKIP $D: no pattern file ($SCRIPTS/trojan_patterns_${fam}.txt)" >&2
    continue
  fi
  for LAB in TjFree TjIn; do
    SRC="$BENCH/$D/src/$LAB"
    O="$OUT/$D/$LAB"
    if [ ! -d "$SRC" ]; then
      echo "SKIP $D/$LAB: no sources at $SRC" >&2; continue
    fi
    mkdir -p "$O"
    echo "--- synth $D/$LAB (patterns $(basename "$PAT")) -> $O"
    vivado -mode batch -notrace -source "$TCL" \
           -log "$O/synth.log" -journal "$O/synth.jou" \
           -tclargs "$D" "$LAB" "$SRC" top "$XDC" NONE NONE "$O" "$PAT" \
           2>&1 | tail -2
  done
done

echo
echo "=== DONE. evidence under $OUT/<design>/<label>/reports/trojan_post_synth.txt ==="
echo "    bring back and run:  python3 assemble_retention.py --screen-dir <dir>"
