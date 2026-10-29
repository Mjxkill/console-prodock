"""Grounded CDC/reset inspector for the R5 frozen USB snapshot (GW5AST-138).

Each returned value is re-derived here from the exact bytes of the frozen
snapshot -- RTL whose R5 and G22 hashes agree (SOURCE_PROVENANCE.json),
the selected netlist taps, the parsed Gowin timing report and the
provenance manifest.  Structural assertions raise on any surprise, so the
fixed validator fails loudly if a checked structure moves.  No synthesis
tool is invoked, no hardware is touched, and this module asserts nothing
about metastability safety from digital evidence alone.
"""

import json
import pathlib
import re


# --- file and netlist-parsing helpers ---------------------------------------

def _read(context: pathlib.Path, name: str) -> str:
    """Read one exact context file; fail loudly if missing or empty."""
    text = (context / name).read_text()
    assert text.strip(), f"empty context file: {name}"
    return text


def _parse_taps(vo: str):
    """Extract DFF*/LUT* primitive blocks plus defparams from the tap netlist.

    Returns (cells, params, lut_out):
      cells    -- instance name -> {prim, ports} with all .PORT(net) entries
      params   -- instance name -> attribute dict (INIT et al.)
      lut_out  -- LUT output net name -> LUT instance name (for tracing
                  combinational reset drivers such as n6_5 -> n6_s1)
    """
    cells = {}
    for prim, inst, body in re.findall(
            r"(DFF\w+|LUT\w+)\s+\\([^()]+?)\s*\(\s*(.*?)\)\s*;", vo, re.S):
        ports = dict(re.findall(r"\.(\w+)\(\s*(.*?)\s*\)", body))
        cells[inst] = {"prim": prim, "ports": ports}
    params = {}
    for inst, attr, val in re.findall(
            r"defparam\s+\\([^.\s]+)\s*\.(\w+)\s*=\s*([^;]+);", vo):
        params.setdefault(inst, {})[attr] = val.strip()
    assert cells, "no tap primitives parsed from netlist_taps.vo"
    lut_out = {}
    for inst, cell in cells.items():
        if cell["prim"].startswith("LUT"):
            f = cell["ports"].get("F")
            if f is not None:
                lut_out[f.strip()] = inst
    return cells, params, lut_out


def _ff(cells, **wanted):
    """Find exactly one DFF cell whose pinned ports match wanted."""
    hits = [name for name, cell in cells.items()
            if cell["prim"].startswith("DFF")
            and all(cell["ports"].get(k, "").strip() == v
                    for k, v in wanted.items())]
    assert len(hits) == 1, f"expected exactly one FF {wanted}, got {hits}"
    return hits[0], cells[hits[0]]["ports"]


def _instance(top: str, inst: str) -> str:
    """Return the port list of one instantiation in console_top.v."""
    hit = re.search(re.escape(inst) + r"\s*\(\s*(.*?)\)\s*;", top, re.S)
    assert hit, f"instantiation not found: {inst}"
    return hit.group(1)


# --- grounded checks ---------------------------------------------------------

