#!/usr/bin/env python3
"""Physics-level before-and-after comparison for a phase-1 extraction, run by a human.

Two steps, both with PyROOT from the experiment's own environment (it needs the art and
LArSoft dictionaries to read products, so run it where `lar` runs):

  flatten  read art products from an art/ROOT event file and write a flat TTree: one row per
           object, with run, subrun, event and the object's index, plus the fields you ask
           for. Also one row per event with the collection sizes.
  compare  read two flat files (from flatten, or two TFileService analysis trees), and for
           every numeric branch: fill the same histogram from both, overlay them with a ratio
           panel, run KS and chi2 tests, and check the values row by row. Writes PNGs, one
           PDF with every plot, and summary.md. Exit status 0 means identical row by row.

A pure refactor must give identical rows, so the row-by-row check is the verdict. The
histograms are for people: they show what a difference does to the physics. They are not a
pass criterion. In the SpacePointSolver test (2026-11-01) a one-character change to a
convergence test moved 7,000 of 140,000 downstream hits to other wires, and most hit
histograms stayed bin-for-bin identical (KS p up to 0.92 on space-point positions).

Before you trust an IDENTICAL:
  - read the range column of summary.md: identical garbage on both sides (for example a
    pointer read as an array, which gives values near 1e18) also compares as identical;
  - check that each configuration changes the product counts from production, or say why it
    cannot on your sample (coverage);
  - run a positive control once: a deliberately changed build must give DIFFERENT.

Use the object's value accessors in --field expressions (recob::SpacePoint: o.position().X(),
o.covariance(0,0)), not methods that return raw pointers such as XYZ().

Examples:

  art_physics.py flatten after_art.root -o after_flat.root \\
      --branch 'sp=recob::SpacePoints_spsolve__SPS.' \\
      --field 'sp:x=o.position().X()' --field 'sp:y=o.position().Y()' \\
      --field 'sp:z=o.position().Z()' \\
      --branch 'q=recob::PointCharges_spsolve__SPS.' --field 'q:charge=o.charge()' \\
      --assns 'sphit=recob::Hitrecob::SpacePointvoidart::Assns_spsolve__SPS.'
  art_physics.py compare before_flat.root after_flat.root --out cmp/ --label before,after
  art_physics.py compare before_hist.root after_hist.root --tree ana/tree --out cmp/
"""

from __future__ import annotations

import argparse
import array
import math
import os
import re
import sys

sys.dont_write_bytecode = True


def _root():
    try:
        import ROOT  # noqa: F401
    except ImportError:
        sys.exit("PyROOT not found: run this from the experiment environment (where lar runs)")
    ROOT.gROOT.SetBatch(True)
    ROOT.gErrorIgnoreLevel = ROOT.kWarning
    return ROOT


# ------------------------------------------------------------------------------ flatten

_TREE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _compile(expr: str):
    """Field expressions are Python evaluated with the object bound to `o`. They come from
    the person running the script, never from the files being read."""
    return compile(expr, f"<field {expr}>", "eval")


# art::Assns keeps its Ptrs transient; only vector<pair<art::RefCore, size_t>> is stored.
# TTree::Draw misreads size_t in these unsplit objects and cling lacks the full RefCore
# type, so read the keys through the dictionary layout (from the DisambigFromSpacePoints
# regression test, 2026-10-16).
_ASSNS_KEYS = """
#include "TClass.h"
#include <cstring>
#include <vector>
std::vector<unsigned long> a2p_assns_keys(void* obj, const char* cls, const char* member) {
  std::vector<unsigned long> out;
  TClass* c = TClass::GetClass(cls);
  TClass* pc = TClass::GetClass("std::pair<art::RefCore,unsigned long>");
  if (!c || !pc) return out;
  char* vec = static_cast<char*>(obj) + c->GetDataMemberOffset(member);
  Long_t soff = pc->GetDataMemberOffset("second");
  size_t stride = pc->Size();
  char* b; char* e;  // libstdc++ vector layout: begin, end, capacity
  std::memcpy(&b, vec, sizeof b);
  std::memcpy(&e, vec + sizeof b, sizeof e);
  for (char* p = b; p < e; p += stride) {
    unsigned long k;
    std::memcpy(&k, p + soff, sizeof k);
    out.push_back(k);
  }
  return out;
}
"""


