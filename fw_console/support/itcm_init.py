#!/usr/bin/env python3
"""Convert a <=64 KiB image into four little-endian AE350 ITCM byte lanes.

Each byte is two lower-case hex digits followed by CRLF. An incomplete final
32-bit word is zero-padded; no additional words are emitted. See PROVENANCE.md.
"""
import argparse
from pathlib import Path

ITCM_BYTES = 65536


def write_lanes(source: Path, destination: Path) -> int:
    """Validate capacity before touching output, then emit all four lane files."""
    data = source.read_bytes()
    if len(data) > ITCM_BYTES:
        raise ValueError(f"image of {len(data)} bytes exceeds 64 KiB ITCM")
    data += b"\0" * (-len(data) % 4)
    destination.mkdir(parents=True, exist_ok=True)
    for lane in range(4):
        (destination / f"itcm{lane}").write_bytes(
            b"".join(b"%02x\r\n" % value for value in data[lane::4]))
    return len(data) // 4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        words = write_lanes(args.source, args.destination)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"itcm_init.py: {exc}\n")
    print(f"itcm_init.py: {words} words ({words * 4} bytes) -> {args.destination}/itcm0..3")


if __name__ == "__main__":
    main()
