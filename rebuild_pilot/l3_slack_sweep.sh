#!/bin/bash
# BLADE-I Phase 0.5C-L3 -- TIMING-SLACK SWEEP.
#
# WHY. L3b established the causal chain timing closure -> routing determinism
# -> implant visibility by a within-design manipulation: b15 at 125 MHz has a
# benign routing floor of 62 windows and buries a 74-window implant, and the
# same design at 50 MHz has a floor of 0 and shows the implant in 11. That is
# two points. The open question, recorded as a limit in every write-up, is
# WHERE THE THRESHOLD SITS and whether it is sharp or gradual.
#
# WHAT THIS DOES. One host, one implant, one region, one route-directive pair.
# The ONLY variable is the clock period. For each period it builds:
#     golden placed checkpoint -> benign Default -> benign Explore
#                              -> tied 8-cell implant
# and records worst negative slack. The analysis is local: the floor is the
# window difference between the two benign builds, the signal is the implant
# against benign Default, so the deliverable is the .bit files plus the timing
# reports.
#
# Every Vivado step is one already exercised by l3_eco_implant.tcl in the
# recorded L3/L3b campaigns; only the clock constraint changes between passes.
#
# USAGE (on meson):
#   ./l3_slack_sweep.sh <design> <post_synth_dcp> <base_xdc> [periods...]
# e.g.
#   ./l3_slack_sweep.sh b15-T200 \
#       $HOME/blade_pilot_phase05b/builds/b15-T200/TjFree/post_synth.dcp \
#       $HOME/blade_pilot_phase05b/sources/Constraints/PYNQ-Z1_AES.xdc \
#       8 10 12 14 16 20
#
# Periods are nanoseconds. b15's measured endpoints are 8.00 (fails, buried)
# and 20.00 (passes, visible), so the interesting range is between them.
#
# NOTE ON THE CLOCK OVERRIDE. The base XDC's own create_clock line is dropped
# and replaced, which is how the 125 -> 50 MHz comparison was produced. The
# script asserts the base XDC really contained a create_clock, and that the
# clock port name it uses appears in the file, rather than silently building
# something unconstrained.

set -eu

DESIGN="${1:?design tag, e.g. b15-T200}"
SYNTH_DCP="${2:?post-synthesis DCP}"
BASE_XDC="${3:?base XDC}"
shift 3
PERIODS=("${@:-8 12 16 20}")

SCRATCH="${SCRATCH:-$HOME/blade_pilot_phase05b}"
VIVADO_SETTINGS="${VIVADO_SETTINGS:-/share/reconfig/xilinx2/Vivado/2023.2/settings64.sh}"
OUT="$SCRATCH/l3_slack/$DESIGN"
TCL="$(cd "$(dirname "$0")" && pwd)/l3_eco_implant.tcl"

# The implant that every recorded L3 result uses: 8 tied flip-flops, region R2.
REGION="${REGION:-SLICE_X72Y11:SLICE_X79Y49}"
N_CELLS="${N_CELLS:-8}"

[ -f "$SYNTH_DCP" ] || { echo "no such DCP: $SYNTH_DCP" >&2; exit 1; }
[ -f "$BASE_XDC" ]  || { echo "no such XDC: $BASE_XDC" >&2; exit 1; }
[ -f "$TCL" ]       || { echo "no such tcl: $TCL" >&2; exit 1; }
grep -q "create_clock" "$BASE_XDC" || {
  echo "ERROR: $BASE_XDC has no create_clock line to override" >&2; exit 1; }

CLK_PORT="${CLK_PORT:-clk}"
CLK_NAME="${CLK_NAME:-sys_clk_pin}"
grep -q "get_ports.*$CLK_PORT" "$BASE_XDC" || {
  echo "ERROR: clock port '$CLK_PORT' not referenced in $BASE_XDC; set" \
       "CLK_PORT=<name>" >&2; exit 1; }