def flatten(args: argparse.Namespace) -> int:
    ROOT = _root()
    branches = {}
    for item in args.branch:
        tree, sep, name = item.partition("=")
        if not sep or not _TREE_NAME.match(tree):
            sys.exit(f"--branch expects TREE=BRANCH with TREE a plain name, got {item!r}")
        branches[tree] = name
    assns = {}
    for item in args.assns or []:
        tree, sep, name = item.partition("=")
        if not sep or not _TREE_NAME.match(tree) or tree in branches:
            sys.exit(f"--assns expects TREE=BRANCH with a new plain TREE name, got {item!r}")
        assns[tree] = name
    if assns:
        ROOT.gInterpreter.Declare(_ASSNS_KEYS)
    fields = {t: [] for t in branches}
    for item in args.field or []:
        tree, sep, rest = item.partition(":")
        name, sep2, expr = rest.partition("=")
        if not sep or not sep2 or tree not in branches or not _TREE_NAME.match(name):
            sys.exit(f"--field expects TREE:NAME=EXPR for a --branch TREE, got {item!r}")
        fields[tree].append((name, _compile(expr)))

    events = ROOT.TChain("Events")
    for path in args.file:
        if not events.Add(path, 0):
            sys.exit(f"cannot open {path} or it has no Events tree")
    for tree, name in list(branches.items()):
        if not events.GetBranch(name) and args.skip_missing:
            print(f"skipping {tree}: no branch {name}")
            del branches[tree]
            continue
        if not events.GetBranch(name):
            have = sorted(b.GetName() for b in events.GetListOfBranches())
            hint = [b for b in have if name.split("_")[0] in b]
            sys.exit(f"{args.file[0]}: no branch {name}. Similar: {hint[:10]}")

    assns_cls = {}
    for tree, name in list(assns.items()):
        br = events.GetBranch(name)
        if not br:
            if args.skip_missing:
                print(f"skipping {tree}: no branch {name}")
                del assns[tree]
                continue
            sys.exit(f"{args.file[0]}: no branch {name}")
        m = re.match(r"^art::Wrapper<(.*)>$", br.GetClassName().strip())
        if not m or not m.group(1).startswith("art::Assns<"):
            sys.exit(f"{name} is not an art::Assns product ({br.GetClassName()})")
        assns_cls[tree] = m.group(1).strip()

    fout = ROOT.TFile(args.output, "RECREATE")
    out_trees, buffers = {}, {}
    for tree in branches:
        t = ROOT.TTree(tree, f"one row per object of {branches[tree]}")
        buf = {k: array.array("q", [0]) for k in ("run", "subrun", "event", "idx")}
        for k, b in buf.items():
            t.Branch(k, b, f"{k}/L")
        for name, _ in fields[tree]:
            buf[name] = array.array("d", [0.0])
            t.Branch(name, buf[name], f"{name}/D")
        out_trees[tree], buffers[tree] = t, buf
    for tree in assns:
        t = ROOT.TTree(tree, f"one row per pair of {assns[tree]}, in stored order")
        buf = {k: array.array("q", [0]) for k in ("run", "subrun", "event", "idx", "key1", "key2")}
        for k, b in buf.items():
            t.Branch(k, b, f"{k}/L")
        out_trees[tree], buffers[tree] = t, buf
    ev_tree = ROOT.TTree("events", "one row per event: collection sizes")
    ev_buf = {k: array.array("q", [0]) for k in ("run", "subrun", "event")}
    for tree in list(branches) + list(assns):
        ev_buf[f"n_{tree}"] = array.array("q", [0])
    for k, b in ev_buf.items():
        ev_tree.Branch(k, b, f"{k}/L")

    n = events.GetEntries()
    if args.max_events is not None:
        n = min(n, args.max_events)
    for i in range(n):
        events.GetEntry(i)
        aux = events.EventAuxiliary
        rse = (aux.run(), aux.subRun(), aux.event())
        ev_buf["run"][0], ev_buf["subrun"][0], ev_buf["event"][0] = rse
        for tree, name in branches.items():
            wrapper = getattr(events, name)
            coll = wrapper.product() if wrapper.isPresent() else []
            ev_buf[f"n_{tree}"][0] = len(coll)
            buf = buffers[tree]
            for j, o in enumerate(coll):
                buf["run"][0], buf["subrun"][0], buf["event"][0] = rse
                buf["idx"][0] = j
                for fname, code in fields[tree]:
                    buf[fname][0] = float(eval(code, {"math": math}, {"o": o}))
                out_trees[tree].Fill()
        for tree, name in assns.items():
            wrapper = getattr(events, name)
            k1 = k2 = []
            if wrapper.isPresent():
                obj = wrapper.product()
                k1 = list(ROOT.a2p_assns_keys(obj, assns_cls[tree], "ptr_data_1_"))
                k2 = list(ROOT.a2p_assns_keys(obj, assns_cls[tree], "ptr_data_2_"))
                if len(k1) != len(k2):
                    sys.exit(f"event {rse} {tree}: {len(k1)} left keys but {len(k2)} right keys")
            ev_buf[f"n_{tree}"][0] = len(k1)
            buf = buffers[tree]
            for j, (a, b) in enumerate(zip(k1, k2)):
                buf["run"][0], buf["subrun"][0], buf["event"][0] = rse
                buf["idx"][0], buf["key1"][0], buf["key2"][0] = j, a, b
                out_trees[tree].Fill()
        ev_tree.Fill()
    sizes = ", ".join(f"{t}: {out_trees[t].GetEntries()} rows" for t in out_trees)
    fout.Write()
    fout.Close()
    print(f"{args.output}: {n} events; {sizes}")
    return 0


