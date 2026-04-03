// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2023.2 (lin64) Build 4029153 Fri Oct 13 20:13:54 MDT 2023
// Date        : Tue Jul 15 15:57:48 2025
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
  wire [125:0]\^qspo ;
  wire [127:0]NLW_U0_dpo_UNCONNECTED;
  wire [127:0]NLW_U0_qdpo_UNCONNECTED;
  wire [127:12]NLW_U0_qspo_UNCONNECTED;
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
  assign qspo[116] = \^qspo [116];
  assign qspo[115] = \<const0> ;
  assign qspo[114] = \<const0> ;
  assign qspo[113:108] = \^qspo [113:108];
  assign qspo[107] = \<const0> ;
  assign qspo[106:105] = \^qspo [106:105];
  assign qspo[104] = \<const0> ;
  assign qspo[103] = \^qspo [103];
  assign qspo[102] = \<const0> ;
  assign qspo[101:99] = \^qspo [101:99];
  assign qspo[98] = \<const0> ;
  assign qspo[97:94] = \^qspo [97:94];
  assign qspo[93] = \<const0> ;
  assign qspo[92] = \<const0> ;
  assign qspo[91:90] = \^qspo [91:90];
  assign qspo[89] = \<const0> ;
  assign qspo[88] = \<const0> ;
  assign qspo[87] = \<const0> ;
  assign qspo[86] = \^qspo [86];
  assign qspo[85] = \<const0> ;
  assign qspo[84:80] = \^qspo [84:80];
  assign qspo[79] = \<const0> ;
  assign qspo[78:76] = \^qspo [78:76];
  assign qspo[75] = \<const0> ;
  assign qspo[74:73] = \^qspo [74:73];
  assign qspo[72] = \<const0> ;
  assign qspo[71:63] = \^qspo [71:63];
  assign qspo[62] = \<const0> ;
  assign qspo[61:59] = \^qspo [61:59];
  assign qspo[58] = \<const0> ;
  assign qspo[57] = \<const0> ;
  assign qspo[56:55] = \^qspo [56:55];
  assign qspo[54] = \<const0> ;
  assign qspo[53:51] = \^qspo [53:51];
  assign qspo[50] = \<const0> ;
  assign qspo[49] = \<const0> ;
  assign qspo[48:47] = \^qspo [48:47];
  assign qspo[46] = \<const0> ;
  assign qspo[45:43] = \^qspo [45:43];
  assign qspo[42] = \<const0> ;
  assign qspo[41] = \^qspo [41];
  assign qspo[40] = \<const0> ;
  assign qspo[39] = \^qspo [39];
  assign qspo[38] = \<const0> ;
  assign qspo[37:35] = \^qspo [37:35];
  assign qspo[34] = \<const0> ;
  assign qspo[33:29] = \^qspo [33:29];
  assign qspo[28] = \<const0> ;
  assign qspo[27:26] = \^qspo [27:26];
  assign qspo[25] = \<const0> ;
  assign qspo[24] = \<const0> ;
  assign qspo[23:13] = \^qspo [23:13];
  assign qspo[12] = \<const0> ;
  assign qspo[11:0] = \^qspo [11:0];
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
        .qspo({NLW_U0_qspo_UNCONNECTED[127:126],\^qspo }),
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
`pragma protect encoding = (enctype = "BASE64", line_length = 76, bytes = 20720)
`pragma protect data_block
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
o7TPow9+S1dtnJaqMmAnHt5WDPNRa5eNpVKO/8s=
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
