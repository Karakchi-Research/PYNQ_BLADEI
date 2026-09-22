# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C step 2/3 -- corpus-wide harness tie-off audit.
#
#              The rebuild pilot found that PIC16F84-T100's harness wrapper
#              ties `prog_dat = 14'h0000`, so the trojan's trigger counter can
#              never advance and synthesis deletes the trojan: a MALICIOUS
#              label with no live trojan in the built hardware. The payload
#              still differs from its benign twin by 199 frames, so the
#              audit's payload-identity quarantine does NOT catch it.
#
#              This script asks, statically and corpus-wide, which OTHER
#              benchmarks are in that category. It supersedes the screening
#              flag in candidate_host_inventory.py, which only looked for
#              `assign x = <const>;` in files named top*/wrapper* and so
#              missed three of the four tie-off forms actually used by these
#              harnesses.
#
#              WHAT IS NEW HERE, over the earlier flag:
#                1. all five tie-off forms:
#                     assign net = <const>;      (continuous)
#                     wire  net = <const>;       (inline continuous)
#                     reg   net = <const>;       with no other driver
#                     .port (<const>)            constant in the port map
#                     reg driven ONLY from an `initial` block -- simulation
#                       stimulus, a constant on the device because synthesis
#                       takes the block as a power-on value and ignores its
#                       `#` delays (CONST_SIM_ONLY; how the RS232 harnesses
#                       drive their DUT)
#                2. every RTL file in the TjIn tree, not just top*/wrapper*;
#                3. hierarchical constant resolution -- a signal is CONST only
#                   if it resolves to a constant along EVERY instantiation
#                   path up to the harness top, so a tie-off two levels above
#                   the trojan is still found (the PIC16F84 case);
#                4. the trojan's own READ SET, derived from the TjFree/TjIn
#                   pair, so the verdict is about signals the trojan actually
#                   consumes rather than about tie-offs in general;
#                5. freeze propagation: a trojan state register whose every
#                   data read is constant can never advance, which is the
#                   mechanism that makes synthesis delete the trojan.
#
#              READ-SET EXTRACTION, three methods, recorded per benchmark:
#                TROJAN_MODULE -- modules present in TjIn, absent in TjFree
#                                 (after label-suffix and body-similarity
#                                 pairing), and trojan-marked by name; their
#                                 input port connections at each
#                                 instantiation site are the read set (AES's
#                                 TSC / Trojan_Trigger). The name marker
#                                 keeps merely-restructured host modules out.
#                LINE_DIFF     -- the trojan is inlined into a host module;
#                                 the read set is the identifiers referenced
#                                 by TjIn-only lines (PIC16F84 style). Used
#                                 ONLY when the pair is a clean insertion --
#                                 if TjFree lines were also removed in bulk
#                                 the two files are separate synthesis runs
#                                 and a line diff is resynthesis noise, not
#                                 trojan logic (b15/b19/s-series netlists).
#                NAME_PATTERN  -- discriminative trojan name patterns (present
#                                 in TjIn, ZERO occurrences in TjFree), the
#                                 same discriminative rule retention_screen.py
#                                 applies to post-synthesis netlists; the read
#                                 set is the nets feeding those instances.
#
#              A literal wired into the trojan by the HARNESS TOP counts as a
#              tie-off (CONST); the same literal inside a host module is a
#              design constant (CONST_DESIGN) -- recorded, but it does not
#              decide the verdict.
#
#              VERDICTS (strict pipeline, earliest failing state wins):
#                TROJAN_STATE_FROZEN
#                    >=1 trojan state register whose every data read is
#                    CONST -- the trojan's state can never advance. Highest
#                    risk; this is the measured PIC16F84-T100 mode.
#                TROJAN_INPUTS_ALL_TIED
#                    no trojan state found, but every host signal the trojan
#                    reads is CONST.
#                TROJAN_INPUTS_PARTIALLY_TIED
#                    some host reads CONST, some LIVE.
#                TROJAN_INPUTS_LIVE
#                    no host read resolves to a constant.
#                INDETERMINATE_<reason>
#                    read set not derivable (VHDL, no RTL pair, resynthesized
#                    netlist with no discriminative names). NEVER a pass.
#
#              LIMITS -- this is a SCREENING HEURISTIC, not a synthesis
#              result. It is regex-level static analysis, not elaboration: no
#              parameter evaluation, no generate resolution, no bit-select
#              tracking (a tie-off of one bit of a read vector reports the
#              whole vector CONST only if every driver of that name is
#              constant), and VHDL is not parsed at all. `LIVE` means "not
#              provably constant", so the analysis errs toward NOT flagging.
#              It nominates designs for `screen_trojan_retention.tcl`, which
#              is the only thing that decides retention.
#
# Usage:
#   python3 wrapper_tieoff_audit.py [--bench-dir DIR] [--index corpus_index.json]
#                                   [--outdir corpus_out]

import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone

SCHEMA = "wrapper_tieoff_audit_v1"

# --- verdict states ---------------------------------------------------------
TROJAN_STATE_FROZEN = "TROJAN_STATE_FROZEN"
TROJAN_INPUTS_ALL_TIED = "TROJAN_INPUTS_ALL_TIED"
TROJAN_INPUTS_PARTIALLY_TIED = "TROJAN_INPUTS_PARTIALLY_TIED"
TROJAN_INPUTS_LIVE = "TROJAN_INPUTS_LIVE"
IND_NO_RTL = "INDETERMINATE_NO_VERILOG_PAIR"
IND_NO_READS = "INDETERMINATE_NO_READ_SET"

