#!/usr/bin/env python3
"""Verify and rebuild the immutable MAZE snapshot, without board access.

The archive is a historical source release, not a second maintained engine.
Compilation uses the original argument vector, with compiler/output supplied
explicitly. A different compiler/libc may produce a different ELF checksum.
"""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_sources(manifest):
    """Validate exact members, safe regular paths, sizes and every byte hash."""
    archive = HERE / "source.tar.gz"
    if archive.is_symlink() or sha(archive.read_bytes()) != manifest["source_archive"]["sha256"]:
        raise ValueError("Source archive checksum or file type mismatch")
    expected = manifest["files"]
    found = {}
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream.getmembers():
            name = member.name
            path = PurePosixPath(name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or str(path) != name or name not in expected or name in found):
                raise ValueError(f"Unexpected or unsafe archive member: {name}")
            if member.size != expected[name]["bytes"]:
                raise ValueError(f"Member size mismatch: {name}")
            data = stream.extractfile(member).read()
            if sha(data) != expected[name]["sha256"]:
                raise ValueError(f"Member SHA mismatch: {name}")
            found[name] = data
    if found.keys() != expected.keys():
        raise ValueError("Incomplete source archive")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--target", choices=("host", "riscv"), default="host")
    parser.add_argument("--cc", help="Compiler executable; RV32 requires an explicit compatible toolchain")
    parser.add_argument("--out", type=Path, help="New output directory; never writes the maintained tree")
    args = parser.parse_args()
    manifest = json.loads((HERE / "MANIFEST.json").read_text())
    sources = verified_sources(manifest)
    if args.verify_only:
        print(json.dumps({"passed": True, "source_files": len(sources), "hardware": False}))
        return
    if args.out is None or (args.target == "riscv" and not args.cc):
        parser.error("--out is required; RV32 also requires --cc")
    output = args.out.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a new directory")
    output.mkdir(parents=True)
    tree = output / "source"
    for name, data in sources.items():
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
    executable = output / ("luma3d-" + args.target)
    command = [args.cc or "cc"] + manifest["compiler_arguments"][args.target] + ["-o", str(executable)]
    with (output / "build.log").open("w") as log:
        status = subprocess.run(command, cwd=tree, stdout=log, stderr=subprocess.STDOUT).returncode
    result = {"passed": status == 0, "returncode": status, "hardware": False,
              "target": args.target, "command": command,
              "source_archive_sha256": manifest["source_archive"]["sha256"]}
    if status == 0:
        result.update(elf_sha256=sha(executable.read_bytes()), elf_bytes=executable.stat().st_size)
        result["matches_historical_elf"] = result["elf_sha256"] == manifest["historical_elf"][args.target]["sha256"]
    (output / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if status:
        raise SystemExit(status)


if __name__ == "__main__":
    main()
