# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5B environment capture -- run ONCE in the exact
#              installed Vivado shell on the build host BEFORE any pilot
#              build:
#                vivado -mode batch -source capture_vivado_env.tcl
#              Writes vivado_env_capture/ with version, help texts, and
#              strategy lists. The pilot implementation matrix may only use
#              options that appear VERBATIM in these captures (in particular:
#              do NOT use place_design -seed unless `help place_design` here
#              documents it). Read-only: opens no project, modifies nothing.

set outdir "vivado_env_capture"
file mkdir $outdir

proc capture {name script} {
    global outdir
    set f [open [file join $outdir $name] w]
    if {[catch {uplevel 1 $script} result]} {
        puts $f "CAPTURE ERROR: $result"
    } else {
        puts $f $result
    }
    close $f
    puts "captured -> $outdir/$name"
}

capture version.txt          {version}
capture help_place_design.txt    {help place_design}
capture help_route_design.txt    {help route_design}
capture help_phys_opt_design.txt {help phys_opt_design}
capture help_write_bitstream.txt {help write_bitstream}

# Directive lists as the installed release documents them.
capture place_directives.txt {
    join [list_property_value -class run \
        STEPS.PLACE_DESIGN.ARGS.DIRECTIVE] "\n"
}
capture route_directives.txt {
    join [list_property_value -class run \
        STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE] "\n"
}

# Note for the operator: after opening the existing BLADE-I project on the
# build host, additionally run and save:
#   report_property -all [get_runs impl_1]
#     -> vivado_env_capture/impl1_properties.txt
# (not done here because this capture deliberately opens no project).
puts "done. Attach vivado_env_capture/ to rebuild_pilot/ before the pilot."
