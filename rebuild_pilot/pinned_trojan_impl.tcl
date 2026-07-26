# BLADE-I Phase 0.5C-L2 -- PINNED-TROJAN implementation stage.
#
# Purpose: produce localization ground truth that covers the trojan's FULL
# footprint (LUT configuration and routing included), which the .ll-derived
# labels of stage L1 cannot -- a .ll enumerates memory cells only.
#
# Method: re-open the MALICIOUS post-synthesis DCP, confine every trojan cell
# to a pblock at a KNOWN, caller-chosen device region with CONTAIN_ROUTING,
# then implement. Repeating with the pblock at several disjoint regions yields
# builds whose trojan sits in a different, known place each time, which both
# supplies positive labels and defeats "the model memorised one location".
#
# Every option used here must appear verbatim in the installed Vivado 2023.2
# help captured under rebuild_pilot/vivado_env_capture/. place_design -seed is
# NOT used: this release does not document it.
#
#   vivado -mode batch -source pinned_trojan_impl.tcl -tclargs \
#          <design> <dcp> <tag> <slice_range> <place_dir> <route_dir> \
#          <outdir> <trojan_pattern_file>
#
#   slice_range example: SLICE_X20Y50:SLICE_X29Y99
#
# The build FAILS LOUDLY if the trojan cell set is empty or if any trojan cell
# escapes the pblock -- a silently unpinned trojan would be false ground truth.

set design   [lindex $argv 0]
set dcp      [lindex $argv 1]
set tag      [lindex $argv 2]
set slice_rg [lindex $argv 3]
set place_dir [lindex $argv 4]
set route_dir [lindex $argv 5]
set outdir   [lindex $argv 6]
set patfile  [lindex $argv 7]

file mkdir $outdir
file mkdir $outdir/reports

puts "=== PINNED IMPL: design=$design tag=$tag region=$slice_rg ==="
open_checkpoint $dcp

# --- collect trojan cells from the documented discriminative patterns -------
set pats {}
set fh [open $patfile r]
while {[gets $fh line] >= 0} {
    set line [string trim $line]
    if {$line ne "" && [string index $line 0] ne "#"} { lappend pats $line }
}
close $fh

set tro_cells {}
foreach p $pats {
    foreach c [get_cells -hier -quiet -filter "NAME =~ $p && IS_PRIMITIVE"] {
        if {[lsearch -exact $tro_cells $c] < 0} { lappend tro_cells $c }
    }
}
puts "=== trojan primitive cells matched: [llength $tro_cells] ==="
if {[llength $tro_cells] == 0} {
    puts "ERROR: no trojan cells matched $pats -- refusing to build false ground truth"
    exit 1
}

# Record the exact cell list; it is the ground-truth cell set.
set fh [open $outdir/reports/${tag}_trojan_cells.txt w]
foreach c $tro_cells { puts $fh $c }
close $fh

# --- pin them ---------------------------------------------------------------
create_pblock pblock_trojan
add_cells_to_pblock pblock_trojan $tro_cells
resize_pblock pblock_trojan -add $slice_rg
set_property CONTAIN_ROUTING true [get_pblocks pblock_trojan]
set_property EXCLUDE_PLACEMENT true [get_pblocks pblock_trojan]

opt_design
place_design -directive $place_dir
route_design -directive $route_dir

# --- verify the pin actually held ------------------------------------------
set escaped {}
foreach c $tro_cells {
    set site [get_property SITE [get_cells $c]]
    if {$site eq ""} { continue }
    if {[lsearch -exact [get_sites -quiet -of_objects [get_pblocks pblock_trojan]] $site] < 0} {
        lappend escaped "$c@$site"
    }
}
set fh [open $outdir/reports/${tag}_pin_verification.txt w]
puts $fh "region: $slice_rg"
puts $fh "trojan_cells: [llength $tro_cells]"
puts $fh "escaped: [llength $escaped]"
foreach e $escaped { puts $fh $e }
close $fh
if {[llength $escaped] > 0} {
    puts "ERROR: [llength $escaped] trojan cell(s) placed OUTSIDE the pblock"
    puts "       ground truth would be wrong; see ${tag}_pin_verification.txt"
    exit 1
}
puts "=== pin verified: all [llength $tro_cells] trojan cells inside $slice_rg ==="

report_utilization      -file $outdir/reports/${tag}_utilization.rpt
report_timing_summary   -file $outdir/reports/${tag}_timing.rpt
report_route_status     -file $outdir/reports/${tag}_route_status.rpt
write_checkpoint -force $outdir/${tag}_routed.dcp

# -logic_location_file is documented by this release and gives the independent
# .ll cross-check against the L1 labels.
write_bitstream -force -logic_location_file $outdir/${tag}.bit

puts "=== PINNED IMPL DONE: $tag ==="
exit 0
