# BLADE-I Phase 0.5C-L3 -- FUNCTIONAL TROJAN IMPLANT ON A PLACED CHECKPOINT.
#
# WHY THIS EXISTS. Every L3 implant so far is one of two things: `tied`, which
# observes nothing, or `tapped`, a dormant shift register that samples one host
# net and drives nothing. The recorded limit on every L3 claim is that the
# implant is SYNTHETIC -- "representative of logic added to a placed design,
# not a functional Trojan with a trigger and payload". This script closes that
# gap: a comparator TRIGGER over several host nets, an arming counter, and a
# PAYLOAD that modifies a real host signal when the trigger fires.
#
# STRUCTURE BUILT (all inside the shipped placed checkpoint, host placement
# untouched):
#
#   trigger   LUT6 over up to 6 tapped host nets, INIT chosen so it asserts on
#             ONE specific input combination -- a rare-pattern trigger, the
#             standard Trust-Hub trigger shape.
#   arming    N flip-flops in a chain, CE driven by the trigger: the payload
#             activates only after the pattern has been seen N times, so the
#             trojan is dormant during normal operation.
#   payload   a LUT2 XOR spliced into a host net: the victim load pin is
#             disconnected from its driver and re-driven by
#             XOR(original_driver, fire). While `fire` is 0 the host function
#             is bit-identical; when it is 1 the signal inverts.
#
# The payload is what makes this a trojan rather than an addition: it changes
# host behaviour, and it does so through a cell inserted into an existing
# routed path, which is the case no earlier build covered.
#
# GROUND TRUTH is constructive and written in the SAME format as
# l3_eco_implant.tcl (`IMPLANT <cell> <site>` lines plus a header), so
# l3_site_frame_map.py and l3_acceptance_bar.py consume it unchanged.
#
# HONEST STATUS: the Vivado ECO sequence here is modelled on the proven
# l3_eco_implant.tcl idioms, but net splicing (disconnect_net on a load pin,
# re-drive through an inserted LUT) is NOT exercised by any recorded build. It
# is written to fail LOUDLY at the first step that does not hold, and prints
# what it found, so one debug pass on meson is a realistic expectation.
#
# USAGE
#   vivado -mode batch -source l3_functional_trojan.tcl -tclargs \
#          <placed_dcp> <outdir> <tag> <slice_range> <n_arm_cells> [route_dir]
#
#   vivado -mode batch -source l3_functional_trojan.tcl -tclargs \
#          $D/golden_placed.dcp $D T_func8 SLICE_X72Y11:SLICE_X79Y49 8 Default

set in_dcp   [lindex $argv 0]
set outdir   [lindex $argv 1]
set tag      [lindex $argv 2]
set slice_rg [lindex $argv 3]
set n_arm    [lindex $argv 4]
set route_dir [lindex $argv 5]
if {$n_arm eq ""}     { set n_arm 8 }
if {$route_dir eq ""} { set route_dir "Default" }

file mkdir $outdir
file mkdir $outdir/reports

open_checkpoint $in_dcp
puts "=== FUNCTIONAL TROJAN: tag=$tag region=$slice_rg arm=$n_arm ==="

# ---------------------------------------------------------------- free sites
set region_sites [get_sites -quiet -filter "NAME =~ SLICE_*" -range $slice_rg]
set free {}
foreach s $region_sites {
    if {[llength [get_cells -quiet -of_objects [get_sites $s]]] == 0} {
        lappend free $s
    }
}
# trigger LUT + payload LUT + arming flip-flops.
set need [expr {$n_arm + 2}]
puts "=== region sites [llength $region_sites], free [llength $free], need $need ==="
if {[llength $free] < $need} {
    puts "ERROR: only [llength $free] free sites in $slice_rg, need $need"
    exit 1
}

# ---------------------------------------------------------------- host nets
set clk_net ""
set best 0
foreach n [get_nets -quiet -hier -filter {TYPE == GLOBAL_CLOCK}] {
    set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
    if {$l > $best} { set best $l ; set clk_net $n }
}
if {$clk_net eq ""} { puts "ERROR: no global clock net found" ; exit 1 }
set vcc [lindex [get_nets -quiet -hier -filter {TYPE == POWER}] 0]
set gnd [lindex [get_nets -quiet -hier -filter {TYPE == GROUND}] 0]
if {$vcc eq "" || $gnd eq ""} { puts "ERROR: no VCC/GND net" ; exit 1 }
puts "=== clock net: $clk_net ($best leaf pins) ==="

# Trigger inputs: modest-fanout signal nets, the same selection rule the
# tapped implant uses, so the trigger's observation cost is comparable to the
# tap survey rather than being dominated by a special net.
set trig_nets {}
foreach n [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
    set l [llength [get_pins -quiet -of_objects [get_nets $n] -leaf]]
    if {$l >= 2 && $l <= 8} {
        lappend trig_nets $n
        if {[llength $trig_nets] == 6} { break }
    }
}
if {[llength $trig_nets] < 2} {
    puts "ERROR: found only [llength $trig_nets] taggable host nets"
    exit 1
}
puts "=== trigger taps ([llength $trig_nets]): $trig_nets ==="

# ---------------------------------------------------------------- victim net
# The payload needs a host net with a load pin that can be re-driven. Take a
# single-load signal net that is NOT one of the trigger taps, so the trojan's
# observation and its effect are on different signals.
set victim ""
set victim_pin ""
foreach n [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
    if {[lsearch -exact $trig_nets $n] >= 0} { continue }
    set loads [get_pins -quiet -of_objects [get_nets $n] -leaf \
                        -filter {DIRECTION == IN}]
    if {[llength $loads] == 1} {
        set c [get_cells -quiet -of_objects [lindex $loads 0]]
        if {$c ne "" && [get_property -quiet IS_PRIMITIVE [get_cells $c]]} {
            set victim $n
            set victim_pin [lindex $loads 0]
            break
        }
    }
}
if {$victim eq ""} {
    puts "ERROR: no single-load host net available to splice a payload into"
    exit 1
}
puts "=== payload victim net: $victim -> pin $victim_pin ==="

set placed {}

# ---------------------------------------------------------------- trigger
# LUT6 asserting on exactly one input combination (all-ones): a rare-pattern
# trigger. INIT bit 63 set, all others clear.
set trig_cell "bladei_trig_${tag}"