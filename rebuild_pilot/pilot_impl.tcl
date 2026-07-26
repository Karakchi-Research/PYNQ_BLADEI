# BLADE-I Phase 0.5B rebuild pilot -- implementation stage.
# Re-opens the label's single post-synthesis DCP and runs one implementation
# configuration. Every option used here appears verbatim in the installed
# Vivado 2023.2 help captured in rebuild_pilot/vivado_env_capture/.
# In particular place_design -seed is NOT used: it is not documented by this
# release's `help place_design`.
#
#   vivado -mode batch -source pilot_impl.tcl -tclargs \
#          <design> <label> <dcp> <cfg> <place_dir> <route_dir> <phys_opt_dir> \
#          <outdir> <trojan_pattern_file>
#
# phys_opt_dir = NONE skips phys_opt_design entirely.

set design    [lindex $argv 0]
set label     [lindex $argv 1]
set dcp       [lindex $argv 2]
set cfg       [lindex $argv 3]
set place_dir [lindex $argv 4]
set route_dir [lindex $argv 5]
set phys_dir  [lindex $argv 6]
set outdir    [lindex $argv 7]
set patfile   [lindex $argv 8]

file mkdir $outdir
file mkdir $outdir/reports

puts "=== PILOT IMPL: design=$design label=$label cfg=$cfg ==="
puts "=== place=$place_dir route=$route_dir phys_opt=$phys_dir ==="

open_checkpoint $dcp

opt_design
place_design -directive $place_dir
report_utilization -file $outdir/reports/post_place_utilization.rpt

if {$phys_dir ne "NONE"} {
    phys_opt_design -directive $phys_dir
}

route_design -directive $route_dir

write_checkpoint -force $outdir/post_route.dcp
report_timing_summary -file $outdir/reports/post_route_timing.rpt
report_utilization    -file $outdir/reports/post_route_utilization.rpt
report_route_status   -file $outdir/reports/post_route_status.rpt

# --------------------------------------------------- trojan retention (route)
set patterns [list]
if {[file exists $patfile]} {
    set f [open $patfile r]
    foreach line [split [read $f] "\n"] {
        set line [string trim $line]
        if {$line ne "" && ![string match "#*" $line]} { lappend patterns $line }
    }
    close $f
}
if {[llength $patterns] == 0} {
    puts "ERROR: no trojan patterns loaded from '$patfile' -- refusing to record"
    puts "       an empty retention result that would read as 'trojan absent'."
    exit 1
}

set rf [open $outdir/reports/trojan_post_route.txt w]
puts $rf "design=$design label=$label cfg=$cfg stage=post_route"
puts $rf "pattern_file=$patfile"
puts $rf "total_cells=[llength [get_cells -hier]]"
puts $rf "total_nets=[llength [get_nets -hier]]"
foreach pat $patterns {
    set cells [get_cells -hier -quiet -filter "NAME =~ \"$pat\""]
    set nets  [get_nets  -hier -quiet -filter "NAME =~ \"$pat\""]
    puts $rf "PATTERN $pat cells=[llength $cells] nets=[llength $nets]"
    foreach c $cells {
        set loc ""
        catch { set loc [get_property LOC $c] }
        puts $rf "  CELL $c [get_property REF_NAME $c] LOC=$loc"
    }
    foreach n $nets { puts $rf "  NET  $n" }
}
close $rf

# ---------------------------------------------------------------- bitstream
# -logic_location_file is documented by this release's help write_bitstream.
write_bitstream -force -logic_location_file [file join $outdir "${design}_${label}_${cfg}.bit"]

puts "=== PILOT IMPL DONE: $design/$label/$cfg ==="
exit 0
