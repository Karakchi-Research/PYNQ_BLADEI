# Phase 0.5B diagnostic: dump the full leaf-cell inventory of a checkpoint so
# benign and malicious netlists can be diffed by name and by primitive type.
# Used to explain WHY a matched pair differs when the design's named trojan
# logic did not survive synthesis.
#
#   vivado -mode batch -source dump_cells.tcl -tclargs <dcp> <outfile>

set dcp [lindex $argv 0]
set out [lindex $argv 1]

open_checkpoint $dcp

set f [open $out w]
foreach c [get_cells -hier -filter {IS_PRIMITIVE}] {
    puts $f "[get_property REF_NAME $c]\t$c"
}
close $f

set f [open "${out}.summary" w]
set counts [dict create]
foreach c [get_cells -hier -filter {IS_PRIMITIVE}] {
    set r [get_property REF_NAME $c]
    dict incr counts $r
}
foreach r [lsort [dict keys $counts]] {
    puts $f "[dict get $counts $r]\t$r"
}
close $f

puts "dumped [llength [get_cells -hier -filter {IS_PRIMITIVE}]] primitives -> $out"
exit 0
