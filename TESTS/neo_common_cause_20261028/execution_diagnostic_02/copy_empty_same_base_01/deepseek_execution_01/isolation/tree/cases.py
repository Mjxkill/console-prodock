"""Descriptor-boundary stimuli for neo_copy_same_base_boundaries_01.

The harness feeds each 256-bit command as eight little-endian 32-bit words.
``gpu_copy565`` interprets those words as::

    w0  opcode/header (unused by the DUT)
    w1  source base address
    w2  [31:16] rectangle width, [15:0] rectangle height
    w3  [15:0] source stride in bytes
    w4  [31:16] source x, [15:0] source y       (signed)
    w5  [31:16] destination x, [15:0] dest y   (signed)
    w6  [31:16] clip width, [15:0] clip height
    w7  reserved word, required to be zero

Only the fields under test are changed.  Every stimulus keeps the requested
clip extent at 0x0, so a descriptor that survives validation completes without
issuing a DDR request.  Expected ``bad`` values below are independent
requirements taken from the specification, not values observed from the RTL.
"""

# Fixed ABI values used by the benchmark.
HEADER_WORD = 0x1D000000          # w0: command marker, ignored by the DUT
SOURCE_BASE = 0x12000000          # w1: original source base
DEST_BASE = 0x12000020            # bench dst_base input
NATIVE_WIDTH = 16                 # width in native 32-byte blocks
NATIVE_STRIDE = 32                # bytes per row, matching dst_stride
EMPTY_CLIP = (0, 0)               # w6: zero requested extent


def _pair(high, low):
    """Pack two 16-bit ABI fields into one command word."""
    return ((high & 0xFFFF) << 16) | (low & 0xFFFF)


def _packet(src_base, width=NATIVE_WIDTH, height=1, stride=NATIVE_STRIDE,
            reserved=0, src_xy=(0, 0), dst_xy=(0, 0),
            clip=EMPTY_CLIP):
    """Build the eight ABI words for one descriptor."""
    return [
        HEADER_WORD,
        src_base,
        _pair(width, height),
        stride & 0xFFFFFFFF,
        _pair(*src_xy),
        _pair(*dst_xy),
        _pair(*clip),
        reserved & 0xFFFFFFFF,
    ]


def _case(name, command, force_end, bad, reason):
    """Associate a stimulus with its non-empty, explicit expectation reason."""
    if not reason:
        raise ValueError("every case needs an explicit expectation reason")
    return name, command, force_end, bad, reason


# Ten cases in the required order.  The first eight are ordinary descriptors;
# the last two use the simulation-only src_end fault injection to probe whether
# the base/stride term, rather than the range term alone, controls rejection.
_CASES = (
    _case(
        "original_empty",
        _packet(SOURCE_BASE),
        0, 0,
        "Original base/stride: src_end == 0x12000020 == dst_base, so the strict "
        "overlap interval does not open; clip 0x0 then finishes cleanly.",
    ),
    _case(
        "same_base_empty",
        _packet(DEST_BASE),
        0, 0,
        "Identical source/destination base with matching stride is the one "
        "permitted overlap layout; clip 0x0 finishes without a bad flag.",
    ),
    _case(
        "overlap_wrong_base",
        _packet(SOURCE_BASE, height=2),
        0, 1,
        "Height 2 extends src_end past dst_base and the source base differs "
        "from dst_base, so the overlap descriptor check rejects it.",
    ),
    _case(
        "same_layout_taller",
        _packet(DEST_BASE, height=2),
        0, 0,
        "Height 2 also overlaps, but base and stride match, satisfying the "
        "same-layout exception; empty clip finishes without a bad flag.",
    ),
    _case(
        "same_base_wrong_stride",
        _packet(DEST_BASE, stride=64),
        0, 1,
        "Same base makes the interval overlap, yet stride 64 differs from "
        "dst_stride 32, so the same-layout exception does not apply.",
    ),
    _case(
        "same_base_height_zero",
        _packet(DEST_BASE, height=0),
        0, 1,
        "Height 0 is a zero-height descriptor and is rejected outright even "
        "though the base and stride match.",
    ),
    _case(
        "same_base_misaligned",
        _packet(DEST_BASE + 2),
        0, 1,
        "Source base 0x12000022 has nonzero low address bits, violating the "
        "base-alignment field check on an otherwise same-layout request.",
    ),
    _case(
        "same_base_reserved_word",
        _packet(DEST_BASE, reserved=1),
        0, 1,
        "Reserved w7 must be zero; a nonzero reserved word is rejected even "
        "for an otherwise valid same-base descriptor.",
    ),
    _case(
        "original_forced_end",
        _packet(SOURCE_BASE),
        1, 1,
        "With src_end forced beyond dst_base in the original layout, the "
        "interval overlaps and the differing source base must reject; this is "
        "a simulated fault, not a physical DDR observation.",
    ),
    _case(
        "same_base_forced_end",
        _packet(DEST_BASE),
        1, 0,
        "The same forced src_end still passes because base and stride match: "
        "the base/stride exception neutralizes the overlap term, while the "
        "other descriptor checks remain active.",
    ),
)


def cases():
    """Return the ten public records in order, with exactly four ABI keys."""
    records = []
    for name, command, force_end, bad, reason in _CASES:
        # ``reason`` is deliberately kept out of the record so the public
        # structure remains name/command/force_end/bad while the expectation
        # rationale stays explicit in the source above.
        assert reason
        records.append({
            "name": name,
            "command": list(command),
            "force_end": force_end,
            "bad": bad,
        })
    return records
