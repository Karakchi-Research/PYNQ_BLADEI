# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for the Phase 0.5C harness tie-off audit. Every tie-off
#              form, the hierarchical constant resolution, the freeze
#              analysis, and every verdict state are driven with synthetic
#              Verilog written to a temporary benchmark tree, so the analysis
#              is exercised end to end without the benchmark suite present.
#
#              Two tests are regression guards for real bugs found while
#              developing this screen:
#                - `prog_dat_i == 4'b1000` inside an always block must NOT
#                  register prog_dat_i as procedurally driven. It did, which
#                  hid the tie-off and reported the measured-dead PIC16F84
#                  trojan as live.
#                - a resynthesized netlist pair (bulk added AND removed lines)
#                  must be rejected rather than mined for a read set, or the
#                  b15/b19 pairs manufacture verdicts out of synthesis noise.
#
#              The last test runs against the real benchmark tree when it is
#              present and asserts the screen does not contradict the three
#              Vivado-measured pilot outcomes; it skips when the tree is not
#              on this machine.
#
# Usage:
#   python3 test_wrapper_tieoff_audit.py   (or: pytest -q)

import os
import shutil
import tempfile

from wrapper_tieoff_audit import (IND_NO_READS, IND_NO_RTL, NOMINATED,
                                  TROJAN_INPUTS_ALL_TIED,
                                  TROJAN_INPUTS_LIVE,
                                  TROJAN_INPUTS_PARTIALLY_TIED,
                                  TROJAN_STATE_FROZEN, Design, PILOT_TRUTH,
                                  audit_benchmark, classify, is_const_expr,
                                  validate)

BENCH_TREE = os.path.expanduser(
    "~/Desktop/Karakchi-Research/trusthub_benchmarks")


# --- helpers ---------------------------------------------------------------
def _bench(tjin_files, tjfree_files):
    """Write a synthetic benchmark dir; returns its path (caller deletes)."""
    root = tempfile.mkdtemp(prefix="tieoff_bench_")
    for sub, files in (("TjIn", tjin_files), ("TjFree", tjfree_files)):
        d = os.path.join(root, "src", sub)
        os.makedirs(d)
        for name, text in files.items():
            with open(os.path.join(d, name), "w") as fh:
                fh.write(text)
    return root


def _audit(tjin_files, tjfree_files):
    root = _bench(tjin_files, tjfree_files)
    try:
        return audit_benchmark(root)
    finally:
        shutil.rmtree(root)


def _design(files):
    root = tempfile.mkdtemp(prefix="tieoff_design_")
    try:
        for name, text in files.items():
            with open(os.path.join(root, name), "w") as fh:
                fh.write(text)
        return Design(root)
    finally:
        shutil.rmtree(root)


# --- constant recognition --------------------------------------------------
def test_const_expr_forms():
    for e in ("1'b0", "14'h0000", "8'd12", "0", "{4'h0, 4'h0}", "~1'b1"):
        assert is_const_expr(e), e
    for e in ("prog_dat", "{a, 1'b0}", "a & b", ""):
        assert not is_const_expr(e), e


# --- the four tie-off forms, each resolved through the hierarchy ------------
_CORE = """
module core(input [3:0] d, input clk, output [3:0] q);
    reg [3:0] r;
    always @(posedge clk) r <= d;
    assign q = r;
endmodule
"""


def _top_with(tie):
    return """
module top(input clk, output [3:0] out);
    %s
    core u_core(.d(d), .clk(clk), .q(out));
endmodule
""" % tie


def test_tieoff_form_assign():
    d = _design({"a.v": _CORE + _top_with("wire [3:0] d; assign d = 4'h0;")})
    assert d.resolve("core", "d") == "CONST"


def test_tieoff_form_inline_wire():
    d = _design({"a.v": _CORE + _top_with("wire [3:0] d = 4'h0;")})
    assert d.resolve("core", "d") == "CONST"


def test_tieoff_form_reg_initializer_with_no_other_driver():
    d = _design({"a.v": _CORE + _top_with("reg [3:0] d = 4'hF;")})
    assert d.resolve("core", "d") == "CONST"


def test_reg_initializer_with_a_procedural_driver_is_not_const():
    tie = """reg [3:0] d = 4'hF;
             always @(posedge clk) d <= d + 1'b1;"""
    d = _design({"a.v": _CORE + _top_with(tie)})
    assert d.resolve("core", "d") == "LIVE"


def test_tieoff_form_constant_in_port_map():
    src = _CORE + """
module top(input clk, output [3:0] out);
    core u_core(.d(4'h0), .clk(clk), .q(out));
endmodule
"""
    d = _design({"a.v": src})
    assert d.resolve("core", "d") == "CONST"


