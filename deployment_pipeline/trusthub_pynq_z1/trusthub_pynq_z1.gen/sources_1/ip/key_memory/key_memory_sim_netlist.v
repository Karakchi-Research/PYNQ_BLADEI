// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Thu Dec 18 01:02:02 2025
// Host        : higgs running 64-bit Ubuntu 20.04.6 LTS
// Command     : write_verilog -force -mode funcsim
//               /share/ryes/Vivado/VivadoProjects/trusthub_pynq_z1/trusthub_pynq_z1.gen/sources_1/ip/key_memory/key_memory_sim_netlist.v
// Design      : key_memory
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xc7z020clg400-1
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* CHECK_LICENSE_TYPE = "key_memory,dist_mem_gen_v8_0_14,{}" *) (* downgradeipidentifiedwarnings = "yes" *) (* x_core_info = "dist_mem_gen_v8_0_14,Vivado 2023.2" *) 
(* NotValidForBitStream *)
module key_memory
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
  key_memory_dist_mem_gen_v8_0_14 U0
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
