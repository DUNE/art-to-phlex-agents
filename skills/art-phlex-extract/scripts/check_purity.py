#!/usr/bin/env python3
"""Check that extracted algorithm files are free of art (and Phlex) framework code.

Usage: check_purity.py [--json] FILE...

ERROR   framework includes or identifiers that must not appear in algorithm code
WARN    allowed, but justify it in MIGRATION_NOTES.md (cet::exception, mutable static
        state, ROOT globals and fitting, random engines, ...)
TRANS   an error on a line marked `// PHLEX-TRANSITIONAL: <reason>` (on the line itself
        or on a comment line directly above). Reported, does not fail the check. Every
        TRANS item must appear in the notes' transitional table.

FILE may be a path or git:REV:PATH (see art_inventory.py).
Exit status: 0 when there are no errors, 1 when there are errors.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the kit and of target repos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from art_inventory import LineIndex, read_source, strip_cpp  # noqa: E402

MARKER = "PHLEX-TRANSITIONAL"

INCLUDE_ERRORS = [
    (r"^art/", "art framework header"),
    (r"^art_root_io/", "art ROOT I/O (TFileService and friends)"),
    (r"^canvas/Persistency/", "art persistency: Ptr, Assns, FindMany"),
    (r"^canvas/Utilities/InputTag\.h$", "art::InputTag is configuration; resolve it at the boundary"),
    (r"^fhiclcpp/", "FHiCL: read configuration at the boundary, pass a plain struct"),
    (r"^messagefacility/", "art MessageLogger"),
    (r"^phlex/", "Phlex header: pass-1 algorithm code is framework-free in both directions"),
    (r"^nurandom/", "random-number service"),
    (r"^larcore/CoreUtils/ServiceUtil\.h$", "lar::providerFrom service access"),
    (r"^larcore/Geometry/(Geometry|WireReadout|AuxDetGeometry)\.h$", "geometry art service: pass the provider reference"),
    (r"^lardata/Utilities/AssociationUtil\.h$", "art association helpers"),
    (r"^lardata/ArtDataHelper/", "art-dependent data helpers"),
    (r"(^|/)\w*Services?(/|\.h$)|_service\.h$|DetectorInfoServices/", "art service header: pass the provider or data object"),
]
INCLUDE_WARNINGS = [
    (r"^cetlib_except/", "cet::exception: small non-art library; acceptable, note it"),
    (r"^cetlib/", "cetlib utility: usually fine; confirm no framework dependency"),
    (r"^canvas/", "canvas header outside Persistency: confirm no framework dependency"),
    (r"^(TFile|TTree|TDirectory\w*)\.h$", "ROOT file I/O in algorithm: return values and write at the boundary"),
    (r"^(TF1|TMinuit|TVirtualFitter|Fit/\w+|Minuit2/\w+)\.h$", "ROOT fitting: record the concurrency constraint"),
]
TOKEN_ERRORS = [
    (r"\bart::\w+", "art type or function"),
    (r"\bfhicl::\w+", "FHiCL type"),
    (r"\bmf::\w+|\bMF_LOG_\w+", "MessageLogger"),
    (r"\bServiceHandle\b|\bproviderFrom\b", "service access"),
    (r"\bTFileService\b", "TFileService"),
    (r"\bDEFINE_ART_\w+|\bPHLEX_REGISTER_\w+", "framework registration macro"),
    (r"\bphlex::\w+", "Phlex type"),
    (r"\b(?:produces|consumes|mayConsume)\s*<", "product declaration"),
    (r"\b(?:getByLabel|getByToken|getValidHandle|getHandle|getProduct|getManyByType)\b", "event product retrieval"),
    (r"\bfill_ptr_vector\b|\bFind(?:Many|One)P?\s*<|\bPtrMaker\b", "art pointer or association helper"),
    (r"\bmake_tool\b", "art tool construction"),
    (r"\bDataFor\s*\(", "service DataFor call: pass the resulting *Data object instead"),
]
TOKEN_WARNINGS = [
    (r"\bcet::exception\b", "cet::exception"),
    (r"^\s*static\s+(?![^;={(]*\bconst(?:expr)?\b)[^(;]*[;={]", "mutable static state: blocks concurrency::unlimited"),
    (r"\bmutable\b", "mutable: check re-entrancy"),
    (r"\bthread_local\b", "thread_local state"),
    (r"\b(?:gRandom|gMinuit|gROOT|gDirectory|gStyle|gPad)\b", "ROOT global state"),
    (r"(?:\.|->)\s*Fit\s*\(", "ROOT fit call: record the concurrency constraint"),
    (r"\bHepRandomEngine\b", "random engine: record seeding and draw-order assumptions"),
]


def _compile(rules):
    return [(re.compile(rx, re.M), why) for rx, why in rules]


INCLUDE_ERRORS, INCLUDE_WARNINGS = _compile(INCLUDE_ERRORS), _compile(INCLUDE_WARNINGS)
TOKEN_ERRORS, TOKEN_WARNINGS = _compile(TOKEN_ERRORS), _compile(TOKEN_WARNINGS)
from art_inventory import INCLUDE_RE  # noqa: E402  (shared so both scripts agree on include lines)


def is_transitional(raw_lines: list[str], line: int) -> bool:
    here = raw_lines[line - 1] if 0 < line <= len(raw_lines) else ""
    above = raw_lines[line - 2].strip() if line >= 2 else ""
    return MARKER in here or (above.startswith("//") and MARKER in above)


def check(spec: str, repo: str | None) -> list[dict]:
    text = read_source(spec, repo)
    raw_lines = text.splitlines()
    with_strings = strip_cpp(text, keep_strings=True)
    code = strip_cpp(text, keep_strings=False)
    lines = LineIndex(text)
    findings: list[dict] = []
    include_lines: set[int] = set()

    def add(level: str, line: int, what: str, why: str) -> None:
        if level == "ERROR" and is_transitional(raw_lines, line):
            level = "TRANS"
        findings.append({"level": level, "line": line, "what": what.strip(), "why": why})

    for m in INCLUDE_RE.finditer(with_strings):
        path, line = m.group(1), lines.line(m.start())
        include_lines.add(line)
        for rx, why in INCLUDE_ERRORS:
            if rx.search(path):
                add("ERROR", line, f"#include {path}", why)
                break
        else:
            for rx, why in INCLUDE_WARNINGS:
                if rx.search(path):
                    add("WARN", line, f"#include {path}", why)
                    break

    for rules, level in ((TOKEN_ERRORS, "ERROR"), (TOKEN_WARNINGS, "WARN")):
        for rx, why in rules:
            for m in rx.finditer(code):
                line = lines.line(m.start())
                if line in include_lines:
                    continue
                add(level, line, m.group(0), why)

    findings.sort(key=lambda f: (f["line"], f["level"]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--repo", help="directory to run `git show` in for git:REV:PATH arguments")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = {spec: check(spec, args.repo) for spec in args.files}
    errors = sum(1 for fs in results.values() for f in fs if f["level"] == "ERROR")
    if args.json:
        print(json.dumps({"errors": errors, "files": results}, indent=2))
        return 1 if errors else 0

    for spec, fs in results.items():
        tally = {lvl: sum(1 for f in fs if f["level"] == lvl) for lvl in ("ERROR", "WARN", "TRANS")}
        print(f"{spec}: {tally['ERROR']} error(s), {tally['WARN']} warning(s), {tally['TRANS']} transitional")
        for f in fs:
            print(f"  {f['level']:<5} L{f['line']:<5} {f['what']}  ({f['why']})")
    print(f"\n{'FAIL' if errors else 'PASS'}: {errors} error(s) across {len(results)} file(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