def test_live_top_level_input_is_not_const():
    src = _CORE + """
module top(input clk, input [3:0] ext, output [3:0] out);
    core u_core(.d(ext), .clk(clk), .q(out));
endmodule
"""
    d = _design({"a.v": src})
    assert d.resolve("core", "d") == "LIVE"


def test_const_requires_every_instantiation_path():
    """One tied instance and one live instance must resolve LIVE, not CONST."""
    src = _CORE + """
module top(input clk, input [3:0] ext, output [3:0] out, output [3:0] out2);
    core u_tied(.d(4'h0), .clk(clk), .q(out));
    core u_live(.d(ext), .clk(clk), .q(out2));
endmodule
"""
    d = _design({"a.v": src})
    assert d.resolve("core", "d") == "LIVE"


# --- regression: comparison must not be read as a driver -------------------
def test_comparison_is_not_a_procedural_driver():
    """`if (d == 4'h8)` must not mark d as driven -- it hid the PIC tie-off."""
    src = """
module core(input [3:0] d, input clk, output reg hit);
    always @(posedge clk) begin
        if (d == 4'h8) hit <= 1'b1;
        else hit <= 1'b0;
    end
endmodule
""" + _top_with("wire [3:0] d = 4'h8;")
    d = _design({"a.v": src})
    assert d.resolve("core", "d") == "CONST"


# --- verdict states, end to end -------------------------------------------
# The PIC16F84-T100 mechanism, reduced: the harness ties the bus feeding the
# trigger counter, so the counter can never advance.
_HOST_FREE = """
module host(input [13:0] prog_dat_i, input rst_n, input clk,
            output [12:0] prog_adr_o);
    reg [12:0] pc_reg;
    always @(posedge clk) pc_reg <= pc_reg + 1'b1;
    assign prog_adr_o = pc_reg;
endmodule
"""
_HOST_TROJAN = """
module host(input [13:0] prog_dat_i, input rst_n, input clk,
            output [12:0] prog_adr_o);
    reg [12:0] pc_reg;
    always @(posedge clk) pc_reg <= pc_reg + 1'b1;
    reg [12:0] Counter;
    always @(rst_n, prog_dat_i) begin
        if (rst_n == 0) Counter <= 0;
        else if (prog_dat_i[13:10] == 4'b1000) Counter <= Counter + 1;
    end
    assign prog_adr_o = (Counter > 100) ? pc_reg + 2 : pc_reg;
endmodule
"""
_WRAP_TIED = """
module top(input clk, output [12:0] out);
    wire [13:0] prog_dat;
    assign prog_dat = 14'h0000;
    host u_host(.prog_dat_i(prog_dat), .rst_n(1'b1), .clk(clk),
                .prog_adr_o(out));
endmodule
"""
_WRAP_LIVE = """
module top(input clk, input [13:0] ext, output [12:0] out);
    host u_host(.prog_dat_i(ext), .rst_n(1'b1), .clk(clk),
                .prog_adr_o(out));
endmodule
"""


def test_verdict_state_frozen_matches_the_pic16f84_mechanism():
    rec = _audit({"host.v": _HOST_TROJAN, "top.v": _WRAP_TIED},
                 {"host.v": _HOST_FREE, "top.v": _WRAP_TIED})
    assert rec["verdict"] == TROJAN_STATE_FROZEN
    assert "Counter" in rec["frozen_state_regs"]
    assert rec["verdict"] in NOMINATED


def test_verdict_state_live_when_the_same_trojan_gets_real_data():
    rec = _audit({"host.v": _HOST_TROJAN, "top.v": _WRAP_LIVE},
                 {"host.v": _HOST_FREE, "top.v": _WRAP_LIVE})
    assert rec["verdict"] == TROJAN_INPUTS_LIVE
    assert rec["frozen_state_regs"] == []
    assert rec["verdict"] not in NOMINATED


def test_verdict_all_tied_for_a_combinational_trojan():
    """No trojan state, every host read constant -> ALL_TIED, nominated."""
    free = """
module host(input [7:0] a, input clk, output [7:0] y);
    assign y = a;
endmodule
"""
    trojan = """
module host(input [7:0] a, input clk, output [7:0] y);
    assign y = a;
    wire leak;
    assign leak = a[0] & a[1];
endmodule
"""
    wrap = """
module top(input clk, output [7:0] out);
    wire [7:0] a = 8'h00;
    host u_host(.a(a), .clk(clk), .y(out));
endmodule
"""
    rec = _audit({"host.v": trojan, "top.v": wrap},
                 {"host.v": free, "top.v": wrap})
    assert rec["verdict"] == TROJAN_INPUTS_ALL_TIED
    assert rec["verdict"] in NOMINATED