# Verdicts that nominate a design for the Vivado retention screen, worst first.
RISK_ORDER = [TROJAN_STATE_FROZEN, TROJAN_INPUTS_ALL_TIED,
              TROJAN_INPUTS_PARTIALLY_TIED, IND_NO_RTL, IND_NO_READS,
              TROJAN_INPUTS_LIVE]
NOMINATED = (TROJAN_STATE_FROZEN, TROJAN_INPUTS_ALL_TIED)

# Trojan name patterns. Only counted when DISCRIMINATIVE: present in TjIn and
# absent from TjFree. Mirrors retention_screen.py's post-synthesis patterns.
# ("tjin" is deliberately absent: these files carry `include` paths
# containing ".../src/TjIn/", which is discriminative but meaningless.)
TROJAN_NAME_PATTERNS = ("trojan", "tj_trig", "utj", "_tj", "muxed", "tsc",
                        "trig_en")

_VARIANT = re.compile(r"-(T|CS|CY|NC|NR|NS|RN|SL|BE|BR|BS)\d+.*$")
_VERILOG = (".v", ".sv")

# Constant literals: sized/unsized based literals, bare integers, and
# concatenations/negations of them.
_LITERAL = re.compile(r"^\s*~?\s*(?:\d+\s*)?'[bBoOdDhH][0-9a-fA-FxXzZ_?]+\s*$")
_INTEGER = re.compile(r"^\s*~?\s*\d+\s*$")
_IDENT = re.compile(r"\b([A-Za-z_]\w*)\b")

_KEYWORDS = frozenset("""
module endmodule input output inout wire reg logic integer parameter localparam
assign always initial begin end if else case casex casez endcase default for
while repeat forever posedge negedge or and not xor nand nor xnor buf bufif0
bufif1 notif0 notif1 pmos nmos cmos tran generate endgenerate genvar function
endfunction task endtask signed unsigned real time supply0 supply1 tri wand wor
specify endspecify timescale define ifdef ifndef endif include primitive
endprimitive table endtable defparam event disable fork join deassign force
release wait automatic const struct union typedef enum bit byte int longint
shortint void return break continue unique priority interface endinterface
package endpackage import export always_comb always_ff always_latch
""".split())


# --------------------------------------------------------------------------
# Verilog source handling (regex level -- see LIMITS in the header)
# --------------------------------------------------------------------------
def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def normalized_lines(text):
    """Comment-free, whitespace-collapsed, non-empty lines."""
    return [ln for ln in (re.sub(r"\s+", " ", l).strip()
                          for l in strip_comments(text).split("\n")) if ln]


def is_const_expr(expr):
    """True when expr is a literal constant, or a concatenation of them."""
    e = expr.strip()
    if not e:
        return False
    if _LITERAL.match(e) or _INTEGER.match(e):
        return True
    if e.startswith("{") and e.endswith("}"):
        inner = e[1:-1]
        parts = [p for p in split_top_level(inner, ",") if p.strip()]
        return bool(parts) and all(is_const_expr(p) for p in parts)
    return False


