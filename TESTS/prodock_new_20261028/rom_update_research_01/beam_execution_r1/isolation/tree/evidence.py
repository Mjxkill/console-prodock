#!/usr/bin/env python3
"""Read-only evidence extractor for GW5AST-138/AE350 BSRAM/ITCM update documentation."""
import argparse, hashlib, json, re, sys
from pathlib import Path

SOURCES = {
    "SUG100_excerpts.txt": "SUG100",
    "SUG1220_excerpts.txt": "SUG1220",
    "MUG1031_excerpts.txt": "MUG1031",
    "IPUG913_excerpts.txt": "IPUG913",
}
ALIASES = {
    "claim": ("claim", "text", "statement", "finding", "result", "description"),
    "source": ("source", "source_file", "file", "document", "manual", "src"),
    "pdf_page": ("pdf_page", "pdfpage", "pdf", "page", "page_pdf"),
    "printed_page": ("printed_page", "printedpage", "printed", "document_page", "print_page"),
    "limitation": ("limitation", "caveat", "limit", "scope", "note", "boundary"),
}
KEY_TERMS = [
    "merge_bit", "gen_posp", ".posp", "AE350", "GW5A(S)(T)-138", "ITCM", "BSRAM",
    "bit_incl_bsram_init", "bsram_init_print_mode", "make_hex", "Post-Place File",
]


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def split_pages(text):
    out = {}
    for part in re.split(r"(?===== PDF page )", text):
        m = re.search(r"PDF page (\d+),", part)
        if m:
            out[int(m.group(1))] = part
    return out


def printed_page(block):
    ms = re.findall(r"(\d+)\((\d+)\)", block)
    if not ms:
        return None, None
    n, total = ms[-1]
    return int(n), int(total)


def norm_key(k):
    return re.sub(r"[\s_\-]+", "", str(k)).lower()


def field(entry, name):
    wanted = {norm_key(x) for x in ALIASES[name]}
    for k, v in entry.items():
        if norm_key(k) in wanted:
            return v
    return None


def load_claims(path):
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return data
    for key in ("claims", "findings", "evidence", "results", "entries"):
        if isinstance(data.get(key), list):
            return data[key]
    raise ValueError("findings.json contains no claim list")


def main():
    parser = argparse.ArgumentParser(description="Validate and summarize manual evidence")
    parser.add_argument("--findings", default="findings.json")
    parser.add_argument("--search", help="extra term to locate in excerpts")
    args = parser.parse_args()

    expected = json.loads(Path("source_sha.json").read_text())
    blocks = {}
    for source, code in SOURCES.items():
        p = Path(source)
        if not p.is_file():
            raise SystemExit(f"missing source: {source}")
        actual = sha256_file(p)
        if expected.get(source) and actual != expected[source]:
            raise SystemExit(f"SHA mismatch for {source}")
        blocks[source] = split_pages(p.read_text())

    claims = load_claims(args.findings)
    errors = []
    for i, entry in enumerate(claims, 1):
        source = field(entry, "source")
        if source not in blocks:
            errors.append(f"claim {i}: unknown source {source!r}")
            continue
        try:
            pdf = int(field(entry, "pdf_page"))
        except (TypeError, ValueError):
            errors.append(f"claim {i}: missing/invalid pdf_page")
            continue
        if pdf not in blocks[source]:
            errors.append(f"claim {i}: PDF page {pdf} not found in {source}")
            continue
        page_text = blocks[source][pdf]
        printed = field(entry, "printed_page")
        actual_printed, _ = printed_page(page_text)
        if printed is not None and actual_printed is not None and int(printed) != actual_printed:
            errors.append(f"claim {i}: printed page {printed} != actual {actual_printed}")
            continue
        if not field(entry, "claim"):
            errors.append(f"claim {i}: missing claim text")
            continue
        if not field(entry, "limitation"):
            errors.append(f"claim {i}: missing limitation")
            continue

    if errors:
        for e in errors:
            print(e)
        raise SystemExit(1)

    terms = list(KEY_TERMS)
    if args.search:
        terms.append(args.search)
    print("Term/page occurrences (case-insensitive):")
    for term in terms:
        hits = []
        for source in sorted(blocks):
            for pdf in sorted(blocks[source]):
                if term.lower() in blocks[source][pdf].lower():
                    printed, _ = printed_page(blocks[source][pdf])
                    suffix = f" (printed p.{printed})" if printed else ""
                    hits.append(f"{source} PDF p.{pdf}{suffix}")
        if hits:
            print(f"  {term}: " + "; ".join(hits))
        else:
            print(f"  {term}: not found in examined scope")

    sources_ok = len(blocks)
    print(f"Evidence summary: sources={sources_ok} SHA-verified; claims={len(claims)} validated; term occurrences reported above.")
    print("Summary: all cited sources/PDF pages and printed pages validated successfully.")


if __name__ == "__main__":
    main()