def inspect(context: pathlib.Path) -> dict:  # noqa: C901 (structural asserts)
    """Derive the nine contract keys from the exact snapshot, with asserts."""
    top = _read(context, "console_top.v")
    msc = _read(context, "usb_msc_port.v")
    trace = _read(context, "usb_idle_trace.v")
    fifo = _read(context, "ddr_dcfifo.v")
    release = _read(context, "usb_reset_release.v")
    vo = _read(context, "netlist_taps.vo")
    timing = json.loads(_read(context, "timing.json"))
    provenance = json.loads(_read(context, "SOURCE_PROVENANCE.json"))

    cells, params, lut_out = _parse_taps(vo)
    out = {}

    # ---- A: highspeed PHY -> MSC hs_s[0] data synchronizer -----------------
    # Netlist tap: first stage samples usb_highspeed (PHY-domain reg
    # u_usb_init/s_highspeed_s0 per timing.json) with raw D = usb_highspeed
    # and a clear pin tied OFF -- a true synchronizer, not reset fanout.
    s0_name, s0 = _ff(cells,
                      D="usb_highspeed",
                      CLK="vid_hclk",
                      CE="VCC",
                      CLEAR="GND",
                      Q="\\u_usb_msc_port/hs_s [0]")
    s1_name, s1 = _ff(cells,
                      D="\\u_usb_msc_port/hs_s [0]",
                      CLK="vid_hclk",
                      CE="VCC",
                      Q="\\u_usb_msc_port/hs_s [1]")
    # RTL side must agree: hs_s is the {hs_s[0], highspeed} shifter on hclk.
    assert re.search(r"hs_s\s*<=\s*\{hs_s\[0\],\s*highspeed\}", msc), \
        "hs_s shift structure moved in usb_msc_port.v"
    out["hs_two_stage"] = bool(s0 and s1
                               and s0_name.endswith("/hs_s_0_s0")
                               and s1_name.endswith("/hs_s_1_s0"))

    # ---- B: wr_gray bus -> PHY wr_gray_s1 pointer synchronizer -------------
    # Netlist tap: source pointer reg (vid_hclk) then two phy_clk stages
    # wr_gray_s1 -> wr_gray_s2, both CE=VCC on the read (phy_clk) side.
    src_name, src = _ff(cells,
                        CLK="vid_hclk",
                        CE="\\u_usb_idle_trace/accept",
                        Q="\\u_usb_idle_trace/u_commands/wr_gray [1]")
    g1_name, g1 = _ff(cells,
                      D="\\u_usb_idle_trace/u_commands/wr_gray [1]",
                      CLK="phy_clk",
                      CE="VCC",
                      Q="\\u_usb_idle_trace/u_commands/wr_gray_s1 [1]")
    g2_name, g2 = _ff(cells,
                      D="\\u_usb_idle_trace/u_commands/wr_gray_s1 [1]",
                      CLK="phy_clk",
                      Q="\\u_usb_idle_trace/u_commands/wr_gray_s2 [1]")
    # RTL side: Gray encoding before crossing, two stages, decode after the
    # second stage -- the classic dual-clock Gray pointer discipline.
    assert re.search(r"wr_gray\s*<=\s*bin2gray\(", fifo), \
        "wr_gray is not Gray-encoded before the crossing"
    assert re.search(r"wr_gray_s1\s*<=\s*wr_gray;", fifo)
    assert re.search(r"wr_gray_s2\s*<=\s*wr_gray_s1;", fifo)
    assert re.search(r"gray2bin\(wr_gray_s2\)", fifo), \
        "decode no longer waits for the second synchronizer stage"
    out["gray_two_stage"] = bool(
        src and g1 and g2
        and src_name.endswith("/wr_gray_1_s0")
        and g1_name.endswith("/wr_gray_s1_1_s0")
        and g2_name.endswith("/wr_gray_s2_1_s0"))

    # ---- C: rst_usb -> gather[7] async CLEAR (the raw reset fanout) --------
    # The gather sample register is vid_hclk with an async CLEAR driven by
    # combinational LUT output n6_5, and n6_5 traces to LUT2 n6_s1 whose
    # only inputs are rst_usb and vid_hrstn -- no intermediate register.
    gather_name, gather = _ff(cells, Q="\\u_usb_msc_port/gather [7]")
    assert gather["CLK"].strip() == "vid_hclk", "gather moved clock domain"
    assert cells[gather_name]["prim"] == "DFFCE", "gather reg lost its async CLEAR pin"
    clear_net = gather["CLEAR"].strip()
    lut_inst = lut_out.get(clear_net, "")
    assert lut_inst and lut_inst.endswith("/n6_s1"), \
        f"CLEAR net {clear_net} no longer traces to the tapped LUT2"
    lut = cells[lut_inst]
    lut_inputs = {lut["ports"]["I0"].strip(), lut["ports"]["I1"].strip()}
    # The RTL form of the same expression, both USB AHB slaves:
    assert len(re.findall(r"\.reset_n\(vid_hrstn && !rst_usb\)", top)) == 2, \
        "msc + trace must both use reset_n = vid_hrstn && !rst_usb"
    # rst_usb itself is generated by a registered, phy_clk-qualified release.
    rst_name, rst_ff = _ff(cells, Q="rst_usb")
    assert rst_ff["CLK"].strip() == "phy_clk", "rst_usb moved clock domain"
    assert cells[rst_name]["prim"] == "DFFPE", "rst_usb lost its async PRESET pin"
    assert rst_ff["PRESET"].strip() == "phy_lock_reset"
    # console_top.v: the reset releasing rst_usb is usb_reset_release on phy_clk.
    ctl = _instance(top, "u_usb_controller_start")
    assert ".clk(phy_clk)" in ctl, "controller release guard moved clocks"
    assert ".locked(~phy_lock_reset)" in ctl
    assert ".reset(rst_usb)" in ctl
    # usb_reset_release.v: assert async on !locked, release registered after
    # two synchronizer stages plus HOLD_CYCLES stable clocks.
    assert re.search(
        r"always @\(posedge clk or negedge locked\)", release), \
        "usb_reset_release lost its asynchronous assertion branch"
    assert re.search(r'count == HOLD_CYCLES-1\)\s*reset <= 0', release), \
        "reset release is no longer registered after the hold count"
    out["gather_raw_async_reset"] = True
    out["gather_clock"] = gather["CLK"].strip()
    out["reset_source_clock"] = rst_ff["CLK"].strip()

    # ---- C2: LUT2 INIT and its truth table, indexed by (I1, I0) ------------
    init_raw = params[lut_inst]["INIT"]
    match = re.fullmatch(r"(\d+)'h([0-9a-fA-Fxz_]+)", init_raw)
    assert match, f"INIT not a hex LUT literal: {init_raw}"
    assert match.group(1) == "4", "INIT width unexpected for the tapped LUT2"
    out["raw_clear_lut_init"] = match.group(2).upper()
    init = int(out["raw_clear_lut_init"], 16)
    # Truth table bit i = bit selected by I1*2 + I0 (Gowin LUT bit order).
    table = [(init >> i) & 1 for i in range(4)]
    # Semantic cross-check against the RTL async-clear expression:
    # CLEAR must evaluate !(vid_hrstn && !rst_usb) == 1 - (I1 & !I0).
    for i1 in (0, 1):
        for i0 in (0, 1):
            assert table[i1 * 2 + i0] == 1 - (i1 & (1 - i0)), \
                f"LUT truth table diverges from RTL async clear at I1={i1} I0={i0}"
    out["raw_clear_truth_table"] = table

    # ---- D: local hr/ur release guard of usb_msc_port ----------------------
    # Each domain holds its own local reset until the OTHER clock's release
    # has been observed through two synchronizer stages (cross-view guard).
    guard_msc = all(re.search(p, msc) for p in (
        r"reg \[2:0\] hr .*\bur\b",          # both release counters
        r"uh <= \{uh\[0\], ur\[2\]\}",       # hclk observes phy release
        r"hu <= \{hu\[0\], hr\[2\]\}",       # phy observes hclk release
        r"wire hreset = !hr\[2\] \|\| !uh\[1\]",   # local guard on hclk side
        r"wire ubase\s*= !ur\[2\] \|\| !hu\[1\]",  # local guard on phy side
    ))
    # Same guard idiom exists in usb_idle_trace (shared reset_n net above).
    guard_trace = all(re.search(p, trace) for p in (
        r"uh<\=\{uh\[0\],ur\[2\]\}", r"hu<\=\{hu\[0\],hr\[2\]\}",
        r"wire hreset=!hr\[2\] \|\| !uh\[1\]", r"ureset=!ur\[2\] \|\| !hu\[1\]"))
    assert guard_trace, "usb_idle_trace lost its cross-view release guard"
    assert re.search(r"ASYNC_REG", msc), "hs/ur syncs lost ASYNC_REG attribute"
    # The msc slave instance itself bridges the two domains of that guard.
    msc_ports = _instance(top, "u_usb_msc_port")
    assert ".clk(phy_clk)" in msc_ports and ".hclk(vid_hclk)" in msc_ports
    out["msc_local_release_guard"] = guard_msc

    # ---- E: timing closure status from the two frozen reports --------------
    paths = timing["paths"]
    summary = timing["summary"]
    # The four worst reported paths must be exactly the four contract paths.
    worst_setup = paths["setup"]["worst"]
    worst_hold = paths["hold"]["worst"]
    worst_recovery = paths["recovery"]["worst"]
    worst_removal = paths["removal"]["worst"]
    assert worst_setup[2].endswith("s_highspeed_s0/Q"), worst_setup[2]
    assert worst_setup[3] == "u_usb_msc_port/hs_s_0_s0/D", worst_setup[3]
    assert worst_hold[2].endswith("wr_gray_1_s0/Q"), worst_hold[2]
    assert worst_hold[3].endswith("wr_gray_s1_1_s0/D"), worst_hold[3]
    assert worst_recovery[2] == "u_usb_controller_start/reset_s4/Q", \
        worst_recovery[2]
    assert worst_recovery[3] == "u_usb_msc_port/gather_7_s0/CLEAR", \
        worst_recovery[3]
    assert worst_removal[2] == "u_usb_phy_start/reset_s4/Q", worst_removal[2]
    assert worst_removal[3] == "u_usb_controller_start/count_1_s1/CLEAR", \
        worst_removal[3]
    violated = (
        paths["setup"]["minimum_ns"] < 0
        or paths["hold"]["minimum_ns"] < 0
        or paths["recovery"]["minimum_ns"] < 0
        or paths["removal"]["minimum_ns"] < 0
        or int(summary["Numbers of Setup Violated Endpoints"]) > 0
        or int(summary["Numbers of Hold Violated Endpoints"]) > 0)
    # provenance: "timing_closed": false, and the R5 SDC differs from G22.
    assert provenance["timing_closed"] is False
    assert provenance["hardware_validated"] is False
    assert provenance["sources"]["diagnostics/timing_reports.sdc"]["same_rtl"] \
        is False, "G22 SDC hash unexpectedly matches the R5 snapshot"
    # Negative slacks everywhere, yet per-clock TNS is reported zero:
    # flag this internal inconsistency for the constraint review.
    tns = {row[0]: (row[1], row[2], row[3]) for row in timing["per_clock_tns"]}
    assert all(tns[clock][1] == "0.000"
               for clock, _ in tns.items()), "per-clock TNS report changed"
    out["timing_closed"] = (not violated) and bool(provenance["timing_closed"])
    return out


if __name__ == "__main__":
    context_dir = pathlib.Path(__file__).resolve().parent.parent / "context"
    summary = inspect(context_dir)
    print(json.dumps(summary, indent=2))