def split_top_level(text, sep):
    """Split on `sep` outside (), [], {}."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def identifiers(expr):
    """Identifiers in an expression, keywords and literal radices removed."""
    # Drop the digits+radix part of literals so 'h0 does not yield 'h'.
    cleaned = re.sub(r"(?:\d+\s*)?'[bBoOdDhH][0-9a-fA-FxXzZ_?]+", " ", expr)
    return [i for i in _IDENT.findall(cleaned) if i not in _KEYWORDS]


def split_modules(text):
    """[(name, header, body)] for every module in a comment-free source."""
    out = []
    for m in re.finditer(r"\bmodule\b", text):
        i, depth = m.end(), 0
        while i < len(text):
            c = text[i]
            if c in "([":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif c == ";" and depth == 0:
                break
            i += 1
        header = text[m.end():i]
        name_m = re.match(r"\s*([A-Za-z_]\w*)", header)
        if not name_m:
            continue
        end = text.find("endmodule", i)
        body = text[i + 1:end if end != -1 else len(text)]
        out.append((name_m.group(1), header, body))
    return out


class Module(object):
    """One parsed module: ports, declared nets, tie-offs, instantiations."""

    def __init__(self, name, header, body, path):
        self.name = name
        self.header = header
        self.body = body
        self.path = path
        self.ports = OrderedDict()      # port -> 'input'/'output'/'inout'/None
        self.declared = set()
        self.const_nets = set()         # provably constant
        self.driven_nets = set()        # driven by something non-constant
        self.instances = []             # (child_module, inst_name, conns)
        self.instance_nets = set()      # identifiers appearing in port maps
        self.sim_only_nets = set()      # driven only from an `initial` block
        self.has_delayed_initial = False
        self._parse_ports()
        self._parse_declarations()
        self._parse_assignments()

    # -- header / declarations ------------------------------------------
    def _parse_ports(self):
        paren = self.header[self.header.find("("):] if "(" in self.header else ""
        # ANSI style: directions inside the port list.
        for m in re.finditer(r"\b(input|output|inout)\b([^;()]*)", paren):
            direction, rest = m.group(1), m.group(2)
            rest = re.sub(r"\b(wire|reg|logic|signed|unsigned)\b", " ", rest)
            rest = re.sub(r"\[[^\]]*\]", " ", rest)
            for name in identifiers(rest):
                self.ports[name] = direction
                self.declared.add(name)
        if not self.ports and paren:
            # Non-ANSI: names only in the header, directions in the body.
            names = re.sub(r"\[[^\]]*\]", " ", paren.strip("()"))
            for name in identifiers(names):
                self.ports[name] = None
        # Body direction declarations (non-ANSI, and mixed styles).
        for m in re.finditer(r"\b(input|output|inout)\b([^;]*);", self.body):
            direction, rest = m.group(1), m.group(2)
            rest = re.sub(r"\b(wire|reg|logic|signed|unsigned)\b", " ", rest)
            rest = re.sub(r"\[[^\]]*\]", " ", rest)
            for name in identifiers(rest):
                self.ports[name] = direction
                self.declared.add(name)

    def _parse_declarations(self):
        for m in re.finditer(r"\b(wire|reg|logic)\b([^;]*);", self.body):
            rest = re.sub(r"\[[^\]]*\]", " ", m.group(2))
            # `wire x = 1'b0;` / `reg [3:0] y = 4'h0;` -- inline tie-off.
            for decl in split_top_level(rest, ","):
                if "=" in decl:
                    lhs, rhs = decl.split("=", 1)
                    names = identifiers(lhs)
                    if names:
                        self.declared.add(names[-1])
                        if is_const_expr(rhs):
                            self.const_nets.add(names[-1])
                        else:
                            self.driven_nets.add(names[-1])
                            self.declared.update(names)
                else:
                    self.declared.update(identifiers(decl))

    def _parse_assignments(self):
        for m in re.finditer(r"\bassign\b([^;]*);", self.body):
            for stmt in split_top_level(m.group(1), ","):
                if "=" not in stmt:
                    continue
                lhs, rhs = stmt.split("=", 1)
                names = identifiers(re.sub(r"\[[^\]]*\]", " ", lhs))
                if not names:
                    continue
                target = names[0]
                if is_const_expr(rhs):
                    self.const_nets.add(target)
                else:
                    self.driven_nets.add(target)
        # Procedural targets: assignment statements inside always/initial
        # blocks. Matched only at a statement boundary and with `=` not part of
        # `==`/`>=`/`<=`-as-comparison, so `if (x == 4'b1000)` is not read as a
        # driver of x -- that misread would hide every tie-off downstream.
        #
        # `always` and `initial` are kept apart on purpose. A register whose
        # ONLY procedural driver is an `initial` block has no runtime driver in
        # hardware: synthesis takes the block as a power-on value and ignores
        # its `#` delays, so simulation stimulus like
        #     reg xmitH = 1'b0; initial begin #20 xmitH = 1'b1; #10 xmitH = 1'b0; end
        # is a CONSTANT on the device. That is the fifth tie-off form, and it
        # is how the RS232 harnesses drive their DUT.
        initial_targets = set()
        for m in re.finditer(r"\b(always|initial)\b", self.body):
            kind = m.group(1)
            chunk = self.body[m.end():m.end() + 20000]
            targets = {a.group(1) for a in re.finditer(
                r"(?:^|[;)]|\bbegin\b|\belse\b|\bdo\b)\s*([A-Za-z_]\w*)\s*"
                r"(?:\[[^\]]*\])?\s*(?:<=|=)(?!=)", chunk)}
            if kind == "always":
                self.driven_nets |= targets
            else:
                initial_targets |= targets
                if "#" in chunk[:chunk.find("end") + 1 if "end" in chunk
                                else len(chunk)]:
                    self.has_delayed_initial = True
        self.sim_only_nets = initial_targets - self.driven_nets
        # A reg with a constant initializer but a real (always) driver is not
        # constant.
        self.const_nets -= self.driven_nets
        self.sim_only_nets -= self.const_nets

    # -- instantiations --------------------------------------------------
    def parse_instances(self, known_modules):
        """Find instantiations of known modules and their connections.

        One pass over the body -- a per-module-name scan would be O(modules x
        body) and these netlists reach 7 MB with 300 standard cells.
        """
        known = set(known_modules) - {self.name}
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*"
                             r"(?:\[[^\]]*\])?\s*\(", self.body):
            if m.group(1) not in known:
                continue
            i, depth = m.end() - 1, 0
            while i < len(self.body):
                c = self.body[i]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            conn_text = self.body[m.end():i]
            self.instances.append((m.group(1), m.group(2), conn_text))
            self.instance_nets.update(identifiers(conn_text))
        return self.instances


class Design(object):
    """All Verilog modules under one benchmark RTL directory."""

    def __init__(self, rtl_dir):
        self.dir = rtl_dir
        self.modules = OrderedDict()
        self.parents = defaultdict(list)   # child module -> [(parent, conns)]
        self.top = None
        self._load()
        self._link()

    def _load(self):
        if not os.path.isdir(self.dir):
            return
        for fn in sorted(os.listdir(self.dir)):
            if not fn.lower().endswith(_VERILOG):
                continue
            path = os.path.join(self.dir, fn)
            try:
                with open(path, errors="ignore") as fh:
                    text = strip_comments(fh.read())
            except OSError:
                continue
            for name, header, body in split_modules(text):
                if name not in self.modules:
                    self.modules[name] = Module(name, header, body, fn)
        if "top" in self.modules:
            self.top = "top"
        elif self.modules:
            # Fall back to the module nobody instantiates.
            self.top = None

    def _link(self):
        known = list(self.modules)
        for mod in self.modules.values():
            for child, _inst, conn_text in mod.parse_instances(known):
                conns = self._connections(child, conn_text)
                self.parents[child].append((mod.name, conns))
        if self.top is None:
            instantiated = set(self.parents)
            roots = [n for n in self.modules if n not in instantiated]
            self.top = roots[0] if roots else None

    def _connections(self, child, conn_text):
        """port -> actual expression, for named or positional connections."""
        conns = {}
        parts = [p for p in split_top_level(conn_text, ",") if p.strip()]
        if any(p.strip().startswith(".") for p in parts):
            for p in parts:
                m = re.match(r"\s*\.\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", p,
                             flags=re.S)
                if m:
                    conns[m.group(1)] = m.group(2)
        else:
            ports = list(self.modules[child].ports) if child in self.modules \
                else []
            for port, expr in zip(ports, parts):
                conns[port] = expr
        return conns

    # -- hierarchical constant resolution --------------------------------
    def resolve(self, mod_name, signal, seen=None):
        """CONST / LIVE / UNKNOWN for `signal` as seen inside `mod_name`.

        CONST requires a constant along EVERY instantiation path, so a
        tie-off above the trojan's own module still counts. LIVE means "not
        provably constant" -- the analysis errs toward not flagging.
        """
        seen = seen or frozenset()
        key = (mod_name, signal)
        if key in seen:
            return "UNKNOWN"
        seen = seen | {key}
        mod = self.modules.get(mod_name)
        if mod is None:
            return "UNKNOWN"
        if signal in mod.const_nets:
            return "CONST"
        if signal in mod.sim_only_nets:
            return "CONST_SIM_ONLY"
        if signal in mod.driven_nets:
            return "LIVE"
        direction = mod.ports.get(signal, "__absent__")
        if direction in ("input", None):
            parents = self.parents.get(mod_name, [])
            if not parents:
                # Unconnected top-level input: driven from outside (clk).
                return "LIVE" if mod_name == self.top else "UNKNOWN"
            votes = set()
            for parent, conns in parents:
                expr = conns.get(signal)
                if expr is None:
                    votes.add("UNKNOWN")
                    continue
                if is_const_expr(expr):
                    votes.add("CONST")
                    continue
                ids = identifiers(expr)
                if not ids:
                    votes.add("UNKNOWN")
                    continue
                sub = {self.resolve(parent, i, seen) for i in ids}
                if sub == {"CONST"}:
                    votes.add("CONST")
                elif "LIVE" in sub:
                    votes.add("LIVE")
                else:
                    votes.add("UNKNOWN")
            if votes == {"CONST"}:
                return "CONST"
            return "LIVE" if "LIVE" in votes else "UNKNOWN"
        if signal in mod.declared:
            return "LIVE"
        if signal in mod.instance_nets:
            # Implicit net in a gate-level netlist: driven by some cell, so
            # not provably constant. Checked last so tie-offs still win.
            return "LIVE"
        return "UNKNOWN"


# --------------------------------------------------------------------------
# read-set extraction
# --------------------------------------------------------------------------
def is_tied(state):
    """Constant on the device. CONST_DESIGN is a design constant, not a
    tie-off, so it is deliberately excluded."""
    return state in ("CONST", "CONST_SIM_ONLY")


def is_clock_or_reset(name):
    n = name.lower()
    return bool(re.search(r"clk|clock|rst|reset|clr|_n$|pon", n))


_LABEL_SUFFIX = re.compile(
    r"(_?benign|_?trojan|_?tjin|_?tjfree|_?tj|_?free)$", re.I)


def base_name(name):
    """Module name with a label suffix stripped: aes_128_trojan -> aes_128."""
    return _LABEL_SUFFIX.sub("", name) or name


def line_multiset(text):
    return Counter(normalized_lines(text))


def pair_modules(tjin, tjfree):
    """Match TjIn modules to their TjFree counterparts.

    Three rules, in order: identical name; identical name after stripping a
    label suffix (`uart` <-> `uart_benign`, `aes_128_trojan` <-> `aes_128`);
    body-line similarity above 0.6 for whatever is left. Unpaired TjIn
    modules are candidates for being trojan modules.
    """
    pairs, used = OrderedDict(), set()
    free_by_base = defaultdict(list)
    for n in tjfree.modules:
        free_by_base[base_name(n).lower()].append(n)
    for n in tjin.modules:
        if n in tjfree.modules:
            pairs[n] = n
            used.add(n)
    for n in tjin.modules:
        if n in pairs:
            continue
        cands = [c for c in free_by_base.get(base_name(n).lower(), [])
                 if c not in used]
        if cands:
            pairs[n] = cands[0]
            used.add(cands[0])
    unpaired = [n for n in tjin.modules if n not in pairs]
    if unpaired:
        free_lines = {n: line_multiset(m.body)
                      for n, m in tjfree.modules.items() if n not in used}
        for n in list(unpaired):
            mine = line_multiset(tjin.modules[n].body)
            if not mine:
                continue
            best, best_j = None, 0.0
            for fn, other in free_lines.items():
                if not other:
                    continue
                inter = sum((mine & other).values())
                union = sum((mine | other).values())
                j = inter / union if union else 0.0
                if j > best_j:
                    best, best_j = fn, j
            if best is not None and best_j >= 0.6:
                pairs[n] = best
                used.add(best)
                unpaired.remove(n)
    return pairs, unpaired


def trojan_module_reads(tjin, unpaired):
    """TROJAN_MODULE: unpaired TjIn modules whose NAME is trojan-marked.

    Requiring the name marker keeps host modules that merely have no TjFree
    counterpart (a restructured benign release) out of the read set -- those
    are handled by LINE_DIFF or reported INDETERMINATE instead.
    """
    trojan_modules = [n for n in unpaired
                      if any(p in n.lower() for p in TROJAN_NAME_PATTERNS)
                      and n != tjin.top]
    reads, sites = [], []
    for tname in trojan_modules:
        tmod = tjin.modules[tname]
        inputs = [p for p, d in tmod.ports.items() if d in ("input", None)]
        for parent, conns in tjin.parents.get(tname, []):
            sites.append({"trojan_module": tname, "parent": parent})
            for port in inputs:
                expr = conns.get(port)
                if expr is None:
                    continue
                if is_const_expr(expr):
                    # A literal wired in by the HARNESS is a tie-off; the same
                    # literal inside a host module is a design constant (a
                    # round constant, a width filler) and must not be read as
                    # one -- that misread made every AES benchmark, whose
                    # trojan is measured retained, look partially tied.
                    reads.append({"module": parent, "signal": expr.strip(),
                                  "port": "%s.%s" % (tname, port),
                                  "state": "CONST" if parent == tjin.top
                                  else "CONST_DESIGN"})
                    continue
                for sig in dict.fromkeys(identifiers(expr)):
                    reads.append({"module": parent, "signal": sig,
                                  "port": "%s.%s" % (tname, port),
                                  "state": tjin.resolve(parent, sig)})
    return trojan_modules, reads, sites


def inline_diff_reads(tjin, tjfree, pairs):
    """LINE_DIFF: trojan inlined into a paired module.

    Per paired module: TjIn-only lines are the insertion. Valid ONLY for a
    clean insertion -- if TjFree lines were also removed in bulk, the two
    bodies are separate synthesis runs and the diff is resynthesis noise, not
    trojan logic (b15/b19 ship `*_extracted`/`*_eco` netlists against
    independently synthesized `*_scan` ones). Reporting that noise as a read
    set would manufacture verdicts, so the pair is rejected instead.
    """
    reads, info, added_by_module = [], [], {}
    for in_name, free_name in pairs.items():
        mod = tjin.modules[in_name]
        a = line_multiset(mod.body)
        b = line_multiset(tjfree.modules[free_name].body)
        added, removed = a - b, b - a
        n_added, n_removed = sum(added.values()), sum(removed.values())
        n_free = max(sum(b.values()), 1)
        clean = n_removed <= max(10, 0.02 * n_free)
        rec = {"module": in_name, "tjfree_module": free_name,
               "added_lines": n_added, "removed_lines": n_removed,
               "tjfree_lines": n_free, "clean_insertion": clean}
        if not n_added:
            continue
        info.append(rec)
        if not clean:
            continue
        added_text = "\n".join(added.elements())
        added_by_module[in_name] = added_text
        # Signals DECLARED by the added lines are trojan-internal.
        trojan_decls = set()
        for m in re.finditer(r"\b(wire|reg|logic)\b([^;]*);", added_text):
            trojan_decls.update(
                identifiers(re.sub(r"\[[^\]]*\]", " ", m.group(2))))
        # Instance names introduced by the added lines are not signals.
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(",
                             added_text):
            if m.group(1) not in _KEYWORDS and m.group(2) not in _KEYWORDS:
                trojan_decls.add(m.group(2))
        referenced = set()
        for ln in added.elements():
            referenced.update(identifiers(ln))
        rec["trojan_declarations"] = sorted(trojan_decls)[:40]
        for sig in sorted(referenced - trojan_decls):
            if sig not in mod.declared and sig not in mod.ports:
                continue
            reads.append({"module": in_name, "signal": sig, "port": None,
                          "state": tjin.resolve(in_name, sig)})
    return reads, info, added_by_module


def name_pattern_reads(tjin, tjfree, tjin_text, tjfree_text):
    """NAME_PATTERN: discriminative trojan names; read the nets feeding them.

    Discriminative = the pattern occurs in TjIn and NOT in TjFree, the same
    rule retention_screen.py applies to post-synthesis netlists. Only the
    ACTUAL connection expressions are read, never the cell's port names.
    """
    lo_in, lo_free = tjin_text.lower(), tjfree_text.lower()
    disc = [p for p in TROJAN_NAME_PATTERNS if p in lo_in and p not in lo_free]
    if not disc:
        return disc, []
    reads = []
    for name, mod in tjin.modules.items():
        for child, inst, conn_text in mod.instances:
            if not any(p in inst.lower() or p in child.lower() for p in disc):
                continue
            conns = tjin._connections(child, conn_text)
            exprs = list(conns.values()) if conns else [conn_text]
            for expr in exprs:
                if is_const_expr(expr):
                    reads.append({"module": name, "signal": expr.strip(),
                                  "port": "%s/%s" % (child, inst),
                                  "state": "CONST" if name == tjin.top
                                  else "CONST_DESIGN"})
                    continue
                for sig in dict.fromkeys(identifiers(expr)):
                    reads.append({"module": name, "signal": sig,
                                  "port": "%s/%s" % (child, inst),
                                  "state": tjin.resolve(name, sig)})
    return disc, reads


def dedupe_reads(reads):
    out, seen = [], set()
    for r in reads:
        key = (r["module"], r["signal"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# --------------------------------------------------------------------------
# freeze analysis + verdict
# --------------------------------------------------------------------------
def frozen_state_registers(added_text, reads):
    """Trojan state registers whose every data read is CONST or frozen.

    A sequential trojan construct reading only constants (clock and reset
    aside) can never leave its initial state, which is why synthesis deletes
    it -- the measured PIC16F84-T100 mechanism. Freezing propagates: a
    register whose next state depends only on constants and already-frozen
    registers is itself frozen, iterated to a fixpoint.
    """
    if not added_text:
        return [], []
    state_regs = set()
    for m in re.finditer(r"\breg\b([^;]*);", added_text):
        state_regs.update(identifiers(re.sub(r"\[[^\]]*\]", " ", m.group(1))))
    if not state_regs:
        return [], []
    by_sig = {r["signal"]: r["state"] for r in reads}

    blocks = []
    for m in re.finditer(r"\balways\b", added_text):
        chunk = added_text[m.end():]
        # The block ends at the next concurrent construct -- stopping only at
        # the next `always` would pull a following `assign` into the block and
        # its host reads would mask the freeze.
        nxt = re.search(r"\b(always|initial|assign|endmodule)\b", chunk)
        block = chunk[:nxt.start()] if nxt else chunk
        targets = {a.group(1) for a in re.finditer(
            r"(?:^|[;)]|\bbegin\b|\belse\b)\s*([A-Za-z_]\w*)\s*"
            r"(?:\[[^\]]*\])?\s*(?:<=|=)(?!=)", block)}
        driven = state_regs & targets
        if not driven:
            continue
        reads_in_block = [s for s in dict.fromkeys(identifiers(block))
                          if not is_clock_or_reset(s) and s not in driven]
        blocks.append((driven, reads_in_block))

    frozen, live = set(), set()
    for _ in range(len(blocks) + 1):
        changed = False
        for driven, block_reads in blocks:
            data = [s for s in block_reads if s in by_sig or s in state_regs]
            if not data:
                continue
            if all(is_tied(by_sig.get(s)) or s in frozen for s in data):
                if driven - frozen:
                    frozen |= driven
                    changed = True
            else:
                live |= driven
        if not changed:
            break
    # A register frozen by one block and driven live by another is not frozen.
    return sorted(frozen - live), sorted(live)


def classify(reads, frozen_regs, method, has_rtl_pair):
    """Pure verdict function -- drives the synthetic tests."""
    if not has_rtl_pair:
        return IND_NO_RTL
    if frozen_regs:
        return TROJAN_STATE_FROZEN
    data = [r for r in reads if not is_clock_or_reset(r["signal"])
            and r["state"] != "CONST_DESIGN"]
    if not data:
        return IND_NO_READS
    states = {r["state"] for r in data}
    if all(is_tied(s) for s in states):
        return TROJAN_INPUTS_ALL_TIED
    if any(is_tied(s) for s in states):
        return TROJAN_INPUTS_PARTIALLY_TIED
    if states == {"UNKNOWN"}:
        return IND_NO_READS
    return TROJAN_INPUTS_LIVE


def harness_tieoff_stats(tjin):
    """How much of the DUT's input surface the harness holds constant.

    `quiescent` = every non-clock/reset input of the largest DUT instance is
    constant on the device, so no live data ever enters the design.

    Quiescence is reported as a DATASET FINDING, never as a nomination:
    b15-T200's harness is quiescent at its input surface and its trojan is
    nevertheless measured retained, because that trojan taps an internal net
    of a state machine that runs off the clock alone. Quiescent inputs make a
    DATA-triggered trojan unable to fire; they say nothing about a
    clock-counter trojan.
    """
    top = tjin.top
    if top is None or top not in tjin.modules:
        return {}
    out = []
    for child, inst, _conn in tjin.modules[top].instances:
        cmod = tjin.modules.get(child)
        if cmod is None:
            continue
        inputs = [p for p, d in cmod.ports.items() if d in ("input", None)]
        data_inputs = [p for p in inputs if not is_clock_or_reset(p)]
        if not inputs:
            continue
        states = {p: tjin.resolve(child, p) for p in data_inputs}
        tied = [p for p, s in states.items() if is_tied(s)]
        sim_only = [p for p, s in states.items() if s == "CONST_SIM_ONLY"]
        out.append({"instance": inst, "module": child,
                    "n_inputs": len(inputs),
                    "n_data_inputs": len(data_inputs),
                    "n_tied_const": len(tied),
                    "n_sim_only": len(sim_only),
                    "all_data_inputs_tied": bool(data_inputs) and
                    len(tied) == len(data_inputs),
                    "tied": sorted(tied)[:24]})
    out.sort(key=lambda d: -d["n_inputs"])
    quiescent = bool(out) and out[0]["all_data_inputs_tied"]
    return {"dut_instances": out[:4], "quiescent": quiescent,
            "delayed_initial_stimulus":
            tjin.modules[top].has_delayed_initial}


def audit_benchmark(bench_dir):
    """One benchmark directory -> verdict record."""
    tjin_dir = os.path.join(bench_dir, "src", "TjIn")
    tjfree_dir = os.path.join(bench_dir, "src", "TjFree")
    rec = {"benchmark": os.path.basename(bench_dir)}

    def vfiles(d):
        return sorted(f for f in os.listdir(d)
                      if f.lower().endswith(_VERILOG)) \
            if os.path.isdir(d) else []

    in_files, free_files = vfiles(tjin_dir), vfiles(tjfree_dir)
    if not in_files or not free_files:
        rec.update({"verdict": IND_NO_RTL, "method": None,
                    "reason": "no Verilog pair (TjIn=%d, TjFree=%d files)"
                              % (len(in_files), len(free_files)),
                    "reads": [], "frozen_state_regs": []})
        return rec

    tjin, tjfree = Design(tjin_dir), Design(tjfree_dir)

    def concat(d, files):
        parts = []
        for f in files:
            try:
                with open(os.path.join(d, f), errors="ignore") as fh:
                    parts.append(fh.read())
            except OSError:
                pass
        return "\n".join(parts)

    tjin_text, tjfree_text = concat(tjin_dir, in_files), \
        concat(tjfree_dir, free_files)

    pairs, unpaired = pair_modules(tjin, tjfree)
    methods, reads, extra = [], [], {}

    trojan_modules, m_reads, sites = trojan_module_reads(tjin, unpaired)
    if m_reads:
        methods.append("TROJAN_MODULE")
        reads += m_reads
    extra["trojan_modules"] = trojan_modules
    extra["instantiation_sites"] = sites
    extra["unpaired_tjin_modules"] = unpaired[:20]

    l_reads, l_info, added_by_module = inline_diff_reads(tjin, tjfree, pairs)
    if l_reads:
        methods.append("LINE_DIFF")
        reads += l_reads
    extra["line_diff"] = l_info[:8]

    disc, n_reads = name_pattern_reads(tjin, tjfree, tjin_text, tjfree_text)
    extra["discriminative_name_patterns"] = disc
    if n_reads:
        methods.append("NAME_PATTERN")
        reads += n_reads

    reads = dedupe_reads(reads)
    frozen, live_regs = [], []
    for _mod, added_text in added_by_module.items():
        f, l = frozen_state_registers(added_text, reads)
        frozen += f
        live_regs += l
    frozen = sorted(set(frozen) - set(live_regs))

    method = "+".join(methods) if methods else None
    verdict = classify(reads, frozen, method, True)
    state_counts = Counter(r["state"] for r in reads
                           if not is_clock_or_reset(r["signal"]))
    rec.update({
        "verdict": verdict,
        "method": method,
        "n_modules_tjin": len(tjin.modules),
        "top_module": tjin.top,
        "reads": reads[:60],
        "n_reads": len(reads),
        "read_state_counts": dict(state_counts),
        "frozen_state_regs": frozen,
        "live_state_regs": live_regs,
        "harness": harness_tieoff_stats(tjin),
    })
    rec.update(extra)
    return rec


# --------------------------------------------------------------------------
# corpus cross-reference (Phase 0.5C step 3)
# --------------------------------------------------------------------------
def corpus_exposure(records, index_path):
    """Malicious corpus files behind nominated benchmarks.

    Answers "how many additional files are malicious-label / no-live-trojan
    candidates that the 169-file payload-identity quarantine does not
    catch?" -- an UPPER BOUND from a heuristic, not a measurement.
    """
    if not os.path.exists(index_path):
        return {"available": False, "index": index_path}
    with open(index_path) as fh:
        index = json.load(fh)
    by_key = defaultdict(lambda: {"malicious": 0, "benign": 0,
                                  "quarantined": 0, "payloads": set()})
    for r in index["files"]:
        e = by_key[r["design_key"]]
        e["malicious" if r["label"] == 1 else "benign"] += 1
        e["quarantined"] += bool(r["quarantined"])
        if r["label"] == 1:
            e["payloads"].add(r["payload_id"])

    per_key, totals = {}, Counter()
    for rec in records:
        key = rec["benchmark"].replace("-", "_")
        if key not in by_key:
            continue
        e = by_key[key]
        row = {"verdict": rec["verdict"],
               "malicious_files": e["malicious"],
               "benign_files": e["benign"],
               "quarantined": e["quarantined"],
               "unique_malicious_payloads": len(e["payloads"])}
        per_key[key] = row
        if rec["verdict"] in NOMINATED:
            totals["nominated_design_keys"] += 1
            totals["nominated_malicious_files"] += e["malicious"]
            totals["already_quarantined"] += e["quarantined"]
            totals["nominated_unique_payloads"] += len(e["payloads"])
    totals["additional_beyond_quarantine"] = (
        totals["nominated_malicious_files"] - totals["already_quarantined"])
    return {"available": True, "index": index_path,
            "manifest_id": index.get("manifest_id"),
            "totals": dict(totals), "per_design_key": per_key}


# --------------------------------------------------------------------------
# validation against the measured pilot outcomes
# --------------------------------------------------------------------------
# rebuild_pilot/REBUILD_PILOT_REPORT.md, corpus_out/retention_screen.json.
PILOT_TRUTH = {
    "PIC16F84-T100": "deleted",   # NO_TRACE_AFTER_SYNTHESIS (measured)
    "AES-T1000": "retained",      # TROJAN_RETAINED, 168 cells
    "b15-T200": "retained",       # TROJAN_RETAINED, 5 cells + 74 muxed nets
}


def validate(records):
    """The screen must not contradict the three Vivado-measured outcomes."""
    by_bench = {r["benchmark"]: r for r in records}
    rows, ok = [], True
    for bench, truth in sorted(PILOT_TRUTH.items()):
        rec = by_bench.get(bench)
        verdict = rec["verdict"] if rec else "MISSING"
        if truth == "deleted":
            agrees = verdict in NOMINATED
        else:
            # A retained trojan must NOT be nominated as starved.
            agrees = verdict not in NOMINATED
        ok = ok and agrees
        rows.append({"benchmark": bench, "measured": truth,
                     "verdict": verdict, "agrees": agrees})
    return ok, rows


def main():
    p = argparse.ArgumentParser(
        description="Phase 0.5C corpus-wide harness tie-off audit")
    p.add_argument("--bench-dir", default=os.path.expanduser(
        "~/Desktop/Karakchi-Research/trusthub_benchmarks"))
    p.add_argument("--index",
                   default=os.path.join("corpus_out", "corpus_index.json"))
    p.add_argument("--outdir", default="corpus_out")
    args = p.parse_args()

    if not os.path.isdir(args.bench_dir):
        sys.exit("benchmark tree not found: %s" % args.bench_dir)
    benches = [d for d in sorted(os.listdir(args.bench_dir))
               if os.path.isdir(os.path.join(args.bench_dir, d, "src", "TjIn"))]
    print("=== Phase 0.5C harness tie-off audit ===")
    print("%d trojan benchmark directories in %s\n"
          % (len(benches), args.bench_dir))

    records = []
    for b in benches:
        rec = audit_benchmark(os.path.join(args.bench_dir, b))
        rec["host"] = _VARIANT.sub("", b)
        records.append(rec)
        print("  %-24s %-30s %s" % (b, rec["verdict"], rec["method"] or "-"))

    print("\nVERDICT DISTRIBUTION (benchmark directories)")
    counts = Counter(r["verdict"] for r in records)
    for v in RISK_ORDER:
        if counts.get(v):
            print("    %-32s %4d" % (v, counts[v]))
    for v, c in counts.items():
        if v not in RISK_ORDER:
            print("    %-32s %4d" % (v, c))

    n_quiescent = sum(1 for r in records
                      if (r.get("harness") or {}).get("quiescent"))
    n_delayed = sum(1 for r in records
                    if (r.get("harness") or {}).get("delayed_initial_stimulus"))
    print("\nHARNESS INPUT SURFACE (dataset finding, NOT a nomination)")
    print("    harnesses supplying NO live data to the DUT : %d/%d"
          % (n_quiescent, len(records)))
    print("    harnesses whose stimulus is an `initial` block with delays"
          " (simulation-only): %d/%d" % (n_delayed, len(records)))
    print("    b15-T200 is quiescent at its input surface and its trojan is")
    print("    MEASURED RETAINED, so quiescence alone does not imply the")
    print("    trojan is dead -- it only rules out DATA-triggered activation.")

    print("\nPER HOST (worst verdict over its benchmarks)")
    by_host = defaultdict(list)
    for r in records:
        by_host[r["host"]].append(r)
    host_verdict = {}
    for h, rs in sorted(by_host.items()):
        worst = min((r["verdict"] for r in rs),
                    key=lambda v: RISK_ORDER.index(v)
                    if v in RISK_ORDER else len(RISK_ORDER))
        nominated = [r["benchmark"] for r in rs if r["verdict"] in NOMINATED]
        host_verdict[h] = {"worst_verdict": worst, "n_benchmarks": len(rs),
                           "nominated": nominated}
        print("    %-18s %-30s %d/%d nominated"
              % (h, worst, len(nominated), len(rs)))

    ok, rows = validate(records)
    print("\nVALIDATION against Vivado-measured pilot outcomes")
    for r in rows:
        print("    %-16s measured=%-9s verdict=%-28s %s"
              % (r["benchmark"], r["measured"], r["verdict"],
                 "OK" if r["agrees"] else "CONTRADICTS"))
    print("    -> %s" % ("consistent with all three measured outcomes" if ok
                         else "CONTRADICTION -- screen is wrong, do not use"))

    exposure = corpus_exposure(records, args.index)
    if exposure.get("available"):
        t = exposure["totals"]
        print("\nCORPUS EXPOSURE (nominated = %s)" % ", ".join(NOMINATED))
        print("    nominated design keys           : %d"
              % t.get("nominated_design_keys", 0))
        print("    malicious files behind them     : %d"
              % t.get("nominated_malicious_files", 0))
        print("    unique malicious payloads       : %d"
              % t.get("nominated_unique_payloads", 0))
        print("    already quarantined (169-file)  : %d"
              % t.get("already_quarantined", 0))
        print("    ADDITIONAL beyond the quarantine: %d"
              % t.get("additional_beyond_quarantine", 0))
        print("    NOTE: heuristic nomination, an upper bound. Only the")
        print("    Vivado retention screen decides retention.")
    else:
        print("\nCORPUS EXPOSURE: index not found (%s) -- skipped"
              % exposure.get("index"))

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "bench_dir": args.bench_dir,
        "n_benchmarks": len(records),
        "verdict_counts": dict(counts),
        "harness_input_surface": {
            "n_quiescent": n_quiescent,
            "n_delayed_initial_stimulus": n_delayed,
            "n_benchmarks": len(records),
            "interpretation": (
                "quiescent = every non-clock/reset DUT input is constant on "
                "the device, so no live data enters the design. Reported as a "
                "dataset finding, NOT a nomination: b15-T200 is quiescent and "
                "its trojan is measured retained (it taps an internal net of "
                "a clock-driven state machine). Quiescence rules out "
                "DATA-triggered activation only."),
        },
        "risk_order": RISK_ORDER,
        "nominated_verdicts": list(NOMINATED),
        "validation": {"consistent_with_pilot": ok, "rows": rows,
                       "pilot_truth": PILOT_TRUTH},
        "per_host": host_verdict,
        "corpus_exposure": exposure,
        "per_benchmark": records,
        "method": {
            "tieoff_forms": ["assign net = const", "wire net = const",
                             "reg net = const with no other driver",
                             "constant in instantiation port map"],
            "read_set_methods": ["MODULE_DIFF", "LINE_DIFF", "NAME_PATTERN"],
            "constant_rule": ("CONST requires a constant along every "
                              "instantiation path to the harness top; LIVE "
                              "means not provably constant"),
            "limitation": ("regex-level static analysis, not elaboration: no "
                           "parameter/generate evaluation, no bit-select "
                           "tracking, VHDL not parsed. Nominates designs for "
                           "screen_trojan_retention.tcl; proves nothing about "
                           "retention on its own."),
        },
    }
    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, "wrapper_tieoff_audit.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2, default=list)
    print("\naudit -> %s" % path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
