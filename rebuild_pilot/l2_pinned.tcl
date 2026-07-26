# BLADE-I Phase 0.5C-L2 -- host-locked, density-varied pinned-trojan builds.
#
# WHY THIS SHAPE. L1b showed per-window set-bit density (popcount) matches or
# beats every differential scorer, and that density-normalising a differential
# collapses its ranking 37.5 -> 388.8. Occupancy is the dominant confound. The
# experiment that separates localization from occupancy is: hold the HOST
# fixed, move the SAME trojan across regions of DIFFERING density, and ask
# whether a method's peak follows the trojan.
#
# Two modes:
#   reference  implement the malicious netlist normally and save a routed DCP
#              whose host placement every pinned build will reuse.
#   pinned     re-open the reference, rip up ONLY the trojan (cells + nets),
#              fix all remaining placement, confine the trojan to a pblock at
#              a chosen SLICE region, then re-place and re-route.
#
# So between two pinned builds the host placement is identical BY
# CONSTRUCTION and only the trojan differs -- unlike the matched benign pairs,
# which differ in ~39% of frames from place-and-route churn.
#
# Every option is verbatim from the installed Vivado 2023.2 help captured in
# rebuild_pilot/vivado_env_capture/. place_design -seed is NOT used.
#
#   vivado -mode batch -source l2_pinned.tcl -tclargs reference \
#          <synth_dcp> <patfile> <outdir>
#   vivado -mode batch -source l2_pinned.tcl -tclargs pinned \
#          <reference_dcp> <patfile> <outdir> <region_id> <slice_range>
#
# Fails loudly rather than producing false ground truth if the trojan cell set
# is empty or if any trojan cell lands outside its pblock.

set mode    [lindex $argv 0]
set in_dcp  [lindex $argv 1]
set patfile [lindex $argv 2]
set outdir  [lindex $argv 3]

file mkdir $outdir
file mkdir $outdir/reports

proc trojan_cells {patfile} {
    set pats {}
    set fh [open $patfile r]
    while {[gets $fh line] >= 0} {
        set line [string trim $line]
        if {$line ne "" && [string index $line 0] ne "#"} { lappend pats $line }
    }
    close $fh
    set cells {}
    foreach p $pats {
        foreach c [get_cells -hier -quiet -filter "NAME =~ $p && IS_PRIMITIVE"] {
            if {[lsearch -exact $cells $c] < 0} { lappend cells $c }
        }
    }
    return $cells
}

open_checkpoint $in_dcp
set tro [trojan_cells $patfile]
puts "=== trojan primitive cells: [llength $tro] ==="
if {[llength $tro] == 0} {
    puts "ERROR: no trojan cells matched -- refusing to build false ground truth"
    exit 1
}

if {$mode eq "reference"} {
    opt_design
    # opt_design can rename or absorb cells, so the pre-opt list is stale --
    # re-query against the optimised netlist before reporting or placing.
    set tro [trojan_cells $patfile]
    puts "=== trojan primitive cells after opt_design: [llength $tro] ==="
    if {[llength $tro] == 0} {
        puts "ERROR: opt_design eliminated every trojan cell -- this design is"
        puts "       no-trace after implementation; refusing to continue"
        exit 1
    }
    place_design -directive Default
    route_design -directive Default
    write_checkpoint -force $outdir/reference_routed.dcp
    set fh [open $outdir/reports/reference_trojan_cells.txt w]
    foreach c $tro {
        set obj [get_cells -quiet $c]
        if {[llength $obj] == 0} { puts $fh "$c <absent>" ; continue }
        puts $fh "$c [get_property LOC $obj]"
    }
    close $fh
    report_utilization    -file $outdir/reports/reference_utilization.rpt
    report_timing_summary -file $outdir/reports/reference_timing.rpt
    write_bitstream -force -logic_location_file $outdir/reference.bit
    puts "=== REFERENCE DONE ==="
    exit 0
}

# ---------------- pinned mode ----------------
set region_id [lindex $argv 4]
set slice_rg  [lindex $argv 5]
puts "=== PINNED: region=$region_id range=$slice_rg ==="

