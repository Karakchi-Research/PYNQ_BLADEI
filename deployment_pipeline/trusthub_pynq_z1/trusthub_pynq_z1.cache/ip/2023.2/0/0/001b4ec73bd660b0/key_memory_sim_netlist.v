// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Fri Jul 11 12:51:17 2025
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
  input [3:0]a;
  input clk;
  output [127:0]qspo;

  wire \<const0> ;
  wire [3:0]a;
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
        .dpra({1'b0,1'b0,1'b0,1'b0}),
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
