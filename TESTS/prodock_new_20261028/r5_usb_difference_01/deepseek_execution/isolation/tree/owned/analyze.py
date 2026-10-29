"""Bounded combinational-boundary analyzer for the G22/R5 public netlist data.

The analyzer deliberately compares only what the extracted context supports:
  * the TBUF I cone and the CLKDIV RESETN cone, resolved through LUT/MUX/ALU
    driver cones to constants, primary nets, or registered state;
  * full parameters of common critical cells (PLL, IO, IDES/OSER, CLKDIV, ...);
  * the official ALU mode-0/mode-1 equations for I3 independence.

Unsupported cells, ambiguous drivers, and cycles become explicit unresolved
statuses.  They are never silently treated as equivalent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_LEAVES = 16          # truth-table bound for a resolved cone
MAX_DEPTH = 256          # recursion bound
MAX_CELLS = 4096         # bounded number of driver cells per cone
CONSTANTS = {"GND": 0, "VCC": 1, "1'b0": 0, "1'b1": 1, "0": 0, "1": 1}

DFF_KINDS = {
    "DFF", "DFFE", "DFFCE", "DFFPE", "DFFSE", "DFFRE",
    "DFFN", "DFFNE", "DFFNCE",
}
CRITICAL_KINDS = {
    "PLL", "IBUF", "IOBUF", "ELVDS_IOBUF", "TBUF", "CLKDIV", "DHCE",
    "IDES8", "IDES16", "OSER16",
}
LUT_INPUTS = {"LUT1": 1, "LUT2": 2, "LUT3": 3, "LUT4": 4}
MUX_KINDS = {"MUX2_LUT5", "MUX2_LUT6", "MUX2_LUT7", "MUX2_LUT8"}


class Func:
    """Truth table over a sorted tuple of stable leaf net names."""

    __slots__ = ("ok", "leaves", "mask", "reason")

    def __init__(self, ok, leaves=(), mask=0, reason=""):
        self.ok = ok
        self.leaves = tuple(leaves)
        self.mask = int(mask)
        self.reason = reason if not ok else ""


def _load_json(folder: Path, name: str, default=None):
    path = folder / name
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _parse_literal(text):
    """Parse a Verilog-style INIT/binary/hex literal without guessing X/Z."""
    if isinstance(text, int):
        return text
    if text is None:
        return None
    value = str(text).strip().replace("_", "")
    if value in ("0", "1"):
        return int(value)
    match = re.fullmatch(r"(\d+)'[sS]?([hHbBoOdD])([0-9a-fA-F]+)", value)
    if not match:
        return None
    width, base, digits = match.groups()
    base = base.lower()
    if base in ("x", "z"):
        return None
    try:
        return int(digits, {"h": 16, "b": 2, "o": 8, "d": 10}[base])
    except ValueError:
        return None


def _const_or_none(net):
    return CONSTANTS.get(str(net).strip())


def _leaf(net):
    return Func(True, (net,), 0b10)


def _combine(children, evaluator):
    """Combine child functions with an evaluator over their bit values."""
    leaves = sorted({leaf for child in children for leaf in child.leaves})
    if len(leaves) > MAX_LEAVES:
        return Func(False, reason=f"leaf-cap>{MAX_LEAVES}")
    position = {leaf: index for index, leaf in enumerate(leaves)}
    mask = 0
    for assignment in range(1 << len(leaves)):
        values = []
        for child in children:
            if child.leaves:
                index = 0
                for bit, leaf in enumerate(child.leaves):
                    if (assignment >> position[leaf]) & 1:
                        index |= 1 << bit
                values.append((child.mask >> index) & 1)
            else:
                values.append(child.mask & 1)
        if evaluator(values):
            mask |= 1 << assignment
    if mask == 0:
        return Func(True, (), 0)
    if mask == (1 << (1 << len(leaves))) - 1:
        return Func(True, (), 1)
    return Func(True, tuple(leaves), mask)


def _function_equal(left, right):
    """Compare two resolved functions over the union of their leaf names."""
    if not left.ok or not right.ok:
        return False
    leaves = sorted(set(left.leaves) | set(right.leaves))
    if len(leaves) > MAX_LEAVES:
        return False

    def value(func, assignment):
        if not func.leaves:
            return func.mask & 1
        position = {leaf: index for index, leaf in enumerate(leaves)}
        index = 0
        for bit, leaf in enumerate(func.leaves):
            if (assignment >> position[leaf]) & 1:
                index |= 1 << bit
        return (func.mask >> index) & 1

    for assignment in range(1 << len(leaves)):
        if value(left, assignment) != value(right, assignment):
            return False
    return True


# ---------------------------------------------------------------------------
# Official ALU model parser (only expressions needed for exhaustive tables)
# ---------------------------------------------------------------------------

_EXPR_TOKEN = re.compile(
    r"\d+'[sS]?[bBhHoOdD][0-9a-fA-F_xXzZ]+|[A-Za-z_]\w*|[~!^&|?:()]"
)


class _ExprParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError("bad expression")
        self.pos += 1
        return token

    def parse(self, env):
        value = self.ternary(env)
        if self.pos != len(self.tokens):
            raise ValueError("trailing tokens")
        return value

    def ternary(self, env):
        condition = self.or_expr(env)
        if self.peek() == "?":
            self.take("?")
            yes = self.ternary(env)
            self.take(":")
            no = self.ternary(env)
            return yes if condition else no
        return condition

    def or_expr(self, env):
        value = self.and_expr(env)
        while self.peek() == "|":
            self.take("|")
            value = value | self.and_expr(env)
        return value

    def and_expr(self, env):
        value = self.xor_expr(env)
        while self.peek() == "&":
            self.take("&")
            value = value & self.xor_expr(env)
        return value

    def xor_expr(self, env):
        value = self.unary(env)
        while self.peek() == "^":
            self.take("^")
            value = value ^ self.unary(env)
        return value

    def unary(self, env):
        if self.peek() in ("~", "!"):
            self.take()
            return 1 - self.unary(env)
        if self.peek() == "(":
            self.take("(")
            value = self.ternary(env)
            self.take(")")
            return value
        return self.primary(env)

    def primary(self, env):
        token = self.take()
        number = _parse_literal(token)
        if number is not None:
            return 1 if number else 0
        if token in env:
            return env[token]
        raise ValueError(f"unknown identifier {token}")


def _eval_expr(expression, env):
    tokens = _EXPR_TOKEN.findall(expression.replace(" ", ""))
    if not tokens:
        raise ValueError("empty expression")
    return _ExprParser(tokens).parse(env)


def _strip_verilog_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _official_alu_equations(folder: Path):
    """Return mode -> (S,C,SUM,COUT expressions) from official_models.v."""
    path = folder / "official_models.v"
    if not path.exists():
        return None
    text = _strip_verilog_comments(path.read_text(encoding="utf-8"))
    module = re.search(r"\bmodule\s+ALU\b(.*?)\bendmodule\b", text, re.S)
    if not module:
        return None
    body = module.group(1)
    parameters = {
        name: int(value)
        for name, value in re.findall(r"\bparameter\s+(\w+)\s*=\s*(\d+)\s*;", body)
    }
    case = re.search(r"\bcase\s*\(\s*ALU_MODE\s*\)(.*?)\bendcase\b", body, re.S)
    if not case:
        return None
    modes = {}
    for match in re.finditer(r"(\w+)\s*:\s*begin(.*?)\bend\b", case.group(1), re.S):
        name, block = match.groups()
        if name not in parameters:
            continue
        s_expr = re.search(r"\bS\s*=\s*([^;]+);", block)
        c_expr = re.search(r"\bC\s*=\s*([^;]+);", block)
        if s_expr and c_expr:
            modes[parameters[name]] = (s_expr.group(1), c_expr.group(1))
    sum_expr = re.search(r"\bassign\s+SUM\s*=\s*([^;]+);", body)
    cout_expr = re.search(r"\bassign\s+COUT\s*=\s*([^;]+);", body)
    if not sum_expr or not cout_expr:
        return None
    return modes, sum_expr.group(1), cout_expr.group(1)


def _official_alu_outputs(equations, mode, i0, i1, i3, cin):
    modes, sum_expr, cout_expr = equations
    if mode not in modes:
        return None
    s_expr, c_expr = modes[mode]
    s_value = _eval_expr(s_expr, {"I0": i0, "I1": i1, "I3": i3, "CIN": cin})
    c_value = _eval_expr(c_expr, {"I0": i0, "I1": i1, "I3": i3, "CIN": cin})
    env = {"S": s_value, "C": c_value, "CIN": cin}
    return _eval_expr(sum_expr, env), _eval_expr(cout_expr, env)


def _i3_independent(equations, mode):
    """Exhaustively prove that both official outputs ignore I3 for a mode."""
    for i0 in (0, 1):
        for i1 in (0, 1):
            for cin in (0, 1):
                low = _official_alu_outputs(equations, mode, i0, i1, 0, cin)
                high = _official_alu_outputs(equations, mode, i0, i1, 1, cin)
                if low is None or high is None or low != high:
                    return False
    return True


def _alu_i3_check(folder: Path, result):
    equations = _official_alu_equations(folder)
    if equations is None:
        return False, {"status": "official-alu-unavailable"}
    independent = {
        str(mode): _i3_independent(equations, mode) for mode in (0, 1)
    }
    modes = result.get("i3_modes") if isinstance(result, dict) else None
    expected_count = result.get("i3_only_alu_count") if isinstance(result, dict) else None
    if not isinstance(modes, dict) or not isinstance(expected_count, int):
        return False, {"status": "i3-summary-missing", "independent": independent}
    total = 0
    bad_modes = []
    try:
        for key, count in modes.items():
            key_int = int(key)
            count_int = int(count)
            total += count_int
            if count_int > 0 and key_int not in (0, 1):
                bad_modes.append(key_int)
    except (TypeError, ValueError):
        return False, {"status": "i3-summary-malformed", "independent": independent}
    ok = (
        all(independent.values())
        and total == expected_count
        and not bad_modes
    )
    return ok, {
        "status": "ok" if ok else "i3-dependence-or-count-mismatch",
        "independent": independent,
        "mode_counts": modes,
        "counted": total,
        "expected_count": expected_count,
        "bad_modes": sorted(bad_modes),
    }


# ---------------------------------------------------------------------------
# Bounded combinational cone resolution
# ---------------------------------------------------------------------------

def _cell_outputs(cell):
    """Map an output net to the output pin that drives it."""
    kind = cell.get("kind", "")
    ports = cell.get("ports", {})
    outputs = {}
    if kind in LUT_INPUTS:
        outputs["F"] = ports.get("F")
    elif kind == "INV":
        outputs["O"] = ports.get("O")
    elif kind in MUX_KINDS:
        outputs["O"] = ports.get("O")
    elif kind == "ALU":
        for pin in ("SUM", "COUT"):
            outputs[pin] = ports.get(pin)
    elif kind == "IBUF":
        outputs["O"] = ports.get("O")
    elif kind in ("TBUF", "IOBUF", "ELVDS_IOBUF"):
        outputs["O"] = ports.get("O")
    elif kind == "PLL":
        for pin in ("CLKFBOUT", "LOCK", "RESET_O"):
            outputs[pin] = ports.get(pin)
        for pin in ("CLKOUT0", "CLKOUT1", "CLKOUT2", "CLKOUT3",
                    "CLKOUT4", "CLKOUT5", "CLKOUT6"):
            outputs[pin] = ports.get(pin)
    elif kind == "CLKDIV":
        outputs["CLKOUT"] = ports.get("CLKOUT")
    elif kind == "DHCE":
        outputs["CLKOUT"] = ports.get("CLKOUT")
    elif kind in ("IDES8", "IDES16"):
        for pin, net in ports.items():
            if re.fullmatch(r"Q\d+", pin):
                outputs[pin] = net
    elif kind == "OSER16":
        outputs["Q"] = ports.get("Q")
    elif kind in ("SDPB", "SDPX9B"):
        outputs["DO"] = ports.get("DO")
    return {pin: net for pin, net in outputs.items() if net is not None}


def _build_drivers(graph):
    drivers = {}
    for name, cell in graph.items():
        for pin, net in _cell_outputs(cell).items():
            drivers.setdefault(str(net), []).append((name, pin))
    return drivers


def _cell_function(cell, pin, resolve):
    kind = cell.get("kind", "")
    ports = cell.get("ports", {})
    params = cell.get("params", {})
    if kind in DFF_KINDS and pin == "Q":
        return _leaf(ports.get("Q", ""))
    if kind in LUT_INPUTS:
        if pin != "F":
            return Func(False, reason="unsupported-lut-pin")
        count = LUT_INPUTS[kind]
        init = _parse_literal(params.get("INIT", "0"))
        if init is None or init >= (1 << (1 << count)):
            return Func(False, reason="invalid-lut-init")
        children = [resolve(ports.get(f"I{index}", "")) for index in range(count)]
        if any(not child.ok for child in children):
            return next(child for child in children if not child.ok)

        def lut_eval(values):
            index = sum(value << bit for bit, value in enumerate(values))
            return (init >> index) & 1

        return _combine(children, lut_eval)
    if kind == "INV":
        child = resolve(ports.get("I", ""))
        if not child.ok:
            return child
        return _combine([child], lambda values: 1 - values[0])
    if kind in MUX_KINDS:
        children = [resolve(ports.get("I0", "")),
                    resolve(ports.get("I1", "")),
                    resolve(ports.get("S0", ""))]
        if any(not child.ok for child in children):
            return next(child for child in children if not child.ok)
        return _combine(children, lambda values: values[1] if values[2] else values[0])
    if kind == "ALU":
        mode = _parse_literal(params.get("ALU_MODE", "0"))
        equations = cell.get("_alu_equations")
        if mode is None or equations is None:
            return Func(False, reason="alu-model-unavailable")
        children = [resolve(ports.get("I0", "")),
                    resolve(ports.get("I1", "")),
                    resolve(ports.get("I3", "")),
                    resolve(ports.get("CIN", ""))]
        if any(not child.ok for child in children):
            return next(child for child in children if not child.ok)

        def alu_eval(values):
            outputs = _official_alu_outputs(equations, mode, *values)
            if outputs is None:
                return 0
            return outputs[0] if pin == "SUM" else outputs[1]

        return _combine(children, alu_eval)
    if kind == "IBUF" and pin == "O":
        return resolve(ports.get("I", ""))
    if kind in ("TBUF", "IOBUF", "ELVDS_IOBUF"):
        return Func(False, reason=f"unsupported-{kind.lower()}-output")
    return Func(False, reason=f"unsupported-{kind.lower()}-{pin}")


def _resolve_cone(net, graph, drivers, algorithms, memo, visiting, depth=0):
    net = str(net)
    if net in memo:
        return memo[net]
    if depth > MAX_DEPTH or algorithms["cells"] > MAX_CELLS:
        result = Func(False, reason="cone-bound")
        memo[net] = result
        return result
    constant = _const_or_none(net)
    if constant is not None:
        result = Func(True, (), constant)
        memo[net] = result
        return result
    if net in visiting:
        result = Func(False, reason="combinational-cycle")
        memo[net] = result
        return result
    candidates = drivers.get(net, [])
    if not candidates:
        # A bounded extraction cuts at primary nets and registered state.
        result = _leaf(net)
        memo[net] = result
        return result
    if len(candidates) > 1:
        result = Func(False, reason="multiple-drivers")
        memo[net] = result
        return result
    cell_name, pin = candidates[0]
    cell = graph[cell_name]
    if cell.get("kind") in DFF_KINDS:
        result = _leaf(net)
        memo[net] = result
        return result
    visiting.add(net)
    algorithms["cells"] += 1
    result = _cell_function(cell, pin, lambda child: _resolve_cone(
        child, graph, drivers, algorithms, memo, visiting, depth + 1
    ))
    visiting.discard(net)
    memo[net] = result
    return result


# ---------------------------------------------------------------------------
# Critical boundary extraction and parameter comparison
# ---------------------------------------------------------------------------

def _cell_candidates(folder, critical, changed, name):
    """Collect a cell from both authoritative context files per build."""
    candidates = {"g22": [], "r5": []}
    for source_name, source in (("critical_cells", critical), ("changed_cones", changed)):
        if not isinstance(source, dict):
            continue
        for side in ("g22", "r5"):
            cells = source.get(side, {})
            if name in cells:
                candidates[side].append((source_name, cells[name]))
    return candidates


def _target_net(folder, critical, changed, name, pin):
    candidates = _cell_candidates(folder, critical, changed, name)
    nets = {"g22": set(), "r5": set()}
    for side in ("g22", "r5"):
        for _, cell in candidates[side]:
            net = cell.get("ports", {}).get(pin)
            if net is not None:
                nets[side].add(str(net))
    if not nets["g22"] or not nets["r5"]:
        return None, {"status": "target-cell-missing", "nets": nets}
    if len(nets["g22"]) != 1 or len(nets["r5"]) != 1:
        return None, {"status": "target-source-conflict", "nets": nets}
    ordered = {side: sorted(values) for side, values in nets.items()}
    return (next(iter(nets["g22"])), next(iter(nets["r5"]))), {"nets": ordered}


def _cone_equivalence(folder, critical, changed, target_name, pin, graph):
    nets, details = _target_net(folder, critical, changed, target_name, pin)
    if nets is None:
        return False, details
    drivers = {
        "g22": _build_drivers(graph.get("g22", {})),
        "r5": _build_drivers(graph.get("r5", {})),
    }
    equations = _official_alu_equations(folder)
    left_graph = graph.get("g22", {})
    right_graph = graph.get("r5", {})
    for side_graph in (left_graph, right_graph):
        for cell in side_graph.values():
            cell["_alu_equations"] = equations
    left = _resolve_cone(nets[0], left_graph, drivers["g22"],
                         {"cells": 0}, {}, set())
    right = _resolve_cone(nets[1], right_graph, drivers["r5"],
                          {"cells": 0}, {}, set())
    equivalent = _function_equal(left, right)
    details.update({
        "g22_net": nets[0],
        "r5_net": nets[1],
        "g22_status": "ok" if left.ok else left.reason,
        "r5_status": "ok" if right.ok else right.reason,
        "g22_leaves": list(left.leaves),
        "r5_leaves": list(right.leaves),
    })
    return equivalent, details


def _critical_parameter_changes(critical, changed):
    changes = {}
    for source_name, source in (("critical_cells", critical), ("changed_cones", changed)):
        if not isinstance(source, dict):
            continue
        left = source.get("g22", {})
        right = source.get("r5", {})
        for name in sorted(set(left) & set(right)):
            lcell, rcell = left[name], right[name]
            if source_name == "changed_cones":
                if lcell.get("kind") not in CRITICAL_KINDS and rcell.get("kind") not in CRITICAL_KINDS:
                    continue
            lparams = lcell.get("params", {}) or {}
            rparams = rcell.get("params", {}) or {}
            for parameter in sorted(set(lparams) | set(rparams)):
                lvalue = lparams.get(parameter, "<missing>")
                rvalue = rparams.get(parameter, "<missing>")
                if lvalue == rvalue:
                    continue
                key = (name, parameter)
                if key not in changes:
                    changes[key] = {
                        "cell": name,
                        "parameter": parameter,
                        "g22": lvalue,
                        "r5": rvalue,
                        "source": source_name,
                    }
    return [changes[key] for key in sorted(changes)]


def analyze(context: Path) -> dict:
    """Analyze the bounded public post-route context directory."""
    folder = Path(context)
    critical = _load_json(folder, "critical_cells.json", {}) or {}
    changed = _load_json(folder, "changed_cones.json", {}) or {}
    result = _load_json(folder, "result.json", {}) or {}
    graph = {
        "g22": dict(changed.get("g22", {}) if isinstance(changed, dict) else {}),
        "r5": dict(changed.get("r5", {}) if isinstance(changed, dict) else {}),
    }

    pullup, pullup_details = _cone_equivalence(
        folder, critical, changed,
        "\\u_usb_softphy_top/usb_pullup_en_o_s1", "I", graph,
    )
    clkdiv, clkdiv_details = _cone_equivalence(
        folder, critical, changed,
        "\\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/"
        "u_usb2_0_softphy/u_usb_phy_hs/clkdiv_inst", "RESETN", graph,
    )
    alu_ok, alu_details = _alu_i3_check(folder, result)
    params = _critical_parameter_changes(critical, changed)

    return {
        "pullup_equivalent": bool(pullup),
        "clkdiv_reset_equivalent": bool(clkdiv),
        "alu_i3_mode01_equivalent": bool(alu_ok),
        "critical_parameter_changes": params,
        "evidence": {
            "pullup": pullup_details,
            "clkdiv_reset": clkdiv_details,
            "alu_i3": alu_details,
            "scope": result.get("scope", "") if isinstance(result, dict) else "",
            "changed_count": result.get("changed_count") if isinstance(result, dict) else None,
            "other_changes": len(result.get("other_changes", [])) if isinstance(result, dict) else None,
            "missing": len(result.get("missing", [])) if isinstance(result, dict) else None,
            "added": len(result.get("added", [])) if isinstance(result, dict) else None,
        },
    }
