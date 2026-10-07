# Phlex pass 1 (separation and extraction): `<Module>`

| | |
|---|---|
| Repository and base | `<repo>` @ `<sha>` (`<branch>`) |
| Module | `<path>` (art::`<EDProducer / EDFilter / EDAnalyzer>`) |
| Working tree | `<worktree path>`, branch `<branch>` |
| Guide | phlex-examples `migration/doc` @ 5df307b (v0.1.alpha, 2026-09-09) |
| Phlex target | v0.4.1 (phlex-examples `phlex-v0.4`) |
| Phlex-era home | `<DUNE/dune-... repository, two candidates and the deciding question, or "LArSoft (upstream)">` |
| Kit | art-to-phlex-agents @ `<git -C $KIT describe --always --dirty>` |
| Model | `<extractor model>` |
| Agent / model | `<agent>`, `<model>` |
| Build status | NOT COMPILED / compiled in `<environment>` / regression-tested (`<how>`) |

## 1. What the module computes

Two to five sentences with no framework vocabulary: inputs, the computation, outputs.

## 2. Framework inventory and classification

Output of `art_inventory.py report` on the original, one row per construct or group.

| # | Construct (original file:line) | Kind | Decision | Where it lives now |
|---|---|---|---|---|
| 1 | `evt.getByLabel(fWireLabel, wireHandle)` (L120) | event retrieval | convenience: `getValidHandle` | module L85 |

Kinds: event retrieval, product output, art::Ptr/Assns, service, tool, configuration,
logging, callback state, histogram/TTree, random engine, exception, event metadata.
Decisions: boundary, convenience, data, transitional.

## 3. Extracted algorithm API

```cpp
// signatures, configuration struct, result structs
```

- Inputs and where the module gets each one:
- Outputs and how the module publishes each one:
- Free function or class, and why:
- Re-entrancy: re-entrant yes/no, and what prevents it if no.

## 4. Behaviour preservation

- Code moved verbatim (original lines → new file:lines):
- Mechanical edits (member → cfg field, handle → vector reference, ...):
- Intentional deviations (should be none; justify each):
- Suspected pre-existing issues noticed and **not** fixed:

## 5. Framework-visible contract

Result of `art_inventory.py contract-diff` (before: base ref, after: working tree).
"Unchanged (N items)" or each differing line with an explanation.

## 6. Transitional items

Every `PHLEX-TRANSITIONAL` marker and every `WARN` from `check_purity.py`.

| file:line | What | Why it stays | How it goes away |
|---|---|---|---|

## 7. Phlex binding plan (not implemented)

Phlex-era home: `<repository>` (see `references/dune-repo-map.md`), and why: `<which
production jobs use the module, by detector>`.

Library: the algorithm must end up in a library that does not link art before a Phlex
plugin can use it. Say whether that is already true, or name the split needed in phase 2.

Dependencies that must move first (includes from DUNE art-era repositories):

| Header | Art-era repository | Likely Phlex-era home |
|---|---|---|

| Extracted piece | Node | Inputs (creator / layer / suffix [/ stage]) | Output suffix(es) | Layer | Concurrency | Resources | Gate (when) | Blockers |
|---|---|---|---|---|---|---|---|---|

## 8. Validation plan

How to show equivalence under art: the FHiCL job, input sample, products to compare, and
how to compare them (`scripts/art_compare.py wrap` and `diff`, which compare the persisted
products and TFileService trees entry by entry). Compare collections and
associations in produced order unless the order is known not to matter; a sorted comparison
hides an ordering change, which is a common extraction risk. The pass criterion is
bit-identical products and TFileService trees on a stated sample (file, event range). Cover
every FHiCL combination that reaches a path the extraction touched, including combinations
no shipped configuration uses (for example a non-default option together with a monitoring
switch); list them as `wrap --set` overrides. Diff the job log too, filtered to the module's
message category, because log text and order are part of the behaviour. A unit-test idea for the
algorithm on a hand-built input.

## 9. Checklists

Guide extraction checklist, with evidence:

1. Core algorithm describable without framework callbacks:
2. All real inputs in the signature or constructor:
3. All outputs as return values or explicit output objects:
4. Configuration collected outside the algorithm:
5. Remaining framework assumptions documented as transitional:

Separation checks:

- `ServiceHandle` only in the module:
- Every service-derived value passed explicitly:
- No helper receives the event or a handle:
- No event-scoped data cached across events:

Purity check summary (`check_purity.py`): `PASS/FAIL`, errors / warnings / transitional.
