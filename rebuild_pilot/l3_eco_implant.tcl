# BLADE-I Phase 0.5C-L3 -- ATTACK ON A PLACED CHECKPOINT.
#
# THREAT MODEL (chosen 2026-07-25). The defender implements their design to a
# PLACED checkpoint and hands it on; the returned bitstream is verified against
# builds the defender makes from that same checkpoint. An attacker who modifies
# the placed design must therefore leave the host placement intact, because
# they are editing an already-placed netlist rather than re-running placement.
#
# WHY THIS MODEL. L2f measured that independent place-and-route churn moves
# 4,588 of 10,008 frames (46% of the device) while shared-lineage builds move
# 1,100. A trojan occupying one or two frames cannot be seen against the first
# number. L2p showed that adding more INDEPENDENTLY PLACED benign references
# does not help -- the operative property is a shared placement ancestor, not
# population size. This flow supplies that property by construction.
#
# The task is FORENSIC LOCALIZATION: something is already suspected, and the
# question is where in the configuration the added logic sits.
#
# Modes:
#   golden   opt + place the benign netlist, stop BEFORE routing, and write
#            golden_placed.dcp -- the checkpoint the defender ships.
#   benign   route golden_placed under one route directive -> one member of
#            the legitimate-rebuild population (same placement, routing varies).
#   implant  open golden_placed, ECO-insert flip-flops at CHOSEN, RECORDED
#            sites in a target region, route ONLY the new nets so host routing
#            is disturbed as little as possible, and emit the bitstream + .ll.
#
# Ground truth is exact and constructive: this script chooses the implant
# sites, so the answer is known before the bitstream exists -- no inference
# from pblocks (which L2 showed only partially contain a trojan) and no
# reliance on name patterns.
#
# Every command is from the installed Vivado 2023.2; no place_design -seed.
#
#   vivado -mode batch -source l3_eco_implant.tcl -tclargs golden  <synth_dcp> <outdir>
#   vivado -mode batch -source l3_eco_implant.tcl -tclargs benign  <placed_dcp> <outdir> <tag> <route_dir>
#   vivado -mode batch -source l3_eco_implant.tcl -tclargs implant <placed_dcp> <outdir> <tag> <slice_range> <n_cells>

set mode   [lindex $argv 0]
set in_dcp [lindex $argv 1]
set outdir [lindex $argv 2]

file mkdir $outdir
file mkdir $outdir/reports

if {$mode eq "golden"} {
    open_checkpoint $in_dcp
    opt_design
    place_design -directive Default
    write_checkpoint -force $outdir/golden_placed.dcp
    report_utilization -file $outdir/reports/golden_utilization.rpt
    puts "=== GOLDEN PLACED CHECKPOINT WRITTEN ==="
    exit 0
}

set tag [lindex $argv 3]

if {$mode eq "benign"} {
    set route_dir [lindex $argv 4]
    open_checkpoint $in_dcp
    route_design -directive $route_dir
    report_route_status -file $outdir/reports/${tag}_route_status.rpt
    write_bitstream -force -logic_location_file $outdir/${tag}.bit
    puts "=== BENIGN POPULATION MEMBER DONE: $tag ($route_dir) ==="
    exit 0
}

# ---------------- implant mode ----------------
set slice_rg [lindex $argv 4]
set n_cells  [lindex $argv 5]
if {$n_cells eq ""} { set n_cells 8 }

open_checkpoint $in_dcp
puts "=== IMPLANT: tag=$tag region=$slice_rg cells=$n_cells ==="

# Free SLICEs in the target region: sites with no placed cell.
set region_sites [get_sites -quiet -filter "NAME =~ SLICE_*" -range $slice_rg]
set free {}
foreach s $region_sites {
    if {[llength [get_cells -quiet -of_objects [get_sites $s]]] == 0} {
        lappend free $s
    }
}
puts "=== region sites [llength $region_sites], free [llength $free] ==="
if {[llength $free] < $n_cells} {
    puts "ERROR: only [llength $free] free sites in $slice_rg, need $n_cells"
    exit 1
}

# Clock net to drive the implanted flip-flops. Take the net with the most
# loads on a global buffer -- the design's real clock.
set clk_net ""
set best 0
foreach n [get_nets -quiet -hier -filter {TYPE == GLOBAL_CLOCK}] {
    set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
    if {$l > $best} { set best $l ; set clk_net $n }
}
if {$clk_net eq ""} {
    puts "ERROR: no global clock net found; cannot build a realistic implant"
    exit 1
}
puts "=== clock net: $clk_net ($best leaf pins) ==="

set vcc [get_nets -quiet -hier -filter {TYPE == POWER}]
set gnd [get_nets -quiet -hier -filter {TYPE == GROUND}]
if {[llength $vcc] == 0 || [llength $gnd] == 0} {
    puts "ERROR: no VCC/GND net available"
    exit 1
}
set vcc [lindex $vcc 0] ; set gnd [lindex $gnd 0]

