"""Pure passive boot log classification."""

import re

_MAX_BYTES = 4 * 1024 * 1024
_RELEASE = b"6.12.112-prodock-luma3d-g3d1-sdoptin-r1"
_NR = re.compile(rb"\[\s*\d+\.\d+\]\s*")
_CTRL = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _strip_prefix(line):
    m = _NR.match(line)
    return line[m.end():] if m else line


def _stage_key(norm):
    if norm == b"PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN":
        return 0
    if norm == b"PRODOCK SD BOOT: CRC OK, U-Boot":
        return 1
    if norm.startswith(b"Pro Dock: lecture /PRODOCK/LINUX.BIN"):
        return 2
    if norm == b"Pro Dock: image verifiee, lancement":
        return 3
    prefix = b"Linux version " + _RELEASE
    if norm == prefix or norm.startswith(prefix + b" ") or norm.startswith(prefix + b"\t"):
        return 4
    if norm == b"PRODOCK_AUTOSTART: starting LUMA3D.ELF --festival":
        return 5
    if norm.startswith(b"LUMA3D_GRAPHICS_READY") and re.search(
            rb"(?<![0-9])hardware=1(?![0-9])", norm):
        return 6
    return None


def parse_boot(raw):
    if isinstance(raw, bytearray):
        raw = bytes(raw)
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    if len(raw) > _MAX_BYTES:
        raise ValueError("input too large")

    contaminated = bool(_CTRL.search(raw))
    incomplete_final = False
    segments = raw.split(b"\n")
    if raw.endswith(b"\n"):
        segments = segments[:-1]
    elif segments and segments[-1] != b"":
        segments = segments[:-1]
        incomplete_final = True
    else:
        segments = segments[:-1]

    lines = []
    for seg in segments:
        if seg.endswith(b"\r"):
            seg = seg[:-1]
        lines.append(seg)

    norms = [_strip_prefix(x) for x in lines]
    last_ready = [i for i, n in enumerate(norms)
                  if n == b"PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN"]
    if last_ready:
        start = last_ready[-1]
    else:
        linux_ids = [i for i, n in enumerate(norms) if n.startswith(b"Linux version ")]
        start = linux_ids[-1] if linux_ids else 0

    errors = []
    warnings = []
    if contaminated:
        errors.append("invalid control byte")
    if incomplete_final:
        warnings.append("unterminated final line")

    attempt_norms = norms[start:]
    attempt_keys = []
    attempt_lines = []
    for n in attempt_norms:
        k = _stage_key(n)
        if k is not None:
            attempt_keys.append(k)
            attempt_lines.append(n)

    fatal = []
    for n in attempt_norms:
        low = n.lower()
        if b"kernel panic" in low:
            fatal.append("Kernel panic")
        if b"oops:" in low:
            fatal.append("Oops")
        if b"bug:" in low:
            fatal.append("BUG")
        if b"sd/image invalide" in low or b"aucun repli ni saut" in low:
            fatal.append("SD/image invalid")
        if b"checksum mismatch" in low:
            fatal.append("PRODOCK_AUTOSTART checksum mismatch")
        if b"game exited" in low:
            m = re.search(rb"status[^0-9]*([0-9]+)", low)
            if m:
                if int(m.group(1)) != 0:
                    fatal.append("game exited with status nonzero")
            elif b"nonzero" in low:
                fatal.append("game exited with status nonzero")
    if fatal:
        seen = set()
        uniq = []
        for f in fatal:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        fatal = uniq
        errors.extend(fatal)

    game_launch = False
    if 6 in attempt_keys:
        pos6 = attempt_keys.index(6)
        if 5 in attempt_keys and attempt_keys.index(5) < pos6:
            game_launch = True
        elif 5 not in attempt_keys:
            game_launch = True

    complete = (attempt_keys == list(range(7)))
    if not complete and not fatal:
        errors.append("boot sequence incomplete")
    if not last_ready and norms:
        warnings.append("incomplete capture")

    passed = (not contaminated and not incomplete_final and not fatal
              and complete)

    return {
        "boot_log_checks_passed": bool(passed),
        "game_launch_observed": bool(game_launch),
        "gpu_tested": False,
        "powercycle_validated": False,
        "kernel_sha_measured": False,
        "game_sha_measured": False,
        "stages": attempt_lines,
        "errors": errors,
        "warnings": warnings,
    }
