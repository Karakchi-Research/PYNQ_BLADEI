vlib questa_lib/work
vlib questa_lib/msim

vlib questa_lib/msim/dist_mem_gen_v8_0_14
vlib questa_lib/msim/xil_defaultlib

vmap dist_mem_gen_v8_0_14 questa_lib/msim/dist_mem_gen_v8_0_14
vmap xil_defaultlib questa_lib/msim/xil_defaultlib

vlog -work dist_mem_gen_v8_0_14 -64 -incr -mfcu  \
"../../../ipstatic/simulation/dist_mem_gen_v8_0.v" \

vlog -work xil_defaultlib -64 -incr -mfcu  \
"../../../../trusthub_pynq_z1.gen/sources_1/ip/key_memory/sim/key_memory.v" \


vlog -work xil_defaultlib \
"glbl.v"

