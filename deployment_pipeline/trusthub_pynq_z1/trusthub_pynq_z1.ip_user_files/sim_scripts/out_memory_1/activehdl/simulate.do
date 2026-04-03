transcript off
onbreak {quit -force}
onerror {quit -force}
transcript on

asim +access +r +m+out_memory  -L dist_mem_gen_v8_0_14 -L xil_defaultlib -L unisims_ver -L unimacro_ver -L secureip -O2 xil_defaultlib.out_memory xil_defaultlib.glbl

do {out_memory.udo}

run

endsim

quit -force
