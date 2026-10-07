#!/usr/bin/env python3
"""Before-and-after equivalence check for a phase-1 extraction, run by a human after building.

Two steps:

  wrap   write a FHiCL wrapper around a production job, so the "before" and "after" builds
         write their art and TFileService output to separate, predictable files.
  diff   compare two ROOT files (art event files, or TFileService histogram files) branch by
         branch and entry by entry, in stored order. Exit status 0 means identical.

`diff` reads the files with uproot, so it needs `pip install uproot awkward numpy` in a
virtual environment outside the experiment repository. It compares what was persisted, so it
works for any product type ROOT stored split (hits, wires, associations) without a dumper
module. Order matters: a reordered collection or association is reported as a difference.

Examples:

  art_compare.py wrap standard_reco_protodunehd_MC.fcl --prefix before -n 20 \\
      --set physics.producers.hitpdune.MoveLeftovers=\\"drop\\" > before.fcl
  art_compare.py diff before_art.root after_art.root --branch 'recob::Hit' --branch 'Assns'
  art_compare.py diff before_hist.root after_hist.root --tree hitpdune/hitstats
"""

from __future__ import annotations

import argparse
import re
import sys

sys.dont_write_bytecode = True


# ------------------------------------------------------------------------------ wrap


def wrap(args: argparse.Namespace) -> int:
    lines = [
        f'#include "{args.job}"',
        "",
        f'services.TFileService.fileName: "{args.prefix}_hist.root"',
        f'outputs.{args.output_label}.fileName: "{args.prefix}_art.root"',
    ]
    if args.keep_all:
        lines.append(f'outputs.{args.output_label}.outputCommands: [ "keep *" ]')
    if args.nevents is not None:
        lines.append(f"source.maxEvents: {args.nevents}")
    for item in args.set or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            sys.exit(f"--set expects KEY=VALUE, got {item!r}")
        lines.append(f"{key}: {value}")
    print("\n".join(lines))
    return 0


# ------------------------------------------------------------------------------ diff


def _load():
    try:
        import awkward as ak  # noqa: F401
        import numpy as np  # noqa: F401
        import uproot  # noqa: F401
    except ImportError as exc:
        sys.exit(
            f"diff needs uproot, awkward and numpy ({exc.name} is missing). Install them in a "
            "virtual environment outside the repository: pip install uproot awkward numpy"
        )
    return uproot, ak, np


def _leaves(tree, patterns: list[re.Pattern], ignore: list[re.Pattern]) -> list[str]:
    """Leaf branch paths whose full name matches any pattern (all when none) and no ignore."""
    out = []
    for name in tree.keys(recursive=True, full_paths=True):
        if tree[name].branches:  # not a leaf
            continue
        if patterns and not any(p.search(name) for p in patterns):
            continue
        if any(p.search(name) for p in ignore):
            continue
        out.append(name)
    return out


def _first_difference(a, b, ak, np, rtol: float):
    """Return (entry, detail) for the first difference between two per-entry arrays, or None."""
    if len(a) != len(b):
        return (min(len(a), len(b)), f"entry count {len(a)} vs {len(b)}")
    for i in range(len(a)):
        x, y = a[i], b[i]
        if isinstance(x, ak.Array) or isinstance(y, ak.Array):
            if ak.to_list(x) == ak.to_list(y):
                continue
            fx, fy = ak.flatten(x, axis=None), ak.flatten(y, axis=None)
            if len(fx) != len(fy):
                return (i, f"length {len(fx)} vs {len(fy)}")
            nx, ny = ak.to_numpy(fx), ak.to_numpy(fy)
        else:
            nx, ny = np.asarray(x), np.asarray(y)
        if np.issubdtype(nx.dtype, np.floating):
            if rtol:
                same = np.isclose(nx, ny, rtol=rtol, atol=0.0, equal_nan=True)
            else:
                same = (nx == ny) | (np.isnan(nx) & np.isnan(ny))
        else:
            same = nx == ny
        bad = ~np.atleast_1d(same)
        if bad.any():
            j = int(np.argmax(bad))
            vx, vy = np.atleast_1d(nx)[j].tolist(), np.atleast_1d(ny)[j].tolist()
            return (i, f"element {j}: {vx!r} vs {vy!r}")
    return None


def diff(args: argparse.Namespace) -> int:
    uproot, ak, np = _load()
    patterns = [re.compile(p) for p in args.branch or []]
    ignore = [re.compile(p) for p in args.ignore or []]
    failures = 0
    with uproot.open(args.before) as fb, uproot.open(args.after) as fa:
        for tree_name in args.tree:
            if tree_name not in fb or tree_name not in fa:
                print(f"MISSING  tree {tree_name!r} in {'before' if tree_name not in fb else 'after'}")
                failures += 1
                continue
            tb, ta = fb[tree_name], fa[tree_name]
            if not all(hasattr(t, "num_entries") and hasattr(t, "branches") for t in (tb, ta)):
                sys.exit(f"{tree_name!r} is not a TTree in both files; art and TFileService "
                         "output are TTrees")
            lb, la = _leaves(tb, patterns, ignore), _leaves(ta, patterns, ignore)
            for name in sorted(set(lb) ^ set(la)):
                where = "before only" if name in lb else "after only"
                print(f"BRANCH   {tree_name}:{name} ({where}): the framework contract changed")
                failures += 1
            common = [n for n in lb if n in set(la)]
            if not common:
                print(f"NOTHING  no branches in {tree_name!r} match the selection")
                failures += 1
                continue
            if tb.num_entries != ta.num_entries:
                print(f"ENTRIES  {tree_name}: {tb.num_entries} vs {ta.num_entries}")
                failures += 1
            same = 0
            for name in common:
                a = tb[name].array(library="ak")
                b = ta[name].array(library="ak")
                found = _first_difference(a, b, ak, np, args.rtol)
                if found:
                    entry, detail = found
                    print(f"DIFF     {tree_name}:{name} entry {entry}: {detail}")
                    failures += 1
                else:
                    same += 1
            print(f"{tree_name}: {same} of {len(common)} selected leaves identical "
                  f"over {min(tb.num_entries, ta.num_entries)} entries")
    print("PASS: identical" if failures == 0 else f"FAIL: {failures} difference(s)")
    return 0 if failures == 0 else 1


# ------------------------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("wrap", help="write a FHiCL wrapper with predictable output file names")
    w.add_argument("job", help="the FHiCL job to wrap, as found on FHICL_FILE_PATH")
    w.add_argument("--prefix", required=True, help="output file prefix, e.g. before or after")
    w.add_argument("--output-label", default="out1", help="label of the job's RootOutput (default out1)")
    w.add_argument("--keep-all", action="store_true", help='write every product ("keep *")')
    w.add_argument("-n", "--nevents", type=int, help="source.maxEvents")
    w.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="extra FHiCL override, repeatable; VALUE is written as given")
    w.set_defaults(func=wrap)

    d = sub.add_parser("diff", help="compare two ROOT files entry by entry")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--tree", action="append", help="tree path, repeatable (default: Events)")
    d.add_argument("--branch", action="append", metavar="REGEX",
                   help="compare only leaves whose path matches; repeatable (default: all)")
    d.add_argument("--ignore", action="append", metavar="REGEX",
                   help="skip leaves whose path matches, e.g. timing or provenance; repeatable")
    d.add_argument("--rtol", type=float, default=0.0,
                   help="relative tolerance for floating point (default 0: exact)")
    d.set_defaults(func=diff)

    args = ap.parse_args(argv)
    if args.cmd == "diff" and not args.tree:
        args.tree = ["Events"]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