# shellcheck disable=SC1090
source "$VIVADO_SETTINGS" >/dev/null 2>&1 || true
command -v vivado >/dev/null || { echo "vivado not on PATH" >&2; exit 1; }

mkdir -p "$OUT"
echo "=== slack sweep: $DESIGN | region $REGION | $N_CELLS cells ==="
echo "=== periods: ${PERIODS[*]} ns ==="

for P in "${PERIODS[@]}"; do
  TAGP="p${P/./_}"
  D="$OUT/$TAGP"
  mkdir -p "$D"
  XDC="$D/clock_${TAGP}.xdc"
  grep -v "create_clock" "$BASE_XDC" > "$XDC"
  # Name the clock exactly as the DCP's existing one (sys_clk_pin in
  # PYNQ-Z1_AES.xdc) with no -add, so create_clock REPLACES the baked-in
  # constraint instead of stacking a second clock on the same port.
  echo "create_clock -period $P -name $CLK_NAME [get_ports $CLK_PORT]" >> "$XDC"

  echo
  echo "--- period ${P} ns -> $D"
  # Reconstrain the SAME post-synthesis netlist at this clock period BEFORE
  # placing. place_design is timing-driven, so the target clock must be in
  # force during placement, not applied afterward -- otherwise every period
  # shares one 125 MHz placement and the sweep measures nothing. This writes a
  # reconstrained synthesis checkpoint that the golden pass then places under
  # the new constraint.
  mkdir -p "$D/reports"
  vivado -mode batch -notrace -log "$D/reconstrain.log" \
         -journal "$D/reconstrain.jou" -source /dev/stdin <<TCLEOF 2>&1 | tail -3
open_checkpoint $SYNTH_DCP
read_xdc $XDC
report_timing_summary -file $D/reports/synth_timing.rpt
write_checkpoint -force $D/synth_reconstrained.dcp
TCLEOF
  if [ ! -f "$D/synth_reconstrained.dcp" ]; then
    echo "ERROR: reconstrain failed at period $P (see $D/reconstrain.log)" >&2
    continue
  fi
  # opt + place under the new constraint, stop before routing -> the shipped
  # placed checkpoint for this period. Timing summary here reflects the
  # placement's achievable slack.
  vivado -mode batch -notrace -source "$TCL" \
         -log "$D/golden.log" -journal "$D/golden.jou" \
         -tclargs golden "$D/synth_reconstrained.dcp" "$D" 2>&1 | tail -3
  vivado -mode batch -notrace -log "$D/goldtime.log" \
         -journal "$D/goldtime.jou" -source /dev/stdin <<TCLEOF 2>&1 | tail -3
open_checkpoint $D/golden_placed.dcp
report_timing_summary -file $D/reports/golden_timing.rpt
TCLEOF

  for DIR in Default Explore; do
    vivado -mode batch -notrace -source "$TCL" \
           -log "$D/B_$DIR.log" -journal "$D/B_$DIR.jou" \
           -tclargs benign "$D/golden_placed.dcp" "$D" "B_$DIR" "$DIR" \
           2>&1 | tail -3
  done

  vivado -mode batch -notrace -source "$TCL" \
         -log "$D/T_tied$N_CELLS.log" -journal "$D/T_tied$N_CELLS.jou" \
         -tclargs implant "$D/golden_placed.dcp" "$D" "T_tied$N_CELLS" \
         "$REGION" "$N_CELLS" Default tied 2>&1 | tail -3

  # WNS for the record: the sweep is only interpretable against measured slack.
  for R in "$D"/reports/*timing*.rpt; do
    [ -f "$R" ] && printf '%s WNS %s\n' "$(basename "$R")" \
      "$(grep -m1 -A2 'WNS' "$R" | tail -1 | awk '{print $1}')"
  done
done

echo
echo "=== DONE. bring back: $OUT ==="
echo "    tar czf l3_slack_$DESIGN.tgz -C $SCRATCH/l3_slack $DESIGN"
echo "    then locally: python3 l3_timing_threshold.py --sweep-dir <extracted>"
