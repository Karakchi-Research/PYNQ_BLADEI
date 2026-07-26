# BLADE-I Phase 0.5B rebuild pilot -- synthesis stage.
# One synthesis per design/label. Writes a post-synthesis DCP that every
# implementation variant re-opens, so the matrix isolates P&R variation from
# synthesis variation.
#
#   vivado -mode batch -source pilot_synth.tcl -tclargs \
#          <design> <label> <src_dir> <top> <xdc> <ip_dir> <coe_dir> <outdir> \
#          <trojan_pattern_file>
#
# Options used here are limited to those documented by the installed
# Vivado 2023.2 (see rebuild_pilot/vivado_env_capture/).

set design  [lindex $argv 0]
set label   [lindex $argv 1]
set src_dir [lindex $argv 2]
set top     [lindex $argv 3]
set xdc     [lindex $argv 4]
set ip_dir  [lindex $argv 5]
set coe_dir [lindex $argv 6]
set outdir  [lindex $argv 7]
set patfile [lindex $argv 8]

set part "xc7z020clg400-1"

file mkdir $outdir
file mkdir $outdir/reports

puts "=== PILOT SYNTH: design=$design label=$label top=$top part=$part ==="
puts "=== src_dir=$src_dir xdc=$xdc ==="

# ---------------------------------------------------------------- IP (AES only)
# The AES host design instantiates three block/distributed memories. The .coe
# initialisation files live with the benchmark, so benign and malicious builds
# consume byte-identical memory contents.
set ip_dcps [list]
if {$ip_dir ne "NONE"} {
    # An in-memory project is required before read_ip: without it Vivado
    # reports the .xci as "locked" and generate_target/synth_ip produce
    # nothing, which is what failed the first AES attempt.
    create_project -in_memory -part $part

    set ip_scratch $outdir/ip
    file mkdir $ip_scratch
    foreach ipname {key_memory state_memory out_memory} {
        set srcxci $ip_dir/$ipname/$ipname.xci
        if {![file exists $srcxci]} { continue }
        file mkdir $ip_scratch/$ipname
        set dstxci $ip_scratch/$ipname/$ipname.xci
        file copy -force $srcxci $dstxci

        # Repoint the coefficient file at this benchmark's .coe (the shipped
        # .xci carries an absolute Windows path from the original author).
        set coe ""
        if {$ipname eq "key_memory"}   { set coe [file normalize $coe_dir/key_memory.coe] }
        if {$ipname eq "state_memory"} { set coe [file normalize $coe_dir/state_memory.coe] }
        if {$coe ne "" && [file exists $coe]} {
            set f [open $dstxci r]; set content [read $f]; close $f
            regsub -all {(\"value\":\s*\")[^\"]*\.coe\"} $content "\\1${coe}\"" content
            set f [open $dstxci w]; puts -nonewline $f $content; close $f
            puts "=== IP $ipname: coefficient file -> $coe ==="
        }
        read_ip $dstxci
    }
    if {[llength [get_ips]] > 0} {
        generate_target all [get_ips]
        synth_ip [get_ips]
        foreach ip [get_ips] {
            set d ""
            catch { set d [get_property IP_OUTPUT_DCP [get_ips $ip]] }
            if {$d ne ""} { lappend ip_dcps $d }
        }
        puts "=== IP synthesised: [llength [get_ips]] core(s), \
[llength $ip_dcps] checkpoint(s) ==="
    }
}

# ------------------------------------------------------------------- RTL + XDC
set hdl [lsort [glob -nocomplain -directory $src_dir *.v *.sv *.vh *.vhd *.vhdl]]
if {[llength $hdl] == 0} {
    puts "ERROR: no HDL sources in $src_dir"
    exit 1
}
foreach f $hdl {
    set ext [string tolower [file extension $f]]
    if {$ext eq ".vhd" || $ext eq ".vhdl"} {
        read_vhdl $f
    } else {
        read_verilog $f
    }
    puts "=== source: [file tail $f] ==="
}
read_xdc $xdc

# ------------------------------------------------------------------- synthesis
synth_design -top $top -part $part -include_dirs $src_dir

write_checkpoint -force $outdir/post_synth.dcp
report_utilization -file $outdir/reports/post_synth_utilization.rpt
report_timing_summary -file $outdir/reports/post_synth_timing.rpt

# --------------------------------------------------- trojan retention (synth)
# Patterns are supplied per design by the driver; cells and nets are enumerated
# and written verbatim. Nothing is forced to survive: if synthesis stripped the
# trojan, that is recorded as the finding.
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

set rf [open $outdir/reports/trojan_post_synth.txt w]
puts $rf "design=$design label=$label stage=post_synth"
puts $rf "pattern_file=$patfile"
puts $rf "total_cells=[llength [get_cells -hier]]"
puts $rf "total_nets=[llength [get_nets -hier]]"
foreach pat $patterns {
    set cells [get_cells -hier -quiet -filter "NAME =~ \"$pat\""]
    set nets  [get_nets  -hier -quiet -filter "NAME =~ \"$pat\""]
    puts $rf "PATTERN $pat cells=[llength $cells] nets=[llength $nets]"
    foreach c $cells { puts $rf "  CELL $c [get_property REF_NAME $c]" }
    foreach n $nets  { puts $rf "  NET  $n" }
}
close $rf

puts "=== PILOT SYNTH DONE: $design/$label ==="
exit 0
