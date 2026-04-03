transcript off
onbreak {quit -force}
onerror {quit -force}
transcript on

asim +access +r +m+key_memory  -L dist_mem_gen_v8_0_14 -L xil_defaultlib -L unisims_ver -L unimacro_ver -L secureip -O2 xil_defaultlib.key_memory xil_defaultlib.glbl

do {key_memory.udo}

run

endsim

quit -force