def test_verdict_partially_tied():
    free = """
module host(input [7:0] a, input [7:0] b, input clk, output [7:0] y);
    assign y = a ^ b;
endmodule
"""
    trojan = """
module host(input [7:0] a, input [7:0] b, input clk, output [7:0] y);
    assign y = a ^ b;
    wire leak;
    assign leak = a[0] & b[1];
endmodule
"""
    wrap = """
module top(input clk, input [7:0] ext, output [7:0] out);
    wire [7:0] a = 8'h00;
    host u_host(.a(a), .b(ext), .clk(clk), .y(out));
endmodule
"""
    rec = _audit({"host.v": trojan, "top.v": wrap},
                 {"host.v": free, "top.v": wrap})
    assert rec["verdict"] == TROJAN_INPUTS_PARTIALLY_TIED
    assert rec["verdict"] not in NOMINATED


def test_verdict_indeterminate_without_a_verilog_pair():
    rec = _audit({"top.vhd": "-- VHDL only\n"}, {"top.vhd": "-- VHDL only\n"})
    assert rec["verdict"] == IND_NO_RTL
    assert rec["verdict"] not in NOMINATED


def test_verdict_indeterminate_when_no_read_set_is_derivable():
    """Identical RTL: no trojan construct to analyse -- never a pass."""
    rec = _audit({"host.v": _HOST_FREE, "top.v": _WRAP_TIED},
                 {"host.v": _HOST_FREE, "top.v": _WRAP_TIED})
    assert rec["verdict"] == IND_NO_READS
    assert rec["verdict"] not in NOMINATED


# --- regression: resynthesized netlist pairs must be rejected -------------
def test_resynthesized_netlist_pair_is_not_mined_for_a_read_set():
    """Bulk added AND removed lines = two synthesis runs, not an insertion."""
    cells = "\n".join("INVX0 U%d (.IN(n%d), .QN(n%d));" % (i, i, i + 1)
                      for i in range(200))
    other = "\n".join("INVX0 V%d (.IN(m%d), .QN(m%d));" % (i, i, i + 1)
                      for i in range(200))
    lib = "module INVX0(input IN, output QN); endmodule\n"
    free = lib + "module dut(input clk, output n0);\n%s\nendmodule\n" % cells
    tjin = lib + "module dut(input clk, output n0);\n%s\nendmodule\n" % other
    wrap = """
module top(input clk, output [63:0] out);
    dut u_dut(.clk(clk), .n0(out[0]));
endmodule
"""
    rec = _audit({"dut.v": tjin, "top.v": wrap},
                 {"dut.v": free, "top.v": wrap})
    assert rec["verdict"] == IND_NO_READS
    assert all(not d["clean_insertion"] for d in rec["line_diff"]
               if d["module"] == "dut")


# --- pure classifier ------------------------------------------------------
def test_classify_is_pure_and_covers_every_state():
    const = [{"signal": "d", "state": "CONST"}]
    live = [{"signal": "d", "state": "LIVE"}]
    clk_only = [{"signal": "clk", "state": "LIVE"}]
    assert classify(live, ["Counter"], "LINE_DIFF", True) == TROJAN_STATE_FROZEN
    assert classify(const, [], "LINE_DIFF", True) == TROJAN_INPUTS_ALL_TIED
    assert classify(const + live, [], "LINE_DIFF", True) == \
        TROJAN_INPUTS_PARTIALLY_TIED
    assert classify(live, [], "LINE_DIFF", True) == TROJAN_INPUTS_LIVE
    assert classify(clk_only, [], "LINE_DIFF", True) == IND_NO_READS
    assert classify([], [], None, False) == IND_NO_RTL


# --- validation against measured Vivado outcomes --------------------------
def test_does_not_contradict_the_measured_pilot_outcomes():
    if not os.path.isdir(BENCH_TREE):
        print("SKIP: benchmark tree not on this machine (%s)" % BENCH_TREE)
        return
    records = []
    for bench in PILOT_TRUTH:
        path = os.path.join(BENCH_TREE, bench)
        if not os.path.isdir(path):
            print("SKIP: %s not present" % bench)
            return
        rec = audit_benchmark(path)
        rec["benchmark"] = bench
        records.append(rec)
    ok, rows = validate(records)
    for row in rows:
        assert row["agrees"], row
    assert ok


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items()
           if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in fns:
        try:
            fn()
            print("PASS %s" % name)
        except AssertionError as exc:
            failures += 1
            print("FAIL %s: %s" % (name, exc))
    print("\n%d/%d passed" % (len(fns) - failures, len(fns)))
    sys.exit(1 if failures else 0)
