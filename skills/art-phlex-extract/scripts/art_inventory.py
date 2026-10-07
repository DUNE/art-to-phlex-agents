#!/usr/bin/env python3
"""Inventory art framework usage in C++ sources.

Subcommands:
  report   FILE...   framework constructs per file, grouped by kind, with line numbers
  contract FILE...   normalised framework-visible contract (module, base class, products,
                     consumes, collection-helper product declarations, FHiCL parameters,
                     tools, callbacks) for before/after diffs
  contract-diff --before FILE... --after FILE...
                     unified diff of the two contracts; exit status 1 when they differ
  scan [--rev REV] PATH...
                     rank *_module.cc files as candidates for a first extraction pass.
                     With --rev, PATHs are pathspecs inside --repo and files are read from
                     that git revision instead of the working tree.

FILE may be a filesystem path or git:REV:PATH, read with `git show REV:PATH` from the
directory given by --repo (default: the current directory).

Everything here is regex-based and heuristic. It points a reviewer at the right lines; it
does not replace reading the code. Known blind spots: products declared by helpers other
than *::declare_products / produces_using, member state changed through references or
pointers, and macros that expand to framework calls.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.dont_write_bytecode = True

SKIP_DIRS = {"test", "tests", "build"}
MAX_SOURCE_BYTES = 2_000_000  # larger files are generated or not module source
MAX_BRACKET_SCAN = 200_000  # an unclosed bracket stops the scan here instead of at EOF

# ----------------------------------------------------------------------------- input


def read_source(spec: str, repo: str | None = None) -> str:
    if spec.startswith("git:"):
        parts = spec.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            sys.exit(f"bad source spec {spec!r}: expected git:REV:PATH")
        _, rev, path = parts
        check_rev(rev)
        result = subprocess.run(
            ["git", "show", "--end-of-options", f"{rev}:{path}"],
            cwd=repo or None, capture_output=True, text=True,
        )
        if result.returncode != 0:
            sys.exit(f"git show {rev}:{path} failed: {result.stderr.strip()}")
        if len(result.stdout) > MAX_SOURCE_BYTES:
            sys.exit(f"{spec}: larger than {MAX_SOURCE_BYTES} bytes; not read")
        return result.stdout
    if repo and not os.path.isabs(spec) and not os.path.exists(spec):
        spec = os.path.join(repo, spec)
    if not os.path.isfile(spec):
        sys.exit(f"{spec}: not a regular file; not read")
    if os.path.getsize(spec) > MAX_SOURCE_BYTES:
        sys.exit(f"{spec}: larger than {MAX_SOURCE_BYTES} bytes; not read")
    with open(spec, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def check_rev(rev: str) -> None:
    """Refuse revisions that git would read as an option."""
    if rev.startswith("-"):
        sys.exit(f"bad revision {rev!r}: must not start with '-'")


def _blank(segment: str) -> str:
    return re.sub(r"[^\n]", " ", segment)


def strip_cpp(text: str, keep_strings: bool = True) -> str:
    """Blank out comments, and string/char literal contents unless keep_strings.

    Offsets and line numbers are preserved, so match positions map back to the input.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(_blank(text[i:j]))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(_blank(text[i:j]))
            i = j
        elif c == "R" and nxt == '"' and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            m = re.match(r'R"([^()\\\s]{0,16})\(', text[i:])
            if not m:
                out.append(c)
                i += 1
                continue
            close = ")" + m.group(1) + '"'
            j = text.find(close, i + m.end())
            j = n if j == -1 else j + len(close)
            seg = text[i:j]
            out.append(seg if keep_strings else 'R"' + _blank(seg[2:]))
            i = j
        elif c == '"' or (c == "'" and not (i > 0 and text[i - 1].isalnum())):
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            closed = j < n and text[j] == c
            j = min(j + 1 if closed else j, n)
            seg = text[i:j]
            if keep_strings:
                out.append(seg)
            else:
                inner = seg[1:-1] if closed else seg[1:]
                out.append(c + _blank(inner) + (c if closed else ""))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