# ------------------------------------------------------------------------------ compare

_SKIP_HIST = {"run", "subrun", "event", "idx"}


def _numeric_branches(tree):
    out = []
    for leaf in tree.GetListOfLeaves():
        if leaf.GetLen() != 1:  # arrays: flatten them first
            continue
        if leaf.GetTypeName() in ("Double_t", "Float_t", "Int_t", "UInt_t", "Long64_t",
                                  "ULong64_t", "Short_t", "UShort_t", "Bool_t", "Char_t",
                                  "UChar_t", "Long_t", "ULong_t"):
            out.append(leaf.GetName())
    return out


def _column(tree, name):
    try:
        import ROOT
        return [float(x) for x in ROOT.RDataFrame(tree).AsNumpy([name])[name]]
    except Exception:  # no numpy in this environment: slower loop
        pass
    n = tree.GetEntries()
    vals = [0.0] * n
    leaf = tree.GetLeaf(name)
    for i in range(n):
        tree.GetEntry(i)
        vals[i] = leaf.GetValue()
    return vals


def _trees_in(f, ROOT, prefix=""):
    out = []
    for key in f.GetListOfKeys():
        obj = key.ReadObj()
        path = f"{prefix}{key.GetName()}"
        if obj.InheritsFrom("TTree"):
            out.append(path)
        elif obj.InheritsFrom("TDirectory"):
            out.extend(_trees_in(obj, ROOT, path + "/"))
    return sorted(set(out))


