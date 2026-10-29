"""Logical byte-copy model for the public COPY565 descriptor ABI.

This derives only the descriptor semantics: source base, packed source size,
stride, signed source/destination pixel coordinates, and packed requested
extent.  It is deliberately not a bus or RTL model.  GPU traffic is funnelled
through gpu_read()/gpu_write(), which are byte addressed and range checked so
protected tests can inject independent read, write, canary and bounds faults.
"""
from rv32_model import RV32, SCRATCH, signed

COPY_OP = 0x1d000000
SCRATCH_END = SCRATCH + 128


class CopyCPU(RV32):
    """RV32 plus a bounded, non-overlapping RGB565 rectangle copy.

    gpu_reads/gpu_byte_writes hold byte addresses, not native transaction
    records.  They are intentionally separate from the CPU's own accesses.
    """

    def __init__(self, *args, **kwargs):
        self.gpu_reads = []
        self.gpu_byte_writes = []
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checked_range(address, size):
        """Return the byte-address range, rejecting any scratch overflow."""
        if not isinstance(size, int) or size < 0:
            raise ValueError("invalid GPU scratch access size")
        if address < SCRATCH or address + size > SCRATCH_END:
            raise ValueError(f"GPU range {address:#x}+{size} outside scratch")
        return range(address, address + size)

    def gpu_read(self, address, size):
        """Read bytes from scratch; validate the whole range before logging."""
        addresses = self._checked_range(address, size)
        self.gpu_reads.extend(addresses)
        return bytes(self.memory.get(a, 0) for a in addresses)

    def gpu_write(self, address, data):
        """Write bytes to scratch; validate before logging or modifying."""
        data = bytes(data)
        addresses = self._checked_range(address, len(data))
        self.gpu_byte_writes.extend(addresses)
        for offset, value in enumerate(data):
            self.memory[address + offset] = value

    def command(self, words):
        """Decode COPY locally; leave TARGET and every other command to RV32."""
        if words[0] != COPY_OP:
            return super().command(words)
        self._copy565(words)

    def _reject(self):
        """Reject a malformed/unsupported descriptor without any GPU I/O."""
        self.rejected += 1

    def _copy565(self, words):
        # The public ABI is a full eight-word packet.  Reserved word 7 and the
        # packed dimensions must be understood, otherwise reject the request.
        if len(words) != 8 or words[7] != 0:
            return self._reject()
        width = words[2] >> 16
        height = words[2] & 0xffff
        stride = words[3]
        req_width = words[6] >> 16
        req_height = words[6] & 0xffff
        if not (1 <= width <= 1024 and 1 <= height <= 512):
            return self._reject()
        if stride < width * 2 or stride % 2:
            return self._reject()
        if req_width == 0 or req_height == 0:
            return self._reject()
        if self.target is None:
            return self._reject()

        color, _z, target_width, target_height, color_stride, _z_stride = self.target
        source_x = signed(words[4] >> 16, 16)
        source_y = signed(words[4] & 0xffff, 16)
        dest_x = signed(words[5] >> 16, 16)
        dest_y = signed(words[5] & 0xffff, 16)

        # Clip in request coordinates: every copied pixel must be inside both
        # the source extent and the target rectangle.  Negative source or
        # destination coordinates are handled by starting later in the request.
        first_x = max(0, -source_x, -dest_x)
        last_x = min(req_width, width - source_x, target_width - dest_x)
        first_y = max(0, -source_y, -dest_y)
        last_y = min(req_height, height - source_y, target_height - dest_y)
        if last_x <= first_x or last_y <= first_y:
            # A fully clipped request is a legal completion with no bytes.
            self.done += 1
            return

        columns = last_x - first_x
        row_bytes = columns * 2
        source_base = words[1]
        dest_base = color
        source_rows = []
        dest_rows = []
        for row in range(first_y, last_y):
            source_address = (source_base + (source_y + row) * stride
                              + (source_x + first_x) * 2)
            dest_address = (dest_base + (dest_y + row) * color_stride
                            + (dest_x + first_x) * 2)
            source_rows.append((source_address, source_address + row_bytes))
            dest_rows.append((dest_address, dest_address + row_bytes))

        # Only disjoint rectangles are supported.  Reject before any read so
        # the model never has to invent an overlap order.
        for source_start, source_end in source_rows:
            for dest_start, dest_end in dest_rows:
                if source_start < dest_end and dest_start < source_end:
                    return self._reject()

        # Read every source row first.  This preserves the source even if a
        # future layout were to allow overlap, and it keeps the byte footprint
        # independent of destination writes.
        chunks = []
        for index, (source_address, _source_end) in enumerate(source_rows):
            chunks.append((dest_rows[index][0],
                           self.gpu_read(source_address, row_bytes)))
        for dest_address, data in chunks:
            self.gpu_write(dest_address, data)
        self.done += 1
