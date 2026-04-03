// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Thu Dec 18 01:04:13 2025
// Host        : higgs running 64-bit Ubuntu 20.04.6 LTS
// Command     : write_verilog -force -mode funcsim
//               /share/ryes/Vivado/VivadoProjects/trusthub_pynq_z1/trusthub_pynq_z1.gen/sources_1/ip/state_memory/state_memory_sim_netlist.v
// Design      : state_memory
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xc7z020clg400-1
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* CHECK_LICENSE_TYPE = "state_memory,dist_mem_gen_v8_0_14,{}" *) (* downgradeipidentifiedwarnings = "yes" *) (* x_core_info = "dist_mem_gen_v8_0_14,Vivado 2023.2" *) 
(* NotValidForBitStream *)
module state_memory
   (a,
    clk,
    qspo);
  input [4:0]a;
  input clk;
  output [127:0]qspo;

  wire \<const0> ;
  wire [4:0]a;
  wire clk;
  wire [125:2]\^qspo ;
  wire [127:0]NLW_U0_dpo_UNCONNECTED;
  wire [127:0]NLW_U0_qdpo_UNCONNECTED;
  wire [127:0]NLW_U0_qspo_UNCONNECTED;
  wire [127:0]NLW_U0_spo_UNCONNECTED;

  assign qspo[127] = \<const0> ;
  assign qspo[126] = \<const0> ;
  assign qspo[125:124] = \^qspo [125:124];
  assign qspo[123] = \<const0> ;
  assign qspo[122] = \<const0> ;
  assign qspo[121] = \^qspo [121];
  assign qspo[120] = \<const0> ;
  assign qspo[119] = \<const0> ;
  assign qspo[118] = \^qspo [118];
  assign qspo[117] = \<const0> ;
  assign qspo[116] = \<const0> ;
  assign qspo[115] = \<const0> ;
  assign qspo[114] = \<const0> ;
  assign qspo[113:108] = \^qspo [113:108];
  assign qspo[107] = \<const0> ;
  assign qspo[106:105] = \^qspo [106:105];
  assign qspo[104] = \<const0> ;
  assign qspo[103] = \^qspo [103];
  assign qspo[102] = \<const0> ;
  assign qspo[101] = \^qspo [101];
  assign qspo[100] = \<const0> ;
  assign qspo[99] = \^qspo [99];
  assign qspo[98] = \<const0> ;
  assign qspo[97] = \<const0> ;
  assign qspo[96] = \<const0> ;
  assign qspo[95] = \^qspo [95];
  assign qspo[94] = \<const0> ;
  assign qspo[93] = \<const0> ;
  assign qspo[92] = \<const0> ;
  assign qspo[91] = \^qspo [91];
  assign qspo[90] = \<const0> ;
  assign qspo[89] = \<const0> ;
  assign qspo[88] = \<const0> ;
  assign qspo[87] = \<const0> ;
  assign qspo[86] = \^qspo [86];
  assign qspo[85] = \<const0> ;
  assign qspo[84:83] = \^qspo [84:83];
  assign qspo[82] = \<const0> ;
  assign qspo[81] = \^qspo [81];
  assign qspo[80] = \<const0> ;
  assign qspo[79] = \<const0> ;
  assign qspo[78] = \<const0> ;
  assign qspo[77:76] = \^qspo [77:76];
  assign qspo[75] = \<const0> ;
  assign qspo[74] = \<const0> ;
  assign qspo[73] = \<const0> ;
  assign qspo[72] = \<const0> ;
  assign qspo[71] = \^qspo [71];
  assign qspo[70] = \<const0> ;
  assign qspo[69] = \<const0> ;
  assign qspo[68] = \<const0> ;
  assign qspo[67:66] = \^qspo [67:66];
  assign qspo[65] = \<const0> ;
  assign qspo[64] = \^qspo [64];
  assign qspo[63] = \<const0> ;
  assign qspo[62] = \<const0> ;
  assign qspo[61:60] = \^qspo [61:60];
  assign qspo[59] = \<const0> ;
  assign qspo[58] = \<const0> ;
  assign qspo[57] = \<const0> ;
  assign qspo[56] = \^qspo [56];
  assign qspo[55] = \<const0> ;
  assign qspo[54] = \<const0> ;
  assign qspo[53:52] = \^qspo [53:52];
  assign qspo[51] = \<const0> ;
  assign qspo[50] = \<const0> ;
  assign qspo[49] = \<const0> ;
  assign qspo[48:47] = \^qspo [48:47];
  assign qspo[46] = \<const0> ;
  assign qspo[45] = \<const0> ;
  assign qspo[44:43] = \^qspo [44:43];
  assign qspo[42] = \<const0> ;
  assign qspo[41] = \<const0> ;
  assign qspo[40] = \<const0> ;
  assign qspo[39] = \^qspo [39];
  assign qspo[38] = \<const0> ;
  assign qspo[37] = \^qspo [37];
  assign qspo[36] = \<const0> ;
  assign qspo[35] = \<const0> ;
  assign qspo[34] = \<const0> ;
  assign qspo[33] = \^qspo [33];
  assign qspo[32] = \<const0> ;
  assign qspo[31:29] = \^qspo [31:29];
  assign qspo[28] = \<const0> ;
  assign qspo[27] = \<const0> ;
  assign qspo[26] = \<const0> ;
  assign qspo[25] = \<const0> ;
  assign qspo[24] = \<const0> ;
  assign qspo[23] = \<const0> ;
  assign qspo[22] = \<const0> ;
  assign qspo[21:20] = \^qspo [21:20];
  assign qspo[19] = \<const0> ;
  assign qspo[18:16] = \^qspo [18:16];
  assign qspo[15] = \<const0> ;
  assign qspo[14] = \<const0> ;
  assign qspo[13] = \<const0> ;
  assign qspo[12] = \<const0> ;
  assign qspo[11] = \<const0> ;
  assign qspo[10:8] = \^qspo [10:8];
  assign qspo[7] = \<const0> ;
  assign qspo[6] = \<const0> ;
  assign qspo[5:4] = \^qspo [5:4];
  assign qspo[3] = \<const0> ;
  assign qspo[2] = \^qspo [2];
  assign qspo[1] = \<const0> ;
  assign qspo[0] = \<const0> ;
  GND GND
       (.G(\<const0> ));
  (* C_FAMILY = "zynq" *) 
  (* C_HAS_D = "0" *) 
  (* C_HAS_DPO = "0" *) 
  (* C_HAS_DPRA = "0" *) 
  (* C_HAS_I_CE = "0" *) 
  (* C_HAS_QDPO = "0" *) 
  (* C_HAS_QDPO_CE = "0" *) 
  (* C_HAS_QDPO_CLK = "0" *) 
  (* C_HAS_QDPO_RST = "0" *) 
  (* C_HAS_QDPO_SRST = "0" *) 
  (* C_HAS_WE = "0" *) 
  (* C_MEM_TYPE = "0" *) 
  (* C_PIPELINE_STAGES = "0" *) 
  (* C_QCE_JOINED = "0" *) 
  (* C_QUALIFY_WE = "0" *) 
  (* C_REG_DPRA_INPUT = "0" *) 
  (* c_addr_width = "5" *) 
  (* c_default_data = "0" *) 
  (* c_depth = "32" *) 
  (* c_elaboration_dir = "./" *) 
  (* c_has_clk = "1" *) 
  (* c_has_qspo = "1" *) 
  (* c_has_qspo_ce = "0" *) 
  (* c_has_qspo_rst = "0" *) 
  (* c_has_qspo_srst = "0" *) 
  (* c_has_spo = "0" *) 
  (* c_mem_init_file = "state_memory.mif" *) 
  (* c_parser_type = "1" *) 
  (* c_read_mif = "1" *) 
  (* c_reg_a_d_inputs = "1" *) 
  (* c_sync_enable = "1" *) 
  (* c_width = "128" *) 
  (* is_du_within_envelope = "true" *) 
  state_memory_dist_mem_gen_v8_0_14 U0
       (.a(a),
        .clk(clk),
        .d({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .dpo(NLW_U0_dpo_UNCONNECTED[127:0]),
        .dpra({1'b0,1'b0,1'b0,1'b0,1'b0}),
        .i_ce(1'b1),
        .qdpo(NLW_U0_qdpo_UNCONNECTED[127:0]),
        .qdpo_ce(1'b1),
        .qdpo_clk(1'b0),
        .qdpo_rst(1'b0),
        .qdpo_srst(1'b0),
        .qspo({NLW_U0_qspo_UNCONNECTED[127:126],\^qspo ,NLW_U0_qspo_UNCONNECTED[1:0]}),
        .qspo_ce(1'b1),
        .qspo_rst(1'b0),
        .qspo_srst(1'b0),
        .spo(NLW_U0_spo_UNCONNECTED[127:0]),
        .we(1'b0));
endmodule
`pragma protect begin_protected
`pragma protect version = 1
`pragma protect encrypt_agent = "XILINX"
`pragma protect encrypt_agent_info = "Xilinx Encryption Tool 2023.2"
`pragma protect key_keyowner="Synopsys", key_keyname="SNPS-VCS-RSA-2", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=128)
`pragma protect key_block
uwBH4JaTzmENPjp1VK18+NmHqz3idKCCPayqakkK6bYDVk0JtRfycJYNxbcnLmlw5yuLTcDXBBKk
FqBPE2n7wWKg9tfz2Y8PrWAvnbsIFMfxBK8sfWUf8PPnz8vUwwMHjbXUWcgCgvtygj/TbB+jcZ8Z
CjYnBZ8tNdKOO1iDLpQ=

`pragma protect key_keyowner="Aldec", key_keyname="ALDEC15_001", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
Ff7o4KDFniNgPFT3cDZtw4HhiKzFbOFtLXtuci0MZhgQ8oZ15BcuowAfxUJXngU8JkWI9cbWKkG8
h/PODwnWEt4eK4VDKRk6Hw3QkZiKAa1N3QupC8D5bR7vJ/+RhJwSayz9t2JpdZaEhKgCgqTcX6oZ
4fCEOmSTUWVob+DXV4UfaMyfVm5VI0wxZ7q0mjFx+pdkt56PuNREX9kH4a9Ma1P0sYo8XaTpANLa
JC6eXOuUQlp40M9F/NL1Xajpys0YfGx8AveMAFEyfRmHZs+NbXmny/79vednrm+FhwtS9LveegmF
NZW9jiiR+9Igeraaz+QXPc6JO/nCDTr4Fuwusg==

`pragma protect key_keyowner="Mentor Graphics Corporation", key_keyname="MGC-VELOCE-RSA", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=128)
`pragma protect key_block
enb/INzHPP7GNdz8dyyqgVCJiMs9JXcjMywZXhzPersGm0A258UOUwtOqcF1rO7lnrKwTeWbNFVN
dO3BxXBpzGnYWUqDda208CYV9hTWFhfySQdX58qn1Z8QY5G7KniMCVjaGuPPCfToPOOdbAxR9XUp
XbMr0vrZKWxz8nBhGYc=

`pragma protect key_keyowner="Mentor Graphics Corporation", key_keyname="MGC-VERIF-SIM-RSA-2", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
RKZNANfa63/n14iwmSxsB/UeV76BNqjEiYgjlZ2LdFWOArCv6D+jhC4sjGMiaz8GJ8J5kQeiWB0Y
e1+zdHflgzODs6eVC82MlEcfgP0vdDIBn0PP8rVDg5O31eQuJ7n5zn4XJu+vzjpkvJIHKrktAsP4
jg+LRxcTOu0dILImk7Vwgyuwhi8OxNN+jBVbLVxdNj0l5aQMgRZlU/8FVh3u958SH7z/fHnwGaOw
P8QgNv0ZZblWvpxa8TJIwlgVb9354a0eyD9XsKy5VfuUG03nmputxNzUuIUmGtBGCqx+4D4pyCch
j/ixD5iiKRmeKD1/RtGzxmrJap7SAHMuzic1Hw==

`pragma protect key_keyowner="Real Intent", key_keyname="RI-RSA-KEY-1", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
OQMD0qoDy+4W8+jfTV63GDTwmjWvJILCTofeYJTZqWc2KhrzQXwVMW48dTyIriC6bA4bmXD5BwcB
W2gGbVUvY1Y1+wEFEwYIC0LiPrJO0DhpM1JhP2vkxnTEwaODiEp5x3XqHgsiys0I2/9mE4z4Hlbl
jzftQ/8sVSYokhMp9eaIHk3HNCSBllv90qeBfH3fOdVI2gA1r/22PktttbkyKji24r7jM5o4aMIc
Sp6u0DCnD2cSPCuCuMW3A9sFRuTKbXiLAeeymFIAXHKYQgWXXOqmbKHrk4GviHQyz31C9d+hm6dh
RMtaCyWnhqo3QE/QxP0TsYk3CgkjDCU+KK/ozA==

`pragma protect key_keyowner="Xilinx", key_keyname="xilinxt_2022_10", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
uV1eryjGs1SHbpKIAk5r3BY2SLKX9RlfGw6gbw/UtzBYt4U7vTBIy+x767ojEcmbGLos8kr8vilV
cnNOnsbu7vOAUIe+1PgpaPaCkv2OTPXaE0tfps6+Q6D3zB6j2a2FE1gRIPOniwAdlIn69jL2tuWD
M2BN1efQhi0lZHuKtTgzBOVXIg+zbTiH2k2kHWThOi6WayoBEny+g88wRi6pUBeB6aW3ezFYNmsl
zeOY9xmt+UhRMcr87DCcZdmjsIk6VrsIKF60y93pM0IoQ56iWpQ2OKZK+Ng9qC+pNHBEYEhiMQFb
kUesHtcFOIS7Ok6S9O9SMgf7lMQFOh9w0L31UA==

`pragma protect key_keyowner="Metrics Technologies Inc.", key_keyname="DSim", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
GM2VxmvaiVBg1DsqOLewt6rcWtfH/Gj1QS7fUSMudF5qJ2fn+TXd8kcCwwrxdcXNXjoVi2As5jmL
yw1/NZreemrkS1YCJJDxmnE8CW2q9/4N4a79kApF1VfD5XdpaULhVn+Eb+jXCQFG+GEEOvnPb0Me
bbfRkfc0DAIWgtG2D81EQ28mg7KAWtsDpdUCi+BKdIAj8RXoTiQbFbiBeT7EiRIrz2PQF9nhQBfF
FjlrCNwDP4hRQJQeZcf/1Pl8SFyKGQb6iVF+VhhCVCunL7VBmzaCOW/gowPM7hRM2dvzmxcgeKfs
dZx/fy2rk1iokUi+3B+Jc6CycMWbHu8EfCh7iQ==

`pragma protect key_keyowner="Atrenta", key_keyname="ATR-SG-RSA-1", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=384)
`pragma protect key_block
NSZoNMCco4gpYPcg8pb9mtee1JxEWDcDzt6wnS0LeSPMi2upLvQXnSQKMvJGGOKStJOcu1eu7x33
4Xa3ApbjbfZ+lgs1PYlyY4V+B2Lio1EEo1uzZVWFrVFvmknOZwj6Gcmj5N/osaiqKaeIw7NTTbyX
HNHOabVsQJ540qnP4u/nzS/h/AQcm0PFLadGZtHJZEzyQDSSdghD/y/OLprdBcInfQDwAxQuJpCy
ExX4lD2WMrCkymNBS9NMH0vYh4kvpYKRO/oHuGcOZVg0p8vfMmz/BJDHuxTcS3FpLT0WxGVcmUIk
cuqKQFiVwwgnW9AfYkbsMrwfl9po2pofaAY2JC5ZTMyO1qEfSu4fxTRJNnDRvW65KkMdJhZFa36p
82hcDlaYvBowndZfMc42Sxt+ZULFDTFN0HT50iteAG1yEvJ9jKBiJla+kDQJB0VD0kj4+k8aBug3
uPKVykvf1/Uaw8NoW591pML42qlh8v1RzAm6aDnPRdsDaCc5Dq9QDPuE

`pragma protect key_keyowner="Cadence Design Systems.", key_keyname="CDS_RSA_KEY_VER_1", key_method="rsa"
`pragma protect encoding = (enctype="BASE64", line_length=76, bytes=256)
`pragma protect key_block
oRNld8VrAuP/xHUguZzkh8+wROOItnvw1FQUP5KHjxeh8nudEYH2PGefTPsV73QyEruJanGifjCR
m8XHiIxqAY9fk4CAm+2n67YLFUEHjC1Qri9htrL4W5fnj7OIdzcwttvmGEuGOuYOFA98RcnR0jSL
Nyqq5u/eILCh2MiKiELfsBjRv/WckpboJ+gzO1btduECvdBGjsIcjjHiIzPwNSGxnX3G6zG9OiWq
hXP2Jh0Ril7rGbajit90p+gJpDpuLee/aOh0BUXbYYLU0YIXK8bskgMir7D6cfu5oWDKwYH6/YRR
tFjIhRzFsqwjtmaxUnGTZzxsWGazk+uFfHXl7w==

`pragma protect data_method = "AES128-CBC"
`pragma protect encoding = (enctype = "BASE64", line_length = 76, bytes = 19664)
`pragma protect data_block
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
`pragma protect end_protected
`ifndef GLBL
`define GLBL
`timescale  1 ps / 1 ps

module glbl ();

    parameter ROC_WIDTH = 100000;
    parameter TOC_WIDTH = 0;
    parameter GRES_WIDTH = 10000;
    parameter GRES_START = 10000;

//--------   STARTUP Globals --------------
    wire GSR;
    wire GTS;
    wire GWE;
    wire PRLD;
    wire GRESTORE;
    tri1 p_up_tmp;
    tri (weak1, strong0) PLL_LOCKG = p_up_tmp;

    wire PROGB_GLBL;
    wire CCLKO_GLBL;
    wire FCSBO_GLBL;
    wire [3:0] DO_GLBL;
    wire [3:0] DI_GLBL;
   
    reg GSR_int;
    reg GTS_int;
    reg PRLD_int;
    reg GRESTORE_int;

//--------   JTAG Globals --------------
    wire JTAG_TDO_GLBL;
    wire JTAG_TCK_GLBL;
    wire JTAG_TDI_GLBL;
    wire JTAG_TMS_GLBL;
    wire JTAG_TRST_GLBL;

    reg JTAG_CAPTURE_GLBL;
    reg JTAG_RESET_GLBL;
    reg JTAG_SHIFT_GLBL;
    reg JTAG_UPDATE_GLBL;
    reg JTAG_RUNTEST_GLBL;

    reg JTAG_SEL1_GLBL = 0;
    reg JTAG_SEL2_GLBL = 0 ;
    reg JTAG_SEL3_GLBL = 0;
    reg JTAG_SEL4_GLBL = 0;

    reg JTAG_USER_TDO1_GLBL = 1'bz;
    reg JTAG_USER_TDO2_GLBL = 1'bz;
    reg JTAG_USER_TDO3_GLBL = 1'bz;
    reg JTAG_USER_TDO4_GLBL = 1'bz;

    assign (strong1, weak0) GSR = GSR_int;
    assign (strong1, weak0) GTS = GTS_int;
    assign (weak1, weak0) PRLD = PRLD_int;
    assign (strong1, weak0) GRESTORE = GRESTORE_int;

    initial begin
	GSR_int = 1'b1;
	PRLD_int = 1'b1;
	#(ROC_WIDTH)
	GSR_int = 1'b0;
	PRLD_int = 1'b0;
    end

    initial begin
	GTS_int = 1'b1;
	#(TOC_WIDTH)
	GTS_int = 1'b0;
    end

    initial begin 
	GRESTORE_int = 1'b0;
	#(GRES_START);
	GRESTORE_int = 1'b1;
	#(GRES_WIDTH);
	GRESTORE_int = 1'b0;
    end

endmodule
`endif
