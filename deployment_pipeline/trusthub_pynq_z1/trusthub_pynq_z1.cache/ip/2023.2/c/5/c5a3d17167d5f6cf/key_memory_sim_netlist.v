// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Thu Dec 18 01:02:00 2025
// Host        : higgs running 64-bit Ubuntu 20.04.6 LTS
// Command     : write_verilog -force -mode funcsim -rename_top decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix -prefix
//               decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix_ key_memory_sim_netlist.v
// Design      : key_memory
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xc7z020clg400-1
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* CHECK_LICENSE_TYPE = "key_memory,dist_mem_gen_v8_0_14,{}" *) (* downgradeipidentifiedwarnings = "yes" *) (* x_core_info = "dist_mem_gen_v8_0_14,Vivado 2023.2" *) 
(* NotValidForBitStream *)
module decalper_eb_ot_sdeen_pot_pi_dehcac_xnilix
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
  assign qspo[125] = \^qspo [125];
  assign qspo[124] = \<const0> ;
  assign qspo[123] = \^qspo [123];
  assign qspo[122] = \<const0> ;
  assign qspo[121:120] = \^qspo [121:120];
  assign qspo[119] = \<const0> ;
  assign qspo[118:113] = \^qspo [118:113];
  assign qspo[112] = \<const0> ;
  assign qspo[111] = \<const0> ;
  assign qspo[110] = \<const0> ;
  assign qspo[109] = \<const0> ;
  assign qspo[108] = \^qspo [108];
  assign qspo[107] = \<const0> ;
  assign qspo[106] = \^qspo [106];
  assign qspo[105] = \<const0> ;
  assign qspo[104] = \^qspo [104];
  assign qspo[103] = \<const0> ;
  assign qspo[102] = \<const0> ;
  assign qspo[101] = \<const0> ;
  assign qspo[100] = \^qspo [100];
  assign qspo[99] = \<const0> ;
  assign qspo[98:97] = \^qspo [98:97];
  assign qspo[96] = \<const0> ;
  assign qspo[95] = \<const0> ;
  assign qspo[94] = \<const0> ;
  assign qspo[93] = \^qspo [93];
  assign qspo[92] = \<const0> ;
  assign qspo[91] = \^qspo [91];
  assign qspo[90] = \<const0> ;
  assign qspo[89] = \<const0> ;
  assign qspo[88] = \<const0> ;
  assign qspo[87] = \^qspo [87];
  assign qspo[86] = \<const0> ;
  assign qspo[85] = \^qspo [85];
  assign qspo[84] = \<const0> ;
  assign qspo[83:81] = \^qspo [83:81];
  assign qspo[80] = \<const0> ;
  assign qspo[79:78] = \^qspo [79:78];
  assign qspo[77] = \<const0> ;
  assign qspo[76] = \^qspo [76];
  assign qspo[75] = \<const0> ;
  assign qspo[74] = \<const0> ;
  assign qspo[73] = \^qspo [73];
  assign qspo[72] = \<const0> ;
  assign qspo[71] = \^qspo [71];
  assign qspo[70] = \<const0> ;
  assign qspo[69] = \^qspo [69];
  assign qspo[68] = \<const0> ;
  assign qspo[67] = \<const0> ;
  assign qspo[66:65] = \^qspo [66:65];
  assign qspo[64] = \<const0> ;
  assign qspo[63] = \^qspo [63];
  assign qspo[62] = \<const0> ;
  assign qspo[61] = \^qspo [61];
  assign qspo[60] = \<const0> ;
  assign qspo[59] = \^qspo [59];
  assign qspo[58] = \<const0> ;
  assign qspo[57:52] = \^qspo [57:52];
  assign qspo[51] = \<const0> ;
  assign qspo[50:48] = \^qspo [50:48];
  assign qspo[47] = \<const0> ;
  assign qspo[46] = \<const0> ;
  assign qspo[45] = \<const0> ;
  assign qspo[44] = \^qspo [44];
  assign qspo[43] = \<const0> ;
  assign qspo[42] = \^qspo [42];
  assign qspo[41] = \<const0> ;
  assign qspo[40:39] = \^qspo [40:39];
  assign qspo[38] = \<const0> ;
  assign qspo[37] = \<const0> ;
  assign qspo[36] = \<const0> ;
  assign qspo[35] = \^qspo [35];
  assign qspo[34] = \<const0> ;
  assign qspo[33] = \<const0> ;
  assign qspo[32] = \<const0> ;
  assign qspo[31] = \<const0> ;
  assign qspo[30] = \<const0> ;
  assign qspo[29] = \<const0> ;
  assign qspo[28] = \<const0> ;
  assign qspo[27] = \^qspo [27];
  assign qspo[26] = \<const0> ;
  assign qspo[25] = \<const0> ;
  assign qspo[24:22] = \^qspo [24:22];
  assign qspo[21] = \<const0> ;
  assign qspo[20] = \<const0> ;
  assign qspo[19:16] = \^qspo [19:16];
  assign qspo[15] = \<const0> ;
  assign qspo[14] = \^qspo [14];
  assign qspo[13] = \<const0> ;
  assign qspo[12] = \<const0> ;
  assign qspo[11:8] = \^qspo [11:8];
  assign qspo[7] = \<const0> ;
  assign qspo[6] = \<const0> ;
  assign qspo[5:2] = \^qspo [5:2];
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
  (* c_mem_init_file = "key_memory.mif" *) 
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
`pragma protect encoding = (enctype = "BASE64", line_length = 76, bytes = 19696)
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