class LineIndex:
    def __init__(self, text: str) -> None:
        self._starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self._starts, pos)


def template_arg(code: str, lt: int) -> tuple[str, int] | None:
    """Given the index of '<', return (argument text, index just past the matching '>')."""
    depth = 0
    for j in range(lt, min(len(code), lt + 400)):
        ch = code[j]
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                return code[lt + 1 : j], j + 1
        elif ch in ";{}":
            return None
    return None


def balanced(code: str, open_pos: int, pair: str = "()") -> tuple[str, int] | None:
    """Given the index of an opening bracket, return (inner text, index past the closer)."""
    opener, closer = pair
    depth = 0
    for j in range(open_pos, min(len(code), open_pos + MAX_BRACKET_SCAN)):
        ch = code[j]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return code[open_pos + 1 : j], j + 1
    return None


def split_top_level(args: str) -> list[str]:
    parts: list[str] = []
    depth, cur = 0, []
    for ch in args:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return [p.strip() for p in parts]


def norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s*([<>,():{}\[\]&*])\s*", r"\1", s)


def skip_space(code: str, k: int) -> int:
    while k < len(code) and code[k].isspace():
        k += 1
    return k


def body_span(code: str, pos: int) -> tuple[int, int] | None:
    """From a function name at pos, return (open, close) of its body; None for a declaration."""
    paren = code.find("(", pos)
    if paren == -1:
        return None
    args = balanced(code, paren)
    if args is None:
        return None
    k = args[1]
    while k < len(code) and code[k] not in "{;":
        k += 1
    if k >= len(code) or code[k] == ";":
        return None
    block = balanced(code, k, "{}")
    return (k, block[1] - 1) if block else None


FUNC_NAME_RE = re.compile(r"(?<![\w.>])(~?[A-Za-z_]\w*)\s*\(")
NOT_FUNCTIONS = {
    "if", "for", "while", "switch", "catch", "return", "sizeof", "decltype", "alignof",
    "alignas", "static_assert", "noexcept", "throw", "new", "delete", "defined",
}


def function_bodies(code: str) -> list[dict]:
    """Outermost function definitions in order: name, whether constructor/destructor, body span."""
    classes = set(re.findall(r"\b(?:class|struct)\s+(\w+)", code))
    found: list[dict] = []
    last_end = -1
    for m in FUNC_NAME_RE.finditer(code):
        if m.start() < last_end:
            continue
        name = m.group(1)
        if name in NOT_FUNCTIONS:
            continue
        span = body_span(code, m.start())
        if not span:
            continue
        found.append({"name": name, "ctor": name in classes or name.startswith("~"), "span": span})
        last_end = span[1]
    return found


# -------------------------------------------------------------------------- patterns

