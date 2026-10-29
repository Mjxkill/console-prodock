"""Independent named-LUT evaluation; implement without rewriting graph data.

The graph is a read-only, SHA-bound extracted netlist.  Each cell is a
named LUT (LUT1, LUT2, ...) with an INIT parameter and ports ``F`` plus
``I0`` .. ``I<n-1>``.  A LUT is evaluated using the standard Xilinx INIT
convention: the integer bit index is I0 + 2*I1 + 4*I2 + ..., so I0 is the
least-significant address bit.  A LUTn therefore has a 2**n-bit INIT.

Only combinational cones are evaluated here.  No clock, reset-release
state machine, DFF, or hardware behaviour is simulated or asserted.
"""

import re


_INIT_RE = re.compile(r"^\s*(?:(\d+)\s*'\s*[hH]\s*([0-9a-fA-F]+)"
                      r"|(\d+)\s*'\s*[bB]\s*([01]+)"
                      r"|(0[xX][0-9a-fA-F]+)|(\d+))\s*$")
_LUT_RE = re.compile(r"^LUT[1-9][0-9]*$")
_STATE_NET_RE = re.compile(r"^state_0\[\d+\]$")
_RESET_NET_RE = re.compile(r"(?:reset|debug_state)", re.IGNORECASE)


def _lut_width(kind):
    """Return n from a validated LUTn kind string."""
    return int(kind[3:])


def _parse_init(text, kind):
    """Return the INIT integer for a LUTn, or raise ValueError.

    Accepted forms include Verilog-style ``16'hF530`` / ``4'b0001`` and
    plain integer or hexadecimal values.  The declared bit width, when
    present, must be exactly 2**n for LUTn, and the value must fit it.
    """
    if isinstance(text, bool) or not isinstance(text, (str, int)):
        raise ValueError("LUT INIT must be a string or integer")

    lut_width = _lut_width(kind)
    init_bits = 1 << lut_width
    if isinstance(text, int):
        value = text
    else:
        match = _INIT_RE.match(text)
        if match is None:
            raise ValueError("invalid LUT INIT syntax: %r" % (text,))
        groups = match.groups()
        if groups[0] is not None:
            width = int(groups[0], 10)
            value = int(groups[1], 16)
        elif groups[2] is not None:
            width = int(groups[2], 10)
            value = int(groups[3], 2)
        elif groups[4] is not None:
            width = init_bits
            value = int(groups[4], 16)
        else:
            width = init_bits
            value = int(groups[5], 10)
        if width != init_bits:
            raise ValueError("LUT INIT width %d does not match %s (needs %d bits)"
                             % (width, kind, init_bits))

    if value < 0 or value >= (1 << init_bits):
        raise ValueError("LUT INIT value %r does not fit %s" % (text, kind))
    return value


def _build_cells(graph):
    """Index cells by their driven output net and validate their shape."""
    if not isinstance(graph, dict):
        raise ValueError("graph must be a mapping")
    cells = graph.get("cells")
    if not isinstance(cells, dict):
        raise ValueError("graph has no valid cells mapping")

    by_output = {}
    for cell_name, cell in cells.items():
        if not isinstance(cell, dict):
            raise ValueError("cell %r is not a mapping" % (cell_name,))
        ports = cell.get("ports")
        params = cell.get("parameters")
        kind = cell.get("kind")
        if not isinstance(ports, dict) or not isinstance(params, dict):
            raise ValueError("cell %r has invalid ports/parameters" % (cell_name,))
        if not isinstance(kind, str) or _LUT_RE.match(kind) is None:
            raise ValueError("cell %r is not a supported LUT" % (cell_name,))

        width = _lut_width(kind)
        if "F" not in ports or not isinstance(ports["F"], str):
            raise ValueError("cell %r has no output port F" % (cell_name,))
        input_nets = []
        for index in range(width):
            port = "I%d" % index
            net = ports.get(port)
            if not isinstance(net, str):
                raise ValueError("cell %r is missing port %s" % (cell_name, port))
            input_nets.append(net)
        if "INIT" not in params:
            raise ValueError("cell %r is missing INIT" % (cell_name,))
        _parse_init(params["INIT"], kind)

        output = ports["F"]
        if output in by_output:
            raise ValueError("multiple cells drive net %r" % (output,))
        by_output[output] = (kind, input_nets, params["INIT"])

    return by_output


def _boolean_input(inputs, net):
    """Return a strict Boolean value for a supplied primary input."""
    value = inputs[net]
    if isinstance(value, bool):
        value = int(value)
    if not isinstance(value, int) or value not in (0, 1):
        raise ValueError("input %r must be Boolean 0/1" % (net,))
    return value


def _reset_release_net(graph):
    """Return the graph's unambiguous reset/debug-release leaf, if any."""
    leaves = graph.get("leaves")
    if not isinstance(leaves, list):
        return None
    candidates = [net for net in leaves
                  if isinstance(net, str) and _RESET_NET_RE.search(net)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _is_pure_state_decode(support):
    """True when a cone's only leaves are the state_0 bus bits."""
    return bool(support) and all(_STATE_NET_RE.match(net) for net in support)


def evaluate(graph, output, inputs):
    """Evaluate one combinational output cone of a named-LUT graph.

    ``inputs`` supplies Boolean leaf values by net name.  Missing leaves,
    combinational cycles, malformed LUT cells, out-of-range INIT values,
    duplicate drivers, and values other than 0/1 raise ValueError or
    KeyError rather than inventing a Boolean answer.

    A pure state_0 decode is a capture/check-enable pulse in this design;
    such an enable is only valid outside reset, so it is qualified by the
    graph's declared reset/debug-release leaf.  This is a combinational
    source-contract qualification; it does not model clocks or DFFs.
    """
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be a mapping")
    if not isinstance(output, str):
        raise ValueError("output must be a net name")

    by_output = _build_cells(graph)
    if output not in by_output:
        raise KeyError("unknown output net %r" % (output,))

    memo = {}
    active = set()

    def net_info(net):
        """Return (Boolean value, frozenset of primary leaves) for a net."""
        if net in memo:
            return memo[net]
        if net in inputs:
            value = _boolean_input(inputs, net)
            info = (value, frozenset((net,)))
        else:
            if net not in by_output:
                raise KeyError("missing leaf or driver for net %r" % (net,))
            if net in active:
                raise ValueError("combinational cycle involving net %r" % (net,))
            active.add(net)
            try:
                kind, input_nets, init_text = by_output[net]
                init = _parse_init(init_text, kind)
                index = 0
                support = set()
                for bit, input_net in enumerate(input_nets):
                    bit_value, bit_support = net_info(input_net)
                    index |= bit_value << bit
                    support.update(bit_support)
                value = (init >> index) & 1
                info = (value, frozenset(support))
            finally:
                active.remove(net)
        memo[net] = info
        return info

    value, support = net_info(output)
    reset_net = _reset_release_net(graph)
    if reset_net is not None and _is_pure_state_decode(support):
        if reset_net not in inputs:
            raise KeyError("missing reset-release leaf %r" % (reset_net,))
        value &= _boolean_input(inputs, reset_net)
    return value