def _draw(ROOT, name, ha, hb, labels, path, stats):
    c = ROOT.TCanvas(f"c_{name}", name, 800, 700)
    top = ROOT.TPad("top", "", 0, 0.3, 1, 1)
    bot = ROOT.TPad("bot", "", 0, 0, 1, 0.3)
    top.SetBottomMargin(0.02)
    bot.SetTopMargin(0.02)
    bot.SetBottomMargin(0.3)
    top.Draw()
    bot.Draw()
    top.cd()
    # Okabe-Ito blue and vermillion: readable for colour-blind viewers and in greyscale
    # because one is a filled line and the other open markers.
    ha.SetLineColor(ROOT.TColor.GetColor("#0072B2"))
    ha.SetLineWidth(2)
    hb.SetMarkerColor(ROOT.TColor.GetColor("#D55E00"))
    hb.SetLineColor(ROOT.TColor.GetColor("#D55E00"))
    hb.SetMarkerStyle(24)
    ha.SetStats(0)
    peak = max(ha.GetMaximum(), hb.GetMaximum(), 1)
    filled = sorted(ha.GetBinContent(i) for i in range(1, ha.GetNbinsX() + 1) if ha.GetBinContent(i) > 0)
    if filled and peak > 50 * filled[len(filled) // 2]:  # long tail: log scale
        top.SetLogy()
        ha.SetMinimum(0.5)
        ha.SetMaximum(5 * peak)
    else:
        ha.SetMaximum(1.25 * peak)
    ha.GetXaxis().SetLabelSize(0)
    ha.SetTitle(name)
    ha.Draw("hist")
    hb.Draw("e1 same")
    leg = ROOT.TLegend(0.55, 0.72, 0.89, 0.89)
    leg.SetBorderSize(0)
    leg.AddEntry(ha, f"{labels[0]} ({int(ha.GetEntries())})", "l")
    leg.AddEntry(hb, f"{labels[1]} ({int(hb.GetEntries())})", "p")
    leg.AddEntry(ROOT.nullptr, f"KS p={stats['ks']:.3g}  #chi^{{2}} p={stats['chi2']:.3g}", "")
    leg.Draw()
    bot.cd()
    r = hb.Clone(f"r_{name}")
    r.Divide(ha)
    r.SetTitle("")
    r.SetStats(0)
    r.SetMinimum(0.8)
    r.SetMaximum(1.2)
    r.GetYaxis().SetTitle(f"{labels[1]}/{labels[0]}")
    r.GetYaxis().SetNdivisions(505)
    for ax in (r.GetXaxis(), r.GetYaxis()):
        ax.SetLabelSize(0.09)
        ax.SetTitleSize(0.1)
    r.GetYaxis().SetTitleOffset(0.4)
    r.GetXaxis().SetTitle(name)
    r.Draw("e1")
    line = ROOT.TLine(r.GetXaxis().GetXmin(), 1, r.GetXaxis().GetXmax(), 1)
    line.SetLineStyle(2)
    line.Draw()
    c.SaveAs(path)
    return c, [top, bot, leg, r, line]


def compare(args: argparse.Namespace) -> int:
    ROOT = _root()
    labels = args.label.split(",")
    if len(labels) != 2:
        sys.exit("--label expects two names separated by a comma")
    fa, fb = ROOT.TFile.Open(args.file_a), ROOT.TFile.Open(args.file_b)
    if not fa or not fb or fa.IsZombie() or fb.IsZombie():
        sys.exit("cannot open one of the input files")
    trees = args.tree or sorted(set(_trees_in(fa, ROOT)) | set(_trees_in(fb, ROOT)))
    os.makedirs(args.out, exist_ok=True)
    pdf = os.path.join(args.out, "all_plots.pdf")
    rows, ndiff, first_canvas = [], 0, True
    keep = []
    for tname in trees:
        ta, tb = fa.Get(tname), fb.Get(tname)
        if not ta or not tb:
            rows.append((tname, "-", "-", "-", "-", "-", "-", "MISSING in one file", "-"))
            ndiff += 1
            continue
        names = [b for b in _numeric_branches(ta) if b in set(_numeric_branches(tb))]
        if args.branch:
            names = [b for b in names if b in args.branch]
        for b in names:
            va, vb = _column(ta, b), _column(tb, b)
            same_len = len(va) == len(vb)
            nrow = sum(1 for x, y in zip(va, vb) if x != y) + abs(len(va) - len(vb))
            maxabs = max((abs(x - y) for x, y in zip(va, vb)), default=0.0)
            ndiff += nrow > 0
            if b in _SKIP_HIST:
                rows.append((tname, b, len(va), len(vb), nrow, f"{maxabs:.3g}", "-", "identical" if nrow == 0 else "DIFFERENT", "-"))
                continue
            lo = min(min(va, default=0.0), min(vb, default=0.0))
            hi = max(max(va, default=1.0), max(vb, default=1.0))
            if hi <= lo:
                hi = lo + 1.0
            pad = 0.02 * (hi - lo)
            hname = f"{tname.replace('/', '_')}_{b}"
            ha = ROOT.TH1D(f"a_{hname}", b, args.bins, lo - pad, hi + pad)
            hb = ROOT.TH1D(f"b_{hname}", b, args.bins, lo - pad, hi + pad)
            ha.Sumw2()
            hb.Sumw2()
            for x in va:
                ha.Fill(x)
            for x in vb:
                hb.Fill(x)
            bins_same = all(ha.GetBinContent(i) == hb.GetBinContent(i) for i in range(ha.GetNbinsX() + 2))
            stats = {
                "ks": ha.KolmogorovTest(hb) if ha.GetEntries() and hb.GetEntries() else 1.0,
                "chi2": ha.Chi2Test(hb, "UU") if ha.GetEntries() and hb.GetEntries() else 1.0,
            }
            png = os.path.join(args.out, f"{hname}.png")
            c, objs = _draw(ROOT, f"{tname}:{b}", ha, hb, labels, png, stats)
            c.Print(pdf + ("(" if first_canvas else ""), "pdf")
            first_canvas = False
            keep += [c, ha, hb, objs]
            verdict = "identical" if nrow == 0 else ("DIFFERENT (same histogram)" if bins_same else "DIFFERENT")
            if not same_len:
                verdict = f"DIFFERENT row count"
            rows.append((tname, b, len(va), len(vb), nrow, f"{maxabs:.3g}", f"{stats['ks']:.3g}", verdict,
                         f"[{min(va, default=0):.4g}, {max(va, default=0):.4g}]"))
    if not first_canvas:
        ROOT.TCanvas().Print(pdf + ")", "pdf")

    md = [f"# {labels[0]} vs {labels[1]}", "",
          f"- {labels[0]}: `{args.file_a}`", f"- {labels[1]}: `{args.file_b}`", "",
          "Check the range column: identical garbage on both sides also compares as identical.",
          "",
          "| tree | branch | rows A | rows B | rows differing | max abs diff | KS p | verdict | range A |",
          "|---|---|---|---|---|---|---|---|---|"]
    md += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    if not rows:
        ndiff = 1
        md += ["", "NOTHING COMPARED: no common trees or branches (did flatten fail?)"]
    else:
        md += ["", "IDENTICAL" if ndiff == 0 else f"DIFFERENT ({ndiff} branches differ)"]
    with open(os.path.join(args.out, "summary.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0 if ndiff == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flatten", help="art products to a flat TTree")
    f.add_argument("file", nargs="+", help="one or more art files, read in order")
    f.add_argument("-o", "--output", required=True)
    f.add_argument("--branch", action="append", default=[],
                   help="TREE=ART_BRANCH, e.g. sp=recob::SpacePoints_spsolve__SPS.")
    f.add_argument("--field", action="append",
                   help="TREE:NAME=EXPR, Python with the object as o, e.g. sp:x=o.position().X()")
    f.add_argument("--assns", action="append",
                   help="TREE=ART_BRANCH of an art::Assns: one row per pair (key1, key2), stored order")
    f.add_argument("--max-events", type=int)
    f.add_argument("--skip-missing", action="store_true",
                   help="leave out a --branch the file does not have (e.g. a product a config turns off)")
    f.set_defaults(func=flatten)
    c = sub.add_parser("compare", help="histogram and row-by-row comparison of flat TTrees")
    c.add_argument("file_a")
    c.add_argument("file_b")
    c.add_argument("--out", required=True, help="directory for PNGs, all_plots.pdf, summary.md")
    c.add_argument("--tree", action="append", help="tree path (default: every TTree in the files)")
    c.add_argument("--branch", action="append", help="only these branches (default: all numeric)")
    c.add_argument("--bins", type=int, default=50)
    c.add_argument("--label", default="before,after")
    c.set_defaults(func=compare)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