# (kind, label, regex). If the regex has a capture group, its text is appended to the label.
PATTERNS = [
    ("module", "DEFINE_ART_MODULE", r"\bDEFINE_ART_MODULE\s*\(\s*([\w:]+)"),
    ("module", "art base class", r"\bpublic\s+art::(\w+)"),
    ("event-read", "getByLabel (legacy)", r"\bgetByLabel\s*\("),
    ("event-read", "getByToken", r"\bgetByToken\s*\("),
    ("event-read", "getMany / getManyByType", r"\bgetMany(?:ByType)?\s*[<(]"),
    ("event-read", "getValidHandle", r"\bgetValidHandle\s*<"),
    ("event-read", "getHandle", r"\bgetHandle\s*<"),
    ("event-read", "getProduct", r"\bgetProduct\s*[<(]"),
    ("event-read", "art::Handle / ValidHandle", r"\bart::(?:Valid)?Handle\s*<"),
    ("event-read", "consumes / mayConsume", r"\b(?:consumes|mayConsume|consumesMany)\s*<"),
    ("event-read", "event metadata", r"\.\s*(?:isRealData|time)\s*\(\s*\)|\bid\s*\(\s*\)\s*\.\s*(?:event|run|subRun)\s*\("),
    ("event-write", "put", r"(?:\.|->)\s*put\s*\("),
    ("event-write", "put_into (collection helper)", r"\bput_into\s*\("),
    ("event-write", "produces", r"\bproduces\s*<"),
    ("event-write", "helper declares products", r"(?:::|\.|->)\s*(?:declare_products|produces_using)\b"),
    ("ptr-assns", "art::Ptr", r"\bart::Ptr\s*<"),
    ("ptr-assns", "art::PtrVector", r"\bart::PtrVector\s*<"),
    ("ptr-assns", "art::PtrMaker", r"\bart::PtrMaker\s*<"),
    ("ptr-assns", "art::Assns", r"\bart::Assns\s*<"),
    ("ptr-assns", "fill_ptr_vector", r"\bfill_ptr_vector\s*\("),
    ("ptr-assns", "FindManyP", r"\bFindManyP\s*<"),
    ("ptr-assns", "FindMany", r"\bFindMany\s*<"),
    ("ptr-assns", "FindOneP", r"\bFindOneP\s*<"),
    ("ptr-assns", "FindOne", r"\bFindOne\s*<"),
    ("ptr-assns", "util::CreateAssn", r"\butil::CreateAssn\w*\s*\("),
    ("service", "ServiceHandle", r"\bServiceHandle\s*<\s*([\w:]+)"),
    ("service", "lar::providerFrom", r"\bproviderFrom\s*<\s*([\w:]+)"),
    ("service", "detinfo DataFor", r"\bDataFor\s*\("),
    ("output-file", "TFileService", r"\bTFileService\b"),
    ("output-file", "ROOT histogram/tree pointer", r"\b(TH[123][DFIS]?|TProfile2?D?|TTree|TGraph\w*|TNtuple)\s*\*"),
    ("rng", "random numbers", r"\b(HepRandomEngine|createEngine|NuRandomService|RandomNumberGenerator|gRandom)\b"),
    ("tool", "art::make_tool", r"\bmake_tool\s*<\s*([\w:]+)"),
    ("config", "fhicl::ParameterSet", r"\bfhicl::ParameterSet\b"),
    ("config", "ParameterSet get", r"(?:\.|->)\s*get(?:_if_present)?\s*<"),
    ("config", "validated FHiCL", r"\bfhicl::(Atom|OptionalAtom|Sequence|OptionalSequence|Table|OptionalTable|TupleAs|DelegatedParameter|OptionalDelegatedParameter)\b"),
    ("logging", "MessageLogger", r"\bmf::Log\w+|\bMF_LOG_\w+|\bLOG_(?:DEBUG|INFO|WARNING|ERROR|VERBATIM)\b"),
    ("exception", "art::Exception", r"\bart::Exception\b"),
    ("exception", "cet::exception", r"\bcet::exception\b"),
    ("thread-safety", "ROOT fit / global state", r"(?:\.|->)\s*Fit\s*\(|\b(?:gMinuit|TMinuit|TVirtualFitter|gROOT|gDirectory)\b"),
    ("thread-safety", "mutable static", r"^[ \t]*static[ \t]+(?![^;={(]*\bconst(?:expr)?\b)[^(;]*[;={]"),
]
PATTERNS = [(k, lbl, re.compile(rx, re.M)) for k, lbl, rx in PATTERNS]

CALLBACK_RE = re.compile(
    r"\b(?P<name>produce|analyze|filter|beginRun|endRun|beginSubRun|endSubRun|beginJob|endJob"
    r"|respondToOpenInputFile|respondToCloseInputFile)\s*"
    r"(?=\(\s*(?:art::(?:Event|Run|SubRun|FileBlock|ProcessingFrame)\b|\)))"
)
MAIN_CALLBACKS = ("produce", "analyze", "filter")

_MEMBER = r"(?P<member>f[A-Z]\w*|m_\w+|[A-Za-z]\w+_)"
MEMBER_MUTATION_RES = [
    re.compile(
        rf"(?<![\w.>:]){_MEMBER}\s*(?:\[[^\]]*\]\s*)*"
        r"(?:\+\+|--|[-+*/%|&^]?=(?!=)|(?:\.|->)\s*(?:push_back|emplace_back|insert|clear|reset|resize|Fill)\s*\()"
    ),
    re.compile(rf"(?:\+\+|--)\s*{_MEMBER}\b"),
]