# Implant style:
#   tied   -- D/CE tied to VCC, R to GND. Minimal, purely additive: it changes
#             configuration and adds routing but observes nothing.
#   tapped -- a DORMANT SHIFT REGISTER: the first flip-flop samples a real host
#             net, each subsequent one takes the previous Q. The final Q is
#             left unconnected (no payload). This is the structure a Trust-Hub
#             trojan has before its trigger fires, and unlike `tied` it adds a
#             load to a real host net, so the routing perturbation is realistic
#             rather than purely local.
set style [lindex $argv 7]
if {$style eq ""} { set style "tied" }
puts "=== implant style: $style ==="

# An explicit tap net (argv 8) lets the STEALTHY-TAP survey hold everything
# else fixed and vary only which host net is observed, so the perturbation can
# be attributed to the net's properties (fanout, slack, driver type) rather
# than to an arbitrary auto-selection.
set tap_net ""
set tap_req [lindex $argv 8]
if {$style eq "tapped" && $tap_req ne ""} {
    set tap_net [get_nets -quiet -hier $tap_req]
    if {[llength $tap_net] == 0} {
        puts "ERROR: requested tap net '$tap_req' not found"
        exit 1
    }
    set tap_net [lindex $tap_net 0]
    puts "=== tapping REQUESTED host net: $tap_net ==="
} elseif {$style eq "tapped"} {
    # A signal net with modest fanout: representative of something a trojan
    # would observe, without being a global/high-fanout special net.
    # NOTE: do NOT filter on ROUTE_STATUS here -- the golden checkpoint is
    # PLACED but UNROUTED, so no net reports ROUTED and the search finds
    # nothing (the first attempt failed exactly this way).
    foreach n [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
        set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
        if {$l >= 2 && $l <= 8} { set tap_net $n ; break }
    }
    if {$tap_net eq ""} {
        puts "ERROR: no suitable host net to tap; cannot build a tapped implant"
        exit 1
    }
    puts "=== tapping host net: $tap_net ==="
}

# FFs are used deliberately: when their Q is connected they appear in the .ll
# logic-location file, giving an INDEPENDENT confirmation of where the implant
# landed on top of this script's own record.
set placed {}
set prev_q ""
for {set i 0} {$i < $n_cells} {incr i} {
    set site [lindex $free $i]
    set cell "bladei_implant_${tag}_$i"
    create_cell -reference FDRE $cell
    set_property INIT 1'b0 [get_cells $cell]
    place_cell $cell ${site}/AFF
    connect_net -hier -net $clk_net -objects [get_pins $cell/C]
    connect_net -hier -net $vcc     -objects [get_pins $cell/CE]
    connect_net -hier -net $gnd     -objects [get_pins $cell/R]
    if {$style eq "tapped"} {
        if {$i == 0} {
            connect_net -hier -net $tap_net -objects [get_pins $cell/D]
        } else {
            set qn "bladei_implant_${tag}_q$i"
            create_net $qn
            connect_net -hier -net $qn -objects [get_pins $prev_q/Q]
            connect_net -hier -net $qn -objects [get_pins $cell/D]
        }
        set prev_q $cell
    } else {
        connect_net -hier -net $vcc -objects [get_pins $cell/D]
    }
    lappend placed "$cell $site"
}
puts "=== implanted [llength $placed] flip-flops (style=$style) ==="

# Route the whole design, exactly as an attacker starting from the shipped
# PLACED checkpoint would have to. (Routing only the implant nets was tried
# first and is wrong here: the golden checkpoint is placed but NOT routed, so
# a subset route leaves the host unrouted and write_bitstream fails with
# "[DRC RTSTAT-13] Insufficient Routing".)
#
# Placement provenance is still shared by construction -- every legitimate
# build and this attacked build descend from the same golden_placed.dcp, so
# host PLACEMENT is identical and only routing varies, which is precisely the
# low-churn condition L2f identified as the enabling property.
set route_dir [lindex $argv 6]
if {$route_dir eq ""} { set route_dir "Default" }
puts "=== routing full design, directive $route_dir ==="
route_design -directive $route_dir

set fh [open $outdir/reports/${tag}_implant_truth.txt w]
puts $fh "tag: $tag"
puts $fh "region: $slice_rg"
puts $fh "n_cells: [llength $placed]"
puts $fh "clock_net: $clk_net"
puts $fh "style: $style"
puts $fh "tap_net: $tap_net"
foreach p $placed { puts $fh "IMPLANT $p" }
close $fh

report_route_status -file $outdir/reports/${tag}_route_status.rpt
report_utilization  -file $outdir/reports/${tag}_utilization.rpt
write_checkpoint -force $outdir/${tag}_routed.dcp
write_bitstream -force -logic_location_file $outdir/${tag}.bit
puts "=== IMPLANT DONE: $tag ==="
exit 0
