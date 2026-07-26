# BLADE-I Phase 0.5C-L3s -- STEALTHY-TAP SURVEY.
#
# QUESTION. L3 measured that a functional implant tapping one host net expands
# the perturbed area from 6 windows (0.5% of device) to 379 (30.3%) -- a ~60x
# expansion caused not by the implant's own configuration bits but by the
# router's global response to the added load. That result used ONE arbitrarily
# chosen net (a1_n_0, the first net matching a fanout filter).
#
# The adversarial question a reviewer will ask: can an attacker CHOOSE a tap
# that stays quiet? If low-perturbation taps exist and are identifiable, the
# 30% figure is optimistic and the defence is weaker than L3 suggests. If
# every tap perturbs broadly, the defence is robust to tap selection.
#
# Mode `survey` dumps candidate host nets with the properties an attacker
# could plausibly use to choose one: fanout, driver cell type, and timing
# slack. Mode `implant` in l3_eco_implant.tcl then taps a NAMED net so the
# footprint can be measured per net.
#
#   vivado -mode batch -source l3_tap_survey.tcl -tclargs <placed_dcp> <outfile>

set in_dcp  [lindex $argv 0]
set outfile [lindex $argv 1]

open_checkpoint $in_dcp

# Slack needs a timing view; the golden checkpoint is placed but unrouted, so
# estimates are pre-route. That is exactly what an attacker editing the same
# checkpoint would see, so it is the right basis for this question.
set have_timing 1
if {[catch {report_timing_summary -quiet -no_header -file /dev/null} e]} {
    puts "WARNING: timing summary unavailable ($e); slack column will be n/a"
    set have_timing 0
}

set fh [open $outfile w]
puts $fh "net\tfanout\tdriver_ref\tdriver_loc\tslack_ns"

set n 0
foreach net [get_nets -quiet -hier -filter {TYPE == SIGNAL}] {
    set pins [get_pins -quiet -of_objects [get_nets $net] -leaf]
    set fo [llength $pins]
    if {$fo < 1} { continue }
    # Driver: the output pin on this net.
    set drv ""
    foreach p $pins {
        if {[get_property DIRECTION [get_pins $p]] eq "OUT"} { set drv $p ; break }
    }
    set dref "" ; set dloc ""
    if {$drv ne ""} {
        set dcell [get_cells -quiet -of_objects [get_pins $drv]]
        if {$dcell ne ""} {
            set dref [get_property REF_NAME [get_cells $dcell]]
            set dloc [get_property LOC [get_cells $dcell]]
        }
    }
    set slack "n/a"
    if {$have_timing} {
        set t [get_timing_paths -quiet -through [get_nets $net] -max_paths 1 \
                   -nworst 1 -delay_type max]
        if {[llength $t] > 0} {
            set s [get_property SLACK [lindex $t 0]]
            if {$s ne ""} { set slack $s }
        }
    }
    puts $fh "$net\t$fo\t$dref\t$dloc\t$slack"
    incr n
    if {$n >= 4000} { break }
}
close $fh
puts "=== SURVEYED $n nets -> $outfile ==="
exit 0
