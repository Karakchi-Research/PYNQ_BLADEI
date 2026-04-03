// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Thu Jul 17 17:38:59 2025
// Host        : higgs running 64-bit Ubuntu 20.04.6 LTS
// Command     : write_verilog -force -mode funcsim -rename_top decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix -prefix
//               decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_ state_memory_sim_netlist.v
// Design      : state_memory
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xc7z020clg400-1
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* CHECK_LICENSE_TYPE = "state_memory,dist_mem_gen_v8_0_14,{}" *) (* downgradeipidentifiedwarnings = "yes" *) (* x_core_info = "dist_mem_gen_v8_0_14,Vivado 2023.2" *) 
(* NotValidForBitStream *)
module decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix
   (a,
    clk,
    qspo);
  input [3:0]a;
  input clk;
  output [127:0]qspo;

  wire \<const0> ;
  wire [3:0]a;
  wire clk;
  wire [116:0]\^qspo ;
  wire [127:0]NLW_U0_dpo_UNCONNECTED;
  wire [127:0]NLW_U0_qdpo_UNCONNECTED;
  wire [127:8]NLW_U0_qspo_UNCONNECTED;
  wire [127:0]NLW_U0_spo_UNCONNECTED;

  assign qspo[127] = \<const0> ;
  assign qspo[126] = \<const0> ;
  assign qspo[125] = \<const0> ;
  assign qspo[124] = \<const0> ;
  assign qspo[123] = \<const0> ;
  assign qspo[122] = \<const0> ;
  assign qspo[121] = \<const0> ;
  assign qspo[120] = \<const0> ;
  assign qspo[119] = \<const0> ;
  assign qspo[118] = \<const0> ;
  assign qspo[117] = \<const0> ;
  assign qspo[116] = \^qspo [116];
  assign qspo[115] = \<const0> ;
  assign qspo[114] = \<const0> ;
  assign qspo[113] = \<const0> ;
  assign qspo[112] = \^qspo [112];
  assign qspo[111] = \<const0> ;
  assign qspo[110] = \<const0> ;
  assign qspo[109] = \^qspo [109];
  assign qspo[108] = \<const0> ;
  assign qspo[107] = \<const0> ;
  assign qspo[106] = \<const0> ;
  assign qspo[105] = \^qspo [105];
  assign qspo[104] = \<const0> ;
  assign qspo[103] = \<const0> ;
  assign qspo[102] = \<const0> ;
  assign qspo[101:100] = \^qspo [101:100];
  assign qspo[99] = \<const0> ;
  assign qspo[98] = \<const0> ;
  assign qspo[97:96] = \^qspo [97:96];
  assign qspo[95] = \<const0> ;
  assign qspo[94] = \^qspo [94];
  assign qspo[93] = \<const0> ;
  assign qspo[92] = \<const0> ;
  assign qspo[91] = \<const0> ;
  assign qspo[90] = \^qspo [90];
  assign qspo[89] = \<const0> ;
  assign qspo[88] = \<const0> ;
  assign qspo[87] = \<const0> ;
  assign qspo[86] = \^qspo [86];
  assign qspo[85] = \<const0> ;
  assign qspo[84] = \^qspo [84];
  assign qspo[83] = \<const0> ;
  assign qspo[82] = \^qspo [82];
  assign qspo[81] = \<const0> ;
  assign qspo[80] = \^qspo [80];
  assign qspo[79] = \<const0> ;
  assign qspo[78:77] = \^qspo [78:77];
  assign qspo[76] = \<const0> ;
  assign qspo[75] = \<const0> ;
  assign qspo[74:73] = \^qspo [74:73];
  assign qspo[72] = \<const0> ;
  assign qspo[71] = \<const0> ;
  assign qspo[70:68] = \^qspo [70:68];
  assign qspo[67] = \<const0> ;
  assign qspo[66:63] = \^qspo [66:63];
  assign qspo[62] = \<const0> ;
  assign qspo[61] = \<const0> ;
  assign qspo[60] = \<const0> ;
  assign qspo[59] = \^qspo [59];
  assign qspo[58] = \<const0> ;
  assign qspo[57] = \<const0> ;
  assign qspo[56] = \<const0> ;
  assign qspo[55] = \^qspo [55];
  assign qspo[54] = \<const0> ;
  assign qspo[53] = \<const0> ;
  assign qspo[52:51] = \^qspo [52:51];
  assign qspo[50] = \<const0> ;
  assign qspo[49] = \<const0> ;
  assign qspo[48:47] = \^qspo [48:47];
  assign qspo[46] = \<const0> ;
  assign qspo[45] = \^qspo [45];
  assign qspo[44] = \<const0> ;
  assign qspo[43] = \^qspo [43];
  assign qspo[42] = \<const0> ;
  assign qspo[41] = \^qspo [41];
  assign qspo[40] = \<const0> ;
  assign qspo[39] = \^qspo [39];
  assign qspo[38] = \<const0> ;
  assign qspo[37:35] = \^qspo [37:35];
  assign qspo[34] = \<const0> ;
  assign qspo[33:30] = \^qspo [33:30];
  assign qspo[29] = \<const0> ;
  assign qspo[28] = \<const0> ;
  assign qspo[27:26] = \^qspo [27:26];
  assign qspo[25] = \<const0> ;
  assign qspo[24] = \<const0> ;
  assign qspo[23:22] = \^qspo [23:22];
  assign qspo[21] = \<const0> ;
  assign qspo[20:18] = \^qspo [20:18];
  assign qspo[17] = \<const0> ;
  assign qspo[16:13] = \^qspo [16:13];
  assign qspo[12] = \<const0> ;
  assign qspo[11:9] = \^qspo [11:9];
  assign qspo[8] = \<const0> ;
  assign qspo[7:0] = \^qspo [7:0];
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
  (* c_addr_width = "4" *) 
  (* c_default_data = "0" *) 
  (* c_depth = "16" *) 
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
  decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_dist_mem_gen_v8_0_14 U0
       (.a(a),
        .clk(clk),
        .d({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .dpo(NLW_U0_dpo_UNCONNECTED[127:0]),
        .dpra({1'b0,1'b0,1'b0,1'b0}),
        .i_ce(1'b1),
        .qdpo(NLW_U0_qdpo_UNCONNECTED[127:0]),
        .qdpo_ce(1'b1),
        .qdpo_clk(1'b0),
        .qdpo_rst(1'b0),
        .qdpo_srst(1'b0),
        .qspo({NLW_U0_qspo_UNCONNECTED[127:117],\^qspo }),
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
`pragma protect encoding = (enctype = "BASE64", line_length = 76, bytes = 19536)
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