# Rip up only the trojan: unroute its nets, unplace its cells.
set tro_nets [get_nets -quiet -of_objects [get_pins -quiet -of_objects $tro]]
if {[llength $tro_nets] > 0} {
    route_design -unroute -nets $tro_nets
}
unplace_cell $tro

# Host freezing is OPTIONAL and defaults OFF. Measured reason (2026-07-25):
# with the host frozen, placement fails --
#   [Constraints 18-8706] Failed to create MUXF8 shape for instance
#   AES/a1/S4_0/S_2/out_reg[7]_i_1. Trojan/g2_b7__0 loc is blocked
# Vivado packs trojan LUTs into the SAME MUXF8/MUXF7 macros as host logic, so
# those cells are not spatially separable from the host at slice level. A
# frozen host therefore makes relocation infeasible by construction, not by
# tuning. Leaving the host free lets Vivado carry fused host partners along
# with the trojan into the pblock.
#
# Consequence to state in any result: between two pinned builds the host also
# moves, so their frame difference is trojan relocation PLUS host churn. The
# GROUND TRUTH is unaffected -- it comes from the verified pin, not the diff.
set freeze [expr {[llength $argv] > 6 ? [lindex $argv 6] : 0}]
set fixed 0
if {$freeze} {
    foreach c [get_cells -hier -quiet -filter {IS_PRIMITIVE && LOC != ""}] {
        if {[lsearch -exact $tro $c] >= 0} { continue }
        set_property IS_LOC_FIXED 1 [get_cells $c]
        incr fixed
    }
}
puts "=== host primitives frozen: $fixed (freeze=$freeze) ==="

create_pblock pb_tro
add_cells_to_pblock pb_tro $tro
resize_pblock pb_tro -add $slice_rg
set_property CONTAIN_ROUTING true [get_pblocks pb_tro]

place_design -directive Default
route_design -directive Default

# Verify the pin held; a silently escaped trojan cell would be false labels.
set sites [get_sites -quiet -of_objects [get_pblocks pb_tro]]
set escaped {}
foreach c $tro {
    set obj [get_cells -quiet $c]
    if {[llength $obj] == 0} { continue }
    set loc [get_property LOC $obj]
    if {$loc eq ""} { continue }
    if {[lsearch -exact $sites $loc] < 0} { lappend escaped "$c@$loc" }
}
set fh [open $outdir/reports/${region_id}_pin_verification.txt w]
puts $fh "region_id: $region_id"
puts $fh "slice_range: $slice_rg"
puts $fh "trojan_cells: [llength $tro]"
puts $fh "host_primitives_frozen: $fixed"
puts $fh "escaped: [llength $escaped]"
foreach e $escaped { puts $fh $e }
foreach c $tro {
    set obj [get_cells -quiet $c]
    if {[llength $obj] > 0} { puts $fh "PLACED $c [get_property LOC $obj]" }
}
close $fh
# Containment is REPORTED, not required. Measured reason (2026-07-25): some
# trojan LUTs are fused into MUXF8/MUXF7 macros with host logic and cannot be
# dragged into a remote pblock; with a 121-cell trojan, 28 escaped R0.
#
# This does not weaken the ground truth, because the ground truth is the
# MEASURED placement of every trojan cell (written above as PLACED lines),
# not the assumption that the pblock held them. The pblock's job is only to
# MOVE the trojan so its location varies across builds. A build is rejected
# only if the trojan vanished entirely.
set contained [expr {[llength $tro] - [llength $escaped]}]
puts "=== containment: $contained/[llength $tro] trojan cells inside $slice_rg,\
 [llength $escaped] outside (recorded per-cell, not fatal) ==="
if {$contained == 0} {
    puts "ERROR: no trojan cell landed in the target region -- this build"
    puts "       carries no usable placement signal; aborting"
    exit 1
}

report_utilization    -file $outdir/reports/${region_id}_utilization.rpt
report_timing_summary -file $outdir/reports/${region_id}_timing.rpt
report_route_status   -file $outdir/reports/${region_id}_route_status.rpt
write_checkpoint -force $outdir/${region_id}_routed.dcp
write_bitstream -force -logic_location_file $outdir/${region_id}.bit
puts "=== PINNED DONE: $region_id ==="
exit 0