# [ \t] rather than \s: under re.M a leading \s* would run across preceding blank lines and
# report the include on the wrong line.
INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*[<"]([^>"]+)[>"]', re.M)


def classify_include(path: str) -> str | None:
    if path.startswith(("art/", "art_root_io/")):
        return "art"
    if path.startswith("canvas/"):
        return "canvas"
    if path.startswith("fhiclcpp/"):
        return "fhicl"
    if path.startswith("messagefacility/"):
        return "messagefacility"
    if path.startswith(("cetlib/", "cetlib_except/")):
        return "cetlib"
    if path.startswith("phlex/"):
        return "phlex"
    if path.startswith("nurandom/"):
        return "service"
    if re.search(r"(^|/)\w*Services?(/|\.h$)|_service\.h$|DetectorInfoServices/|ServiceUtil\.h$", path):
        return "service"
    if re.fullmatch(r"larcore/Geometry/(Geometry|WireReadout|AuxDetGeometry)\.h", path):
        return "service"
    return None


# -------------------------------------------------------------------------- analysis


def analyze(text: str) -> dict:
    code = strip_cpp(text, keep_strings=False)
    code_s = strip_cpp(text, keep_strings=True)
    lines = LineIndex(code)

    found: dict[tuple[str, str], list[int]] = {}
    for kind, label, rx in PATTERNS:
        for m in rx.finditer(code):
            name = label + (f"<{m.group(1)}>" if rx.groups and m.group(1) else "")
            found.setdefault((kind, name), []).append(lines.line(m.start()))

    callbacks = []
    for m in CALLBACK_RE.finditer(code):
        span = body_span(code, m.start())
        if span:
            first, last = lines.line(span[0]), lines.line(span[1])
            callbacks.append({"name": m.group("name"), "first": first, "last": last, "lines": last - first + 1})
    callback_names = {c["name"] for c in callbacks}

    # Members written anywhere except constructors and destructors: per-event scratch kept in
    # members, or real cross-event state. Both matter for extraction.
    member_state = []
    for fn in function_bodies(code):
        if fn["ctor"]:
            continue
        lo, hi = fn["span"]
        seg = code[lo:hi]
        for rx in MEMBER_MUTATION_RES:
            for m in rx.finditer(seg):
                member_state.append(
                    {
                        "function": fn["name"],
                        "callback": fn["name"] in callback_names,
                        "member": m.group("member"),
                        "line": lines.line(lo + m.start()),
                    }
                )
    # One row per member and line: several statements on one line, or both patterns matching
    # the same statement, would otherwise list it more than once.
    seen = set()
    member_state = [
        d for d in sorted(member_state, key=lambda d: d["line"])
        if (d["member"], d["line"]) not in seen and not seen.add((d["member"], d["line"]))
    ]

    includes = []
    for m in INCLUDE_RE.finditer(code_s):
        cls = classify_include(m.group(1))
        if cls:
            includes.append({"include": m.group(1), "class": cls, "line": lines.line(m.start())})

    base = re.search(r"\bpublic\s+art::(\w+)", code)
    services = sorted({n.split("<", 1)[1].rstrip(">") for (k, n) in found if k == "service" and "<" in n})
    loc = sum(1 for ln in code.splitlines() if ln.strip())
    return {
        "loc": loc,
        "base": base.group(1) if base else "",
        "callbacks": callbacks,
        "services": services,
        "produces_assns": len(re.findall(r"\bproduces\s*<\s*art::Assns", code)),
        "framework_includes": includes,
        "local_includes": INCLUDE_RE.findall(code_s),
        "constructs": [{"kind": k, "construct": n, "count": len(v), "lines": v} for (k, n), v in found.items()],
        "member_state": member_state,
    }


def contract(text: str) -> Counter:
    code = strip_cpp(text, keep_strings=True)
    items: Counter = Counter()

    m = re.search(r"\bDEFINE_ART_MODULE\s*\(\s*([\w:]+)", code)
    if m:
        items[f"module {m.group(1)}"] += 1
    for m in re.finditer(r"\bpublic\s+art::(\w+)", code):
        items[f"base art::{m.group(1)}"] += 1

    for m in re.finditer(r"\b(produces|consumes|mayConsume|consumesMany)\s*<", code):
        t = template_arg(code, m.end() - 1)
        if not t:
            continue
        k = skip_space(code, t[1])
        args = balanced(code, k) if code[k : k + 1] == "(" else None
        items[f"{m.group(1)} <{norm(t[0])}>({norm(args[0]) if args else ''})"] += 1

    # Collection helpers that declare products on the module's behalf, e.g.
    # recob::HitCollectionCreator::declare_products(producesCollector(), "", true, false)
    for m in re.finditer(r"(?:\b([\w:]+)::|(?:\.|->)\s*)(declare_products|produces_using)\b", code):
        k = skip_space(code, m.end())
        targ = ""
        if code[k : k + 1] == "<":
            t = template_arg(code, k)
            if t:
                targ, k = f"<{norm(t[0])}>", skip_space(code, t[1])
        args = balanced(code, k) if code[k : k + 1] == "(" else None
        owner = m.group(1) or "<member>"
        items[f"{m.group(2)} {owner}{targ}({norm(args[0]) if args else ''})"] += 1

    for m in re.finditer(r"(?:\.|->)\s*(get|get_if_present)\s*<", code):
        t = template_arg(code, m.end() - 1)
        if not t:
            continue
        k = skip_space(code, t[1])
        args = balanced(code, k) if code[k : k + 1] == "(" else None
        if not args:
            continue
        parts = split_top_level(args[0])
        if not parts or not re.fullmatch(r'"[^"]*"', parts[0]):
            continue
        extra = f" default={norm(', '.join(parts[1:]))}" if m.group(1) == "get" and len(parts) > 1 else ""
        items[f"param {m.group(1)}<{norm(t[0])}> {parts[0]}{extra}"] += 1

    validated = re.compile(
        r"\b(?:fhicl::)?(Atom|OptionalAtom|Sequence|OptionalSequence|Table|OptionalTable|TupleAs"
        r"|DelegatedParameter|OptionalDelegatedParameter)\s*<"
    )
    for m in validated.finditer(code):
        t = template_arg(code, m.end() - 1)
        if not t:
            continue
        mm = re.match(r"\s*\w+\s*([{(])", code[t[1] : t[1] + 80])
        if not mm:
            continue
        open_pos = t[1] + mm.start(1)
        blk = balanced(code, open_pos, "{}" if mm.group(1) == "{" else "()")
        if not blk:
            continue
        parts = split_top_level(blk[0])
        name = None
        for p in parts:
            if re.match(r"(?:fhicl::)?Name\b", p):
                q = re.search(r'"[^"]*"', p)
                name = q.group(0) if q else None
        if not name:
            continue
        defaults = [p for p in parts if not re.match(r"(?:fhicl::)?(Name|Comment|use_if|use_unless)\b", p)]
        suffix = f" default={norm(', '.join(defaults))}" if defaults else ""
        items[f"param {m.group(1)}<{norm(t[0])}> {name}{suffix}"] += 1

    for m in re.finditer(r"\bmake_tool\s*<", code):
        t = template_arg(code, m.end() - 1)
        if t:
            items[f"tool <{norm(t[0])}>"] += 1

    stripped = strip_cpp(text, keep_strings=False)
    for m in CALLBACK_RE.finditer(stripped):
        if body_span(stripped, m.start()):
            items[f"callback {m.group('name')}"] += 1
    return items


def render_contract(items: Counter) -> list[str]:
    return [item if count == 1 else f"{item}  [x{count}]" for item, count in sorted(items.items())]


# -------------------------------------------------------------------------- commands


def cmd_report(args: argparse.Namespace) -> int:
    results = {spec: analyze(read_source(spec, args.repo)) for spec in args.files}
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for spec, r in results.items():
        print(f"## {spec}  ({r['loc']} non-blank code lines)")
        if r["base"]:
            print(f"base class: art::{r['base']}")
        if r["callbacks"]:
            cbs = ", ".join(f"{c['name']} L{c['first']}-L{c['last']} ({c['lines']} lines)" for c in r["callbacks"])
            print(f"callbacks: {cbs}")
        if r["services"]:
            print(f"services: {', '.join(r['services'])}")
        if r["framework_includes"]:
            print("framework includes:")
            for inc in r["framework_includes"]:
                print(f"  L{inc['line']:<5} [{inc['class']}] {inc['include']}")
        if r["constructs"]:
            print("\n| kind | construct | count | lines |\n|---|---|---|---|")
            for c in sorted(r["constructs"], key=lambda c: (c["kind"], c["construct"])):
                shown = ", ".join(map(str, c["lines"][:12])) + (" ..." if len(c["lines"]) > 12 else "")
                print(f"| {c['kind']} | `{c['construct']}` | {c['count']} | {shown} |")
        if r["member_state"]:
            print("\nmember state written outside constructors (per-event scratch or cross-event state):")
            for s in r["member_state"]:
                where = f"{s['function']}" + (" [callback]" if s["callback"] else "")
                print(f"  L{s['line']:<5} {s['member']} in {where}")
        print()
    return 0


def cmd_contract(args: argparse.Namespace) -> int:
    total: Counter = Counter()
    for spec in args.files:
        total.update(contract(read_source(spec, args.repo)))
    print("\n".join(render_contract(total)))
    return 0


def cmd_contract_diff(args: argparse.Namespace) -> int:
    before: Counter = Counter()
    after: Counter = Counter()
    for spec in args.before:
        before.update(contract(read_source(spec, args.repo)))
    for spec in args.after:
        after.update(contract(read_source(spec, args.repo)))
    diff = list(difflib.unified_diff(render_contract(before), render_contract(after), "before", "after", lineterm=""))
    if diff:
        print("\n".join(diff))
        return 1
    print(f"contract unchanged ({sum(before.values())} items)")
    return 0


def first_pass_score(r: dict, path: str) -> tuple[int, list[str]]:
    score, notes = 0, []
    segments = path.split("/")
    package = segments[0] + "/" if len(segments) > 1 else ""

    if "art" in segments[:-1]:
        score -= 3
        notes.append("in an art/ subdirectory: package already separates framework code")
    base = r["base"]
    if base in ("EDProducer", "EDFilter"):
        score += 2
    elif base == "EDAnalyzer":
        score += 1
    elif base:
        notes.append(base)
    if 120 <= r["loc"] <= 600:
        score += 2
    elif r["loc"] > 1000:
        score -= 2
        notes.append("very large")
    elif r["loc"] < 80:
        score -= 1
        notes.append("small")
    main = max((c["lines"] for c in r["callbacks"] if c["name"] in MAIN_CALLBACKS), default=0)
    if main >= 40:
        score += 2
    elif main < 15:
        score -= 1
        notes.append("thin callback: logic may already live elsewhere")
    delegated = [
        inc for inc in r["local_includes"]
        if package and inc.startswith(package) and re.search(r"(Alg|Algorithm|Utils?)\w*\.h(pp)?$", inc)
    ]
    if delegated:
        score -= 1
        notes.append("includes own-package algorithm header(s): " + ", ".join(os.path.basename(d) for d in delegated))
    nsvc = len(r["services"])
    if 1 <= nsvc <= 3:
        score += 1
    elif nsvc > 4:
        score -= 1
        notes.append("many services")
    counts = {c["construct"]: c["count"] for c in r["constructs"]}
    tools = sum(v for k, v in counts.items() if k.startswith("art::make_tool"))
    if tools:
        score -= min(tools, 2)
        notes.append(f"{tools} tool(s)")
    if r["produces_assns"] == 0:
        score += 1
    elif r["produces_assns"] > 2:
        score -= 1
        notes.append("several Assns outputs")
    extra = [c["name"] for c in r["callbacks"] if c["name"] not in MAIN_CALLBACKS + ("beginJob", "endJob")]
    if extra:
        score -= 1
        notes.append("run/subrun callbacks (fold shape)")
    if counts.get("getByLabel (legacy)") or counts.get("art::Ptr"):
        score += 1
        notes.append("separation work (getByLabel/art::Ptr)")
    if any(s["member"] and not s["callback"] for s in r["member_state"]):
        notes.append("members written in helper functions")
    if any(c["kind"] == "rng" for c in r["constructs"]):
        notes.append("random numbers")
    return score, notes


def _module_paths(args: argparse.Namespace) -> list[tuple[str, str]]:
    """Return (display path used for scoring, source spec) for every *_module.cc to scan."""
    out = []
    if args.rev:
        check_rev(args.rev)
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "--end-of-options", args.rev, "--", *args.paths],
            cwd=args.repo or None, capture_output=True, text=True,
        )
        if listing.returncode != 0:
            sys.exit(f"git ls-tree {args.rev} failed: {listing.stderr.strip()}")
        for path in listing.stdout.splitlines():
            dirs = path.split("/")[:-1]
            if path.endswith("_module.cc") and not any(d.startswith(".") or d.lower() in SKIP_DIRS for d in dirs):
                out.append((path, f"git:{args.rev}:{path}"))
        return sorted(out)
    for top in args.paths:
        parent = os.path.dirname(os.path.abspath(top))
        for root, subdirs, files in os.walk(top):
            subdirs[:] = sorted(s for s in subdirs if not s.startswith(".") and s.lower() not in SKIP_DIRS)
            for fname in sorted(files):
                if fname.endswith("_module.cc"):
                    path = os.path.join(root, fname)
                    out.append((os.path.relpath(path, parent), path))
    return out


