#!/usr/bin/env python3
"""Producer and consumer graph of an art job chain: the contracts between modules.

An extraction can be right module by module and still break the chain: a product label or
instance name changes, an Assns a downstream module reads goes away, or a FHiCL parameter
of another module stops pointing at anything. This script builds the graph that shows those
contracts, from two things art writes without reading module source:

  - the resolved configuration of each stage: `lar -c <job>.fcl --debug-config <job>.cfg.fcl`;
  - the product list of each stage's input file, and if you have it, its output file:
    `lar -c eventdump.fcl -s <file> -n 1 > <file>.dump`.

An edge is a string parameter of one module whose value names another module's label as an
input tag (`label`, `label:instance` or `label:instance:process`). Labels are matched
against the modules in the job and the producers in the input file.

art's own `--data-dependency-graph` is not enough here: it is built from `consumes` calls,
and on the DUNE FD 1x2x6 reco1 and reco2 jobs (dunesw v10_22_00d01, 2026-11-19) it showed
no product edge that the path order did not already give. Many LArSoft modules read with
`getByLabel` and declare nothing. The FHiCL tags are the wiring people actually maintain.

Subcommands:

  stage   --config CFG [--input-products DUMP] [--output-products DUMP] [-o JSON]
          one job: modules, paths, products, and every tag edge with its resolution
  impact  LABEL STAGE.json...   (stages in chain order)
          what downstream modules, in this stage and later ones, read from LABEL: the
          products, instances and parameters an extraction of LABEL must keep stable
  check   STAGE.json...
          problems in the wiring: a tag that resolves to nothing, a consumer that runs
          before its producer, a missing instance. Exit 1 if any error.
  diff    BEFORE.json AFTER.json
          products and edges that differ between two builds of the same stage. Exit 1 if
          they differ. Use it on the base and the extracted build, same job and input.
  dot     STAGE.json...   Graphviz DOT of the product edges

Regex- and heuristic-based, like the other kit scripts. A tag in a parameter whose value is
built in C++ (for example an instance name appended in code) is invisible to it. A string
that happens to equal a module label is reported as an edge; check the parameter name.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

# --------------------------------------------------------------------------- FHiCL dump

_TOKEN_RE = re.compile(
    r'\s+|#[^\n]*|//[^\n]*|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[{}\[\]:,]|[^\s{}\[\]:,"\']+'
)


def _tokens(text: str):
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ValueError(f"cannot tokenise FHiCL at offset {pos}: {text[pos:pos + 40]!r}")
        tok = m.group(0)
        pos = m.end()
        if tok[0].isspace() or tok.startswith("#") or tok.startswith("//"):
            continue
        yield tok


class _Parser:
    def __init__(self, text: str) -> None:
        self.toks = list(_tokens(text))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want: str | None = None) -> str:
        tok = self.peek()
        if tok is None or (want is not None and tok != want):
            raise ValueError(f"FHiCL parse: expected {want!r}, got {tok!r} at token {self.i}")
        self.i += 1
        return tok

    def table_body(self, closing: str | None) -> dict:
        out: dict = {}
        while self.peek() is not None and self.peek() != closing:
            key = self.take()
            self.take(":")
            out[key] = self.value()
        if closing is not None:
            self.take(closing)
        return out

    def value(self):
        tok = self.peek()
        if tok == "{":
            self.take("{")
            return self.table_body("}")
        if tok == "[":
            self.take("[")
            seq = []
            while self.peek() != "]":
                seq.append(self.value())
                if self.peek() == ",":
                    self.take(",")
            self.take("]")
            return seq
        tok = self.take()
        if tok[0] in "\"'":
            return bytes(tok[1:-1], "utf-8").decode("unicode_escape")
        if tok in ("true", "false"):
            return tok == "true"
        return _Atom(tok)


class _Atom(str):
    """An unquoted FHiCL value (number, nil, infinity); never treated as an input tag."""


def parse_fhicl(text: str) -> dict:
    return _Parser(text).table_body(None)


# --------------------------------------------------------------------------- product dump

_PRINCIPAL_RE = re.compile(r"^PRINCIPAL TYPE:\s*(\w+)")


def parse_eventdump(text: str) -> list[dict]:
    """Products from `lar -c eventdump.fcl` output: process, label, instance, type, branch."""
    products: list[dict] = []
    branch = None
    seen = set()
    for line in text.splitlines():
        m = _PRINCIPAL_RE.match(line)
        if m:
            branch = m.group(1)
            continue
        if branch is None or " | " not in line or line.startswith("PROCESS NAME"):
            continue
        cols = [c.strip() for c in line.split(" | ")]
        if len(cols) != 5:
            continue
        process, label, instance, ptype = (c.rstrip(".") for c in cols[:4])
        key = (branch, process, label, instance, ptype)
        if key in seen:
            continue
        seen.add(key)
        products.append(
            {"branch": branch, "process": process, "label": label, "instance": instance, "type": ptype}
        )
    return products


# --------------------------------------------------------------------------- one stage

_MODULE_KINDS = ("producers", "filters", "analyzers")
_TAG_KEY_RE = re.compile(r"(label|tag|producer|module)s?(vec|list)?$", re.I)
_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SKIP_KEYS = {"module_type", "module_label", "tool_type", "service_provider", "plugin_type"}


def _walk_strings(node, path: str):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _SKIP_KEYS:
                continue
            yield from _walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str) and not isinstance(node, _Atom):
        yield path, node


def _split_tag(s: str):
    parts = s.split(":")
    if len(parts) > 3 or not _LABEL_RE.match(parts[0]):
        return None
    if any(re.search(r"[\s/=*]", p) for p in parts):
        return None
    while len(parts) < 3:
        parts.append("")
    return tuple(parts)


def _paths(physics: dict) -> tuple[dict, list, list]:
    """Path name -> ordered labels; trigger path names; end path names."""
    reserved = set(_MODULE_KINDS) | {"trigger_paths", "end_paths"}
    seqs = {k: [str(x) for x in v] for k, v in physics.items() if k not in reserved and isinstance(v, list)}
    trig = [str(x) for x in physics.get("trigger_paths", [])]
    end = [str(x) for x in physics.get("end_paths", [])]
    if not trig and not end:  # art default: every sequence is a path
        for name, labels in seqs.items():
            (end if all(lbl in physics.get("analyzers", {}) for lbl in labels) else trig).append(name)
    return {k: v for k, v in seqs.items() if k in trig or k in end}, trig, end


def build_stage(cfg: dict, in_products: list[dict], out_products: list[dict] | None) -> dict:
    physics = cfg.get("physics", {})
    process = str(cfg.get("process_name", ""))
    modules: dict[str, dict] = {}
    for kind in _MODULE_KINDS:
        for label, table in physics.get(kind, {}).items():
            if isinstance(table, dict):
                modules[label] = {"kind": kind[:-1], "type": str(table.get("module_type", "?")), "table": table}
    for label, table in cfg.get("outputs", {}).items():
        if isinstance(table, dict):
            modules[label] = {"kind": "output", "type": str(table.get("module_type", "?")), "table": table,
                              "outputCommands": [str(c) for c in table.get("outputCommands", [])]}
    paths, trig, end = _paths(physics)
    position = {}
    for name in trig:
        for i, lbl in enumerate(paths.get(name, [])):
            position.setdefault(lbl, (name, i))
    for name in end:
        for lbl in paths.get(name, []):
            position.setdefault(lbl, (name, None))

    input_by_label = defaultdict(list)
    for p in in_products:
        input_by_label[p["label"]].append(p)
    made_here = defaultdict(list)
    for p in out_products or []:
        if p["process"] == process:
            made_here[p["label"]].append(p)

    edges = []
    for consumer, info in modules.items():
        for param, value in _walk_strings(info["table"], ""):
            tag = _split_tag(value)
            if tag is None:
                continue
            label, instance, proc = tag
            key = param.split(".")[-1].split("[")[0]
            in_job = label in modules and (proc in ("", process))
            in_input = label in input_by_label
            if not (in_job or in_input or (_TAG_KEY_RE.search(key) and "output" not in key.lower())):
                continue
            if label == consumer:
                continue
            edge = {"consumer": consumer, "param": param, "tag": value, "label": label,
                    "instance": instance, "process": proc, "problems": []}
            if in_job:
                edge["source"] = "job"
                cands = made_here.get(label)
                pc, pp = position.get(consumer), position.get(label)
                if pp is None:
                    edge["problems"].append("producer is on no path (never runs)")
                elif pc and pc[1] is not None and pp[1] is not None:
                    if pc[0] != pp[0]:
                        edge["problems"].append(f"producer on path {pp[0]}, consumer on {pc[0]}")
                    elif pp[1] > pc[1]:
                        edge["problems"].append("producer runs after the consumer")
            elif in_input:
                edge["source"] = "input"
                cands = [p for p in input_by_label[label] if proc in ("", p["process"])]
            else:
                edge["source"] = "none"
                cands = []
                edge["problems"].append("unresolved: no module or input product with this label")
            if cands is not None:
                edge["products"] = sorted({p["type"] + ("" if p["instance"] == "" else f" [{p['instance']}]")
                                           for p in cands if p["branch"] == "Event"})
                if cands and instance not in {p["instance"] for p in cands}:
                    edge["problems"].append(f"no product with instance {instance!r}")
            edges.append(edge)

    return {
        "process": process,
        "source": str(cfg.get("source", {}).get("module_type", "")),
        "paths": paths,
        "trigger_paths": trig,
        "end_paths": end,
        "modules": {k: {kk: vv for kk, vv in v.items() if kk != "table"} for k, v in modules.items()},
        "input_products": in_products,
        "output_products": out_products,
        "edges": edges,
    }


# --------------------------------------------------------------------------- commands

def _load(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        with open(p) as f:
            out.append(json.load(f))
    return out


def cmd_stage(args) -> int:
    with open(args.config) as f:
        cfg = parse_fhicl(f.read())
    ins = parse_eventdump(open(args.input_products).read()) if args.input_products else []
    outs = parse_eventdump(open(args.output_products).read()) if args.output_products else None
    stage = build_stage(cfg, ins, outs)
    text = json.dumps(stage, indent=1, sort_keys=True)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text + "\n")
    else:
        print(text)
    n_prob = sum(bool(e["problems"]) for e in stage["edges"])
    print(f"{stage['process']}: {len(stage['modules'])} modules, {len(stage['edges'])} tag edges, "
          f"{n_prob} with problems", file=sys.stderr)
    return 0


def _made_by(stage: dict, label: str) -> list[dict]:
    if stage.get("output_products") is None:
        return []
    return [p for p in stage["output_products"] if p["label"] == label and p["process"] == stage["process"]]


def cmd_impact(args) -> int:
    stages = _load(args.stages)
    home = next((i for i, s in enumerate(stages) if args.label in s["modules"]), None)
    if home is None:
        print(f"{args.label}: not a module in any stage given", file=sys.stderr)
        return 2
    st = stages[home]
    mod = st["modules"][args.label]
    print(f"# Downstream contract of `{args.label}` ({mod['type']}, process {st['process']})\n")
    made = _made_by(st, args.label)
    print("## Products it makes\n")
    if made:
        print("| branch | type | instance |\n|---|---|---|")
        for p in sorted(made, key=lambda p: (p["branch"], p["type"], p["instance"])):
            print(f"| {p['branch']} | `{p['type']}` | `{p['instance']}` |")
    else:
        print("Not known: give `stage` an `--output-products` dump of this stage's output file.")
    print("\n## What reads it\n")
    rows = []
    for i, s in enumerate(stages[home:], start=home):
        for e in s["edges"]:
            if e["label"] != args.label:
                continue
            if i == home and e["source"] != "job":
                continue
            if i > home and (e["source"] != "input" or e["process"] not in ("", st["process"])):
                continue
            rows.append((s["process"], e))
    if rows:
        print("| stage | consumer | type | parameter | tag | products under that label | problems |")
        print("|---|---|---|---|---|---|---|")
        for proc, e in rows:
            ctype = next(s for s in stages if s["process"] == proc)["modules"][e["consumer"]]["type"]
            prods = "<br>".join(f"`{x}`" for x in e.get("products", [])) or "?"
            print(f"| {proc} | `{e['consumer']}` | {ctype} | `{e['param']}` | `{e['tag']}` | {prods} | "
                  f"{'; '.join(e['problems'])} |")
    else:
        print("No module in the stages given names it in a FHiCL tag.")
    later = [s for s in stages[home + 1:]]
    if made and later:
        nxt = later[0]
        on_next = {(p["label"], p["instance"], p["type"]) for p in nxt["input_products"]
                   if p["process"] == st["process"]}
        dropped = [p for p in made if (p["label"], p["instance"], p["type"]) not in on_next]
        print(f"\n## Kept for the next stage ({nxt['process']})\n")
        if dropped:
            print("Not in the next stage's input file (dropped by `outputCommands`, or a different file):\n")
            for p in dropped:
                print(f"- `{p['type']}` `{p['instance']}`")
        else:
            print("Every product above is in the next stage's input file.")
    print("\nRead in C++ by instance names the FHiCL does not show, and products found by type "
          "(`getMany`, `getView` without a tag), do not appear here. Check the consumers' source.")
    return 0


def cmd_check(args) -> int:
    """Errors: path order. Warnings: missing instance. Unresolved names: counted per module.

    A parameter called ...Label whose value matches nothing is often not an art tag at all
    (Pandora shower tools name their own intermediate results that way), so unresolved
    names are listed only with --unresolved and are never errors.
    """
    errors = 0
    for s in _load(args.stages):
        unresolved = defaultdict(list)
        for e in s["edges"]:
            if not e["problems"]:
                continue
            if e["source"] == "none":
                unresolved[e["consumer"]].append(e)
                continue
            hard = any("after" in p or "path" in p for p in e["problems"])
            errors += hard
            print(f"{'ERROR' if hard else 'warn '} {s['process']}: {e['consumer']}.{e['param']} = "
                  f"{e['tag']!r}: {'; '.join(e['problems'])}")
        for consumer, es in sorted(unresolved.items()):
            names = sorted({e["tag"] for e in es})
            print(f"note  {s['process']}: {consumer}: {len(es)} tag-like parameters name nothing in the "
                  f"job or input ({', '.join(names[:6])}{', ...' if len(names) > 6 else ''})")
            if args.unresolved:
                for e in es:
                    print(f"        {e['param']} = {e['tag']!r}")
    return 1 if errors else 0


def _edge_key(e: dict) -> tuple:
    return (e["consumer"], e["param"], e["tag"], e["source"], tuple(e["problems"]))


def _fmt_product(p: tuple) -> str:
    d = dict(p)
    return f"{d['type']} {d['label']}:{d['instance']}:{d['process']} ({d['branch']})"


def _fmt_edge(k: tuple) -> str:
    consumer, param, tag, source, problems = k
    tail = f"  [{'; '.join(problems)}]" if problems else ""
    return f"{consumer}.{param} = {tag!r} from {source}{tail}"


def cmd_diff(args) -> int:
    a, b = _load([args.before, args.after])
    differ = False
    for what, fmt, ka, kb in (
        ("module", lambda k: f"{k[0]} ({k[1]})", {(k, v["type"]) for k, v in a["modules"].items()},
         {(k, v["type"]) for k, v in b["modules"].items()}),
        ("product", _fmt_product, {tuple(sorted(p.items())) for p in a.get("output_products") or []},
         {tuple(sorted(p.items())) for p in b.get("output_products") or []}),
        ("edge", _fmt_edge, {_edge_key(e) for e in a["edges"]}, {_edge_key(e) for e in b["edges"]}),
    ):
        for x in sorted(ka - kb):
            print(f"- {what}: {fmt(x)}")
            differ = True
        for x in sorted(kb - ka):
            print(f"+ {what}: {fmt(x)}")
            differ = True
    if a.get("output_products") is None or b.get("output_products") is None:
        print("note: output products missing on one side; only edges and modules compared", file=sys.stderr)
    print("identical" if not differ else "DIFFERENT")
    return 1 if differ else 0


def cmd_dot(args) -> int:
    print("digraph chain {\n  rankdir=LR\n  node [shape=box fontsize=10]")
    for s in _load(args.stages):
        proc = s["process"]
        print(f'  subgraph "cluster_{proc}" {{ label="{proc}"')
        for label, m in s["modules"].items():
            print(f'    "{proc}/{label}" [label="{label}\\n{m["type"]}"]')
        print("  }")
        for e in s["edges"]:
            if e["source"] == "job":
                src = f"{proc}/{e['label']}"
            elif e["source"] == "input":
                procs = sorted({p["process"] for p in s["input_products"] if p["label"] == e["label"]
                                and e["process"] in ("", p["process"])})
                src = f"{procs[-1] if procs else 'input'}/{e['label']}"
            else:
                src = f"missing/{e['label']}"
            color = "red" if e["problems"] else "black"
            inst = f":{e['instance']}" if e["instance"] else ""
            print(f'  "{src}" -> "{proc}/{e["consumer"]}" [label="{inst}" color={color} fontsize=8]')
    print("}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("stage", help="graph of one job from its --debug-config dump")
    p.add_argument("--config", required=True, help="output of lar -c JOB --debug-config FILE")
    p.add_argument("--input-products", help="eventdump output for the job's input file")
    p.add_argument("--output-products", help="eventdump output for the job's output file")
    p.add_argument("-o", "--output", help="write JSON here (default stdout)")
    p.set_defaults(func=cmd_stage)

    p = sub.add_parser("impact", help="what downstream modules read from one module")
    p.add_argument("label")
    p.add_argument("stages", nargs="+", help="stage JSON files in chain order")
    p.set_defaults(func=cmd_impact)

    p = sub.add_parser("check", help="wiring problems; exit 1 on errors")
    p.add_argument("stages", nargs="+")
    p.add_argument("--unresolved", action="store_true", help="list every unresolved parameter")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("diff", help="compare two builds of one stage; exit 1 if different")
    p.add_argument("before")
    p.add_argument("after")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("dot", help="Graphviz DOT of the product edges")
    p.add_argument("stages", nargs="+")
    p.set_defaults(func=cmd_dot)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
