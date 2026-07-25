# Rebuild Pilot Report — Phase 0.5B

**Status: BLOCKED BEFORE BUILDING (2026-07-25).** No build was attempted, per
the standing instruction to stop if Vivado 2023.2 cannot be confirmed.

## Blocker

Vivado does not run on macOS, so the local machine
(`carters-mbp-2.lan`) cannot build. Both candidate build hosts —
`higgs.cse.sc.edu` (project's designated compute host) and
`meson.cse.sc.edu` (named for this pilot; present in known_hosts) — resolve
in DNS but have TCP/22 **filtered from the current network** (campus
firewall; VPN or on-campus access required). Vivado presence, exact version,
and license state on those hosts are therefore **unknown**, and no
alternative Vivado release may be substituted. Full inventory:
[environment_inventory.json](environment_inventory.json).

**To unblock:** from a campus/VPN connection, on the build host:

1. `vivado -mode batch -source rebuild_pilot/capture_vivado_env.tcl`
   → captures `version`, `help place_design`, `help route_design`,
   `help phys_opt_design`, `help write_bitstream`, and the documented
   place/route directive lists (plus, with the project open,
   `report_property -all [get_runs impl_1]`).
2. Confirm the version is **2023.2** — the eligible non-ISCAS85 corpus was
   built with 2023.2 and the audit showed a tool-version change is itself a
   label channel (LEAKAGE_AUDIT.md Finding 5). Do not proceed under any
   other release.
3. Proceed with the pilot exactly as specified below.

## Selected host designs (criteria applied, ready to build)

All three: benign (`src/TjFree`) and malicious (`src/TjIn`) RTL present in
`~/Desktop/Karakchi-Research/trusthub_benchmarks/`; malicious variant is
**not** one of the 169 audited no-bitstream-trace cases; trojan logic is
name-identifiable for post-synthesis retention checks.

| design | family | size class | why |
|---|---|---|---|
| **PIC16F84-T100** | MCU/CPU | small | The only family with zero quarantined files besides ITC99; small RISC core keeps build times short for matrix debugging; trojan instances named `Trojan*` in `TjIn/risc16f84.v`/`top.v`. |
| **b15-T200** | ITC99 | medium | ITC99 has zero no-trace cases; b15 is a mid-size processor benchmark; trojan nets named `Trojan*` in the `TjIn` netlist. Note: `TjIn` ships ASIC ECO collateral (.def/.sdc/.spef) alongside the netlist — confirm the Verilog netlist used for the V4 corpus builds before synthesis. |
| **AES-T1000** | CRYPTO | large | CRYPTO's only no-trace case is AES_T200 (excluded); AES-T1000's V4 trojan build differs from its benign build in 3,939/10,008 frames (measured), so the trojan demonstrably reaches the bitstream; explicit trojan hierarchy (`TSC`, `Trojan_Trigger`, `aes_128_trojan`, `expand_key_128_trojan`) makes retention checks unambiguous. |

Three designs, three eligible families (MCU/CPU, ITC99, CRYPTO),
small/medium/large. COMMS, BUS/DISPLAY, ISCAS89 were avoided because their
malicious builds are dominated by no-trace quarantine cases (60 RS232 + 38
Ethernet + 50 ISCAS89 + 15 wb_conmax/vga_lcd of the 169).

## Pilot procedure (fixed; awaiting environment)

Per design and label (`TjFree` / `TjIn`), all under **one** Vivado 2023.2
installation, part `xc7z020clg400-1`, the same XDC, and the same bitstream
settings:

1. **Synthesize once per label**; write the post-synthesis DCP; every
   implementation variant re-opens that DCP, so the matrix isolates P&R
   variation from synthesis variation.
2. **Trojan retention (post-synth):** enumerate cells/nets matching the
   design's trojan name patterns (`Trojan*`, `TSC*`, `*_trojan`); record the
   list. If synthesis already removed them, record that and do **not** add
   DONT_TOUCH/KEEP silently — that is a separate, documented intervention
   requiring its own matched benign control.
3. **Implementation matrix — four configurations**, identical for both
   labels, drawn **only** from the captured directive lists (candidates to
   validate against the capture, not assumptions:
   `place_design` Default / Explore / ExtraNetDelay_high /
   AltSpreadLogic_high crossed with matching `route_design` Default /
   Explore). `place_design -seed` is **not assumed to exist** and may only
   be used if `help place_design` in the captured 2023.2 shell documents it.
4. **Per successful build, produce:** `.bit`; FDRI payload digest +
   exact-payload class (audited parser); post-route DCP; timing summary;
   utilization report; the full strategy/directive arguments; build log +
   exit status; source revision + constraints hash; Vivado version/build;
   part; `.ll` logic-location file via the supported `write_bitstream
   -logic_location_file`; and a `pilot_manifest.json` entry linking the
   benign/malicious pair and the implementation configuration.
5. **Trojan retention (post-route):** the post-synth trojan cells must
   survive in the routed netlist; a malicious build whose FDRI payload is
   byte-identical to its matched benign build is **flagged invalid**
   (no-trace), echoing the audit's Finding 4 mechanism.
6. **Configuration diversity:** compare FDRI payloads (never whole-file
   hashes — the header timestamp makes those always differ);
   exact-byte-confirm every proposed duplicate; report unique payloads per
   design/label; report which matrix configurations actually changed the
   payload. A timestamp-only difference is not a variant.
7. **Grouping rule:** all implementation variants of one host design belong
   to ONE split group forever. Variants add P&R diversity; they do **not**
   add independent host designs — the corpus's effective size for grouped
   splits grows only with new designs.
8. Pilot outputs are for feasibility measurement only — never for training a
   final model.

**Success criteria** (unchanged from the approved instruction): ≥2/3 designs
build in both classes; every successful malicious build has a
configuration-level trace vs its matched benign build; ≥3 distinct FDRI
payloads per successful design/label or documented evidence the supported
matrix is deterministic for that design; complete provenance on every
artifact; no tool-version mixing; no filename-based independence. If the
matrix produces duplicate payloads, the outcome is a *diagnosis* plus a
proposed next perturbation — not a blind campaign expansion.

## Feasibility assessment for a full campaign

- **Scientifically necessary:** yes. The corrected corpus has 36 unique
  benign payloads and 15 non-ISCAS85 components; the primary grouped regime
  is NOT ESTIMABLE. Only new, matched, trace-bearing configurations change
  that.
- **Scientifically sufficient (pilot will test):** unknown — the V4 corpus
  itself shows the directive sweep often produced byte-identical payloads
  (Vivado implementation is deterministic given identical inputs/settings),
  which is exactly what the pilot's diversity check measures. If the
  4-configuration matrix yields <3 distinct payloads per design/label, the
  documented next perturbations to propose are: differing
  `phys_opt_design` step combinations from the captured strategy list, and
  benign logical perturbations with matched controls — each as its own
  controlled intervention, pending approval.
- **Operationally:** blocked on campus network access; otherwise modest
  (3 designs × 2 labels × (1 synth + 4 impl) = 30 runs ≈ a day of build
  time for these design sizes on a typical host).

## Artifacts in this directory

- `environment_inventory.json` — machine/remote/toolchain inventory (this
  session).
- `header_leak_verification.json` — Finding 5 verification (this session).
- `capture_vivado_env.tcl` — to run on the build host (next session).
- NOT present, because no build ran: `pilot_manifest.json`,
  `pilot_results.csv`, `payload_distinctness.json`,
  `matched_pair_frame_diffs.csv`, build logs, utilization/timing summaries,
  `.ll` files. They are deliberately absent rather than stubbed.