def cmd_scan(args: argparse.Namespace) -> int:
    rows = []
    for display, spec in _module_paths(args):
        r = analyze(read_source(spec, args.repo))
        score, notes = first_pass_score(r, display)
        main = max((c["lines"] for c in r["callbacks"] if c["name"] in MAIN_CALLBACKS), default=0)
        counts: Counter = Counter()
        for c in r["constructs"]:
            counts[c["construct"]] += c["count"]
        rows.append(
            {
                "score": score,
                "module": display,
                "base": r["base"],
                "loc": r["loc"],
                "main_cb_lines": main,
                "services": len(r["services"]),
                "assns_out": r["produces_assns"],
                "getByLabel": counts["getByLabel (legacy)"],
                "art_ptr": counts["art::Ptr"],
                "notes": "; ".join(notes),
            }
        )
    rows.sort(key=lambda d: (-d["score"], d["module"]))
    if args.json:
        print(json.dumps(rows[: args.top], indent=2))
        return 0
    source = f" at {args.rev}" if args.rev else " (working tree)"
    print("| score | module | base | loc | main cb | svc | assns out | getByLabel | art::Ptr | notes |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for d in rows[: args.top]:
        print(
            f"| {d['score']} | {d['module']} | {d['base']} | {d['loc']} | {d['main_cb_lines']} | {d['services']} "
            f"| {d['assns_out']} | {d['getByLabel']} | {d['art_ptr']} | {d['notes']} |"
        )
    print(f"\n{len(rows)} modules scanned{source}; showing top {min(args.top, len(rows))}. Scores are heuristic.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="git repository for git:REV:PATH arguments and scan --rev (default: cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("report", help="framework constructs per file")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("contract", help="framework-visible contract of the files, merged")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_contract)

    p = sub.add_parser("contract-diff", help="diff two contracts; exit 1 when they differ")
    p.add_argument("--before", nargs="+", required=True)
    p.add_argument("--after", nargs="+", required=True)
    p.set_defaults(func=cmd_contract_diff)

    p = sub.add_parser("scan", help="rank *_module.cc files as first-pass candidates")
    p.add_argument("paths", nargs="+", help="directories, or pathspecs inside --repo when --rev is given")
    p.add_argument("--rev", help="read files from this git revision of --repo instead of the working tree")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
