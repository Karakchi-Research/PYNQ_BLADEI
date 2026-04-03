# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# March 29th, 2026
# Description: This script is a Vivado TCL script that performs a complete build process for a given Vivado project. 
#              It is designed to be called from the run_random.sh script, which sets up the environment and passes necessary arguments. 
#              The script opens the specified Vivado project, updates the source files based on the provided source directory.
#              It sets the top-level module, runs synthesis and implementation with specified directives, generates the bitstream and exits cleanly.
#
# Arguments; argv[0]: project_xpr (full path to Vivado project file)
#            argv[1]: src_dir (source directory with HDL files)
#            argv[2]: top_name (top-level module name)
#            argv[3]: place_directive (placement directive; default: "Default")
#            argv[4]: route_directive (routing directive; default: "Default")

# Parse arguments
set project_xpr     [lindex $argv 0]
set src_dir         [lindex $argv 1]
set top_name        [lindex $argv 2]
set place_directive [lindex $argv 3]
set route_directive [lindex $argv 4]

# Set default directives if not provided
if {$place_directive eq ""} {
    set place_directive "Default"
}
if {$route_directive eq ""} {
    set route_directive "Default"
}

# Normalize paths to absolute to avoid Vivado path caching issues
set bench_root [file normalize [file join $src_dir .. ..]]

puts "=== Opening project: $project_xpr ==="
open_project $project_xpr

set src_dir [file normalize $src_dir]
set bench_root [file normalize [file join $src_dir .. ..]]

puts "=== Variant source directory: $src_dir ==="
puts "=== Benchmark root directory: $bench_root ==="
puts "=== Place Directive: $place_directive ==="
puts "=== Route Directive: $route_directive ==="

# Remove existing HDL files from the project
set src_files [get_files -of_objects [get_filesets sources_1]]

foreach f $src_files {
    set ext [string tolower [file extension $f]]
    if {$ext eq ".v"  || $ext eq ".sv"  || $ext eq ".vh"  ||
        $ext eq ".vhd"|| $ext eq ".vhdl"} {
        puts "Removing design source: $f"
        remove_files $f
    }
}

# Add new HDL files from the source directory
set new_files [glob -nocomplain -directory $src_dir *.v *.sv *.vh *.vhd *.vhdl *.h]

if {[llength $new_files] == 0} {
    puts "ERROR: No HDL files found in: $src_dir"
    close_project
    exit 1
}

puts "=== Adding HDL files from: $src_dir ==="
set hdl_files [list]
foreach f $new_files {
    if {[string tolower [file extension $f]] ne ".h"} {
        lappend hdl_files $f
    }
}

if {[llength $hdl_files] > 0} {
    add_files $hdl_files
}

# Set include directories for the current fileset to ensure proper compilation
set_property include_dirs $src_dir [current_fileset]

# Set the top-level module for the current fileset
puts "=== Setting top-level to: $top_name ==="
set_property top $top_name [current_fileset]
update_compile_order -fileset sources_1

# Run synthesis
puts "=== Running synthesis ===" 
reset_run synth_1
launch_runs synth_1 -to_step synth_design
wait_on_run synth_1

# Configure implementation with specified directives
puts "=== Configuring implementation with Place=$place_directive, Route=$route_directive ===" 
reset_run impl_1

# Set place_design directive
set_property -name {STEPS.PLACE_DESIGN.ARGS.DIRECTIVE} -value $place_directive -objects [get_runs impl_1]

# Set route_design directive
set_property -name {STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE} -value $route_directive -objects [get_runs impl_1]

# Run implementation until bitstream generation
puts "=== Running implementation ==="
launch_runs impl_1 -to_step write_bitstream
wait_on_run impl_1

# Close the project and exit
puts "=== Build finished successfully ==="
close_project
exit
