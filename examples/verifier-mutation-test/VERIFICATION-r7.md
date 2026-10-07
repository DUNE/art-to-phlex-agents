# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 0 major, 6 minor, 1 nit |
| Working tree and base | `<worktree-r7>` (branch `phlex-extract/DisambigFromSpacePoints-r7`, uncommitted) against `5d619357` |
| Notes reviewed | `runs/dunereco-DisambigFromSpacePoints-r7/MIGRATION_NOTES.md`, `contract.before.txt`, `contract.after.txt`, `extraction.patch` |
| Verifier / model / date | phlex-verifier (Claude Code subagent), Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The extraction moves `runOnSpacePoints`, `resolveUnassigned`, `assignFirstAllowedWire`,
  `assignEveryAllowedWire` and the space point to TPC map into
  `DisambigFromSpacePointsAlg.{h,cxx}` as free functions. The algorithm code is a faithful
  mechanical move: every statement checked, the `unordered_map` threading, `reserve` and
  insertion sequence are kept, and the monitoring counters keep their original write paths,
  including the indeterminate `fNMissedByNeighbors` when `UseNeighbors: false`.
- Framework purity is clean (9 logging lines, all marked and all in the notes table). The
  framework contract is unchanged (13 items).
- **Blocker:** the module's first output loop now adds hit-space point association pairs in
  **reverse** order (module L204). The original and the second loop iterate forward. This
  changes the `art::Assns<recob::Hit, recob::SpacePoint>` product for every resolved hit with
  more than one space point. It is not documented; the notes claim the original order.
- `extraction.patch` matches `git diff 5d619357` of the worktree exactly, so the reversal is in
  the delivered patch, not a later edit.
- Before a build: restore the forward loop, correct the notes (paths, test-file references,
  repository home), and make the validation plan compare association pairs in produced order.

## Original module in brief

Written before reading the new code or the notes. `DisambigFromSpacePoints` is an
`EDProducer` that copies the input `recob::Hit` collection onto disambiguated wire segments.
Collection hits keep the first wire of their channel. Induction hits vote, per TPC, for the
wire segment within one wire pitch of their associated space points (whose TPC comes from the
space point's collection hit). Unresolved induction hits are optionally placed by a
distance-weighted score of the N nearest resolved hits on each candidate segment, then the
rest are put on every allowed segment ("repeat"), the first allowed one ("first"), or dropped.
Output order follows iteration of two `std::unordered_map`s. Contract: FHiCL table of 8
parameters, `HitCollectionCreator::declare_products(..., "", true, false)` (hits plus hit-wire
assns), `produces<Assns<Hit, SpacePoint>>`, both put on every event; an optional
`hitstats` TTree via `TFileService`; `cet::exception` in the constructor when
`NumNeighbors < 1`.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (`.cxx` L17, 50, 146, 177, 242, 255, 336, 342, 348; all MessageLogger) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | contract unchanged (13 items); `contract.before.txt` and `contract.after.txt` identical |
| Algorithm inventory | `art_inventory.py report <alg .h .cxx>` | only `messagefacility/MessageLogger/MessageLogger.h` and 8 `mf::Log*` calls (all marked) |
| Module inventory | `art_inventory.py report DisambigFromSpacePoints_module.cc` | all art constructs now in the module: services, FindManyP/FindOneP, PtrMaker, Assns, TFileService, `cet::exception`; member writes only `fRun`, `fEvent`, the three counter arrays, `fTree->Fill` |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'` | 9 markers added, all in the `.cxx`; each matches a row of notes section 6 and the reason (logging) holds; no table row without a marker |
| Patch vs worktree | `diff extraction.patch <(git diff 5d619357)` ignoring `index` lines | identical |
| DUNE includes in algorithm | `grep '#include "dune' <alg files>` | only its own header |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | **blocker** | `DisambigFromSpacePoints_module.cc:203-207` | Hit-space point association pairs for `hitToWire` hits are added in reverse order. Changes the `Assns<recob::Hit, recob::SpacePoint>` data product (pair order) for every resolved hit with 2 or more space points, which is most hits from `SpacePointSolver`. Undocumented: notes section 3 says "adds `(hitPtrMaker(hcol.size()-1), spPtr)` for each `spPtr` in `spFromHit.at(key)`" and section 4 lists no such deviation. | Original L246-L250: `for (auto const & spPtr : sps) { assns->addSingle(hitPtr, spPtr); }`. New L204: `for (auto it = sps.rbegin(); it != sps.rend(); ++it)`. The `hitToNWires` loop (new L220-L224) is still forward, so the two loops now disagree. Present in `extraction.patch` L649. | Restore `for (auto const & spPtr : sps) { assns->addSingle(hitPtr, spPtr); }`. |
| 2 | minor | `DisambigFromSpacePoints_module.cc:178` | Every hit-to-space point `Ptr` is dereferenced before the algorithm runs; the original dereferenced only those whose key is in `spToTPC` and with a candidate wire in that TPC (original L328). Only differs when an associated space point's product is unavailable. Documented in notes section 4 and justified. | notes section 4, "Intentional deviations" | Accept, or resolve lazily if the human prefers. |
| 3 | minor | `MIGRATION_NOTES.md` section 7 | Binding plan names no Phlex-era repository. The module runs in FD (`dunefd_disambigfromsp`) and ProtoDUNE-HD (`pdune_disambigfromsp`) jobs per section 8, so per `dune-repo-map.md` the candidates are `dune-fd-reco` (shared) versus a protoDUNE repository; the deciding question is which detectors' production FHiCL run it. | `dune-repo-map.md` L38 | Add the home, or the candidates and the deciding question. |
| 4 | minor | `MIGRATION_NOTES.md:7` | Working tree and branch given as `...-DisambigFromSpacePoints-v1`, branch `phlex-extract/DisambigFromSpacePoints-v1`; the verified tree is `-r7`, branch `phlex-extract/DisambigFromSpacePoints-r7`. | `git branch --show-current` | Correct the header. |
| 5 | minor | `MIGRATION_NOTES.md:172` | Issue 10 cites `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`; neither exists in the worktree or the notes directory. | `ls dunereco/HitFinderDUNE`, `ls runs/.../` | Remove the reference or add the files. |
| 6 | minor | `MIGRATION_NOTES.md` section 8 | Validation plan compares association "key pairs" but does not say to compare them in produced order. A sorted or set comparison would miss finding 1. (The suggested `EventDump` plus text diff would catch it if it prints pair order.) | section 8 | State that `Assns<Hit,Wire>` and `Assns<Hit,SpacePoint>` pairs are compared in produced order, unsorted. |
| 7 | minor | `dunereco/HitFinderDUNE/CMakeLists.txt:2-25` | The algorithm `.cxx` is globbed into `HitFinderDUNE`, whose `LIB_LIBRARIES` already link art, canvas-adjacent art libraries, `fhiclcpp`, MessageLogger and art service libraries. Nothing was added, but a future Phlex plugin linking this library inherits art. The binding plan does not mention it. | CMakeLists L18-L23 | Note in the binding plan that the algorithm needs its own library (larcorealg, lardataalg, lardataobj only, plus MessageLogger while transitional) before binding. |
| 8 | nit | `MIGRATION_NOTES.md:43` | Line references off by one: `eventHits = *hitsHandle` is module L162, not L161. | module L162 | Fix the reference. |

No instructions addressed to an agent were found in the source, comments or notes.

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L46-L49 typedefs | `Alg.h` L29-L32 | identical | same namespace `dune`; no other definitions in the repo |
| L122-L137 ctor init, `NumNeighbors` check | module L102-L113, `make_cfg` L91-L100 | mechanical edit OK | each field maps to its own FHiCL atom; no same-type mix-up (`numNeighbors` size_t, `excludeTPCs` vector<size_t>, `maxDistance` float) |
| L142-L158 product declarations, TTree branches | module L118-L134 | identical | branch buffers still the class members |
| L163-L192 event reads, `FindOneP`, `hcol`, `assns`, `FindManyP`, `DataFor` | module L139-L167 | mechanical edit OK | `fill_ptr_vector` replaced by `*hitsHandle`; key equals index |
| L193-L212 space point to TPC map | `Alg.cxx` L288-L312 | mechanical edit OK | loop bound `hitsFromSp.size()` equals `spHandle->size()` (module L170) |
| L214-L219 locals, `reserve` | `Alg.cxx` L327-L332 | identical | `hitToWire` is `res.hitToWire`, reserved before first insert |
| L221-L232 pass sequence and `LogInfo`s | `Alg.cxx` L334-L348 | identical | message order relative to helper warnings unchanged |
| L236-L251 `hitToWire` output loop | module L193-L208 | **CHANGED** | hit order identical; SP association order reversed (finding 1) |
| L253-L269 `hitToNWires` output loop | module L210-L226 | mechanical edit OK | `spFromHit.at(eventHits[key].key())` to `spFromHit.at(key)` |
| L271-L275 tree fill, puts | module L228-L232 | identical | |
| L278-L363 `runOnSpacePoints` | `Alg.cxx` L30-L118 | mechanical edit OK | `hit.key()` to `i`; `fN*` to `stats.*` (std::array, same `int`, same unchecked `[]`) |
| L365-L467 `resolveUnassigned` | `Alg.cxx` L120-L227 | mechanical edit OK | float/size_t conversions, `<` vs `<=`, buffer logic, `result` map, erase and insert all identical |
| L469-L493 `assignFirstAllowedWire` | `Alg.cxx` L229-L257 | mechanical edit OK | |
| L495-L516 `assignEveryAllowedWire` | `Alg.cxx` L259-L282 | mechanical edit OK | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-L174 | resolves `hitsFromSp` into `Hit const*` lists | none: original dereferenced every hit of every SP in the same order (first loop up to the collection hit, second loop all, or first loop all when none); same first failing `Ptr` |
| module L175-L179 | resolves `spFromHit` into `{key, SpacePoint const*}` | values identical (key is `Ptr::key()`); eager dereference on an unavailable product only (finding 2) |
| module L181 | `DisambigResult` returned by value (prvalue into `result`; NRVO or move inside) | `unordered_map` move or elision keeps node order; output hit order unchanged |
| module L184-L189 | copies stats into branch members; `fNMissedByNeighbors` only when `useNeighbors` | preserves original write sites, including the indeterminate value when `UseNeighbors: false` (notes issue 1); `fNHits`/`fNMissedBySpacePoints` written every event as before |
| `Alg.cxx` L322 `DisambigResult res{}` | value-initialises stats | not observable: module copies only fields the original wrote on that path |

Other items checked: no random draws; no exceptions moved (constructor `cet::exception` unchanged);
`detProp` fetched once per event before any `Ptr` dereference, as before; no event pointers
kept beyond `produce` (`SpacePointRef`, `Hit const*` are locals); no state changed lifetime.

## Validation plan

Configurations are good: FD `hitfd` and ProtoDUNE-HD `hitpdune` (both "repeat"), plus
"first", drop, `UseNeighbors: false`, non-empty `ExcludeTPCs`, `MonitoringPlots: true`. Hit
output compared unsorted, which is right. The plan would catch finding 1 only if the
association comparison keeps produced pair order; it should say so explicitly (finding 6).
The `hitstats` exclusion of `fNMissedByNeighbors` when `UseNeighbors: false` is correct.

## Compile-risk review

- Identifiers: every former member resolves (`cfg.*`, `wireReadout`, `stats.*`); typedefs
  visible via header; anonymous-namespace helpers precede their use in `disambiguateHits`.
- Includes: header has `WireReadoutGeom.h`, `geo_types.h`, `DetectorPropertiesData.h`,
  `Hit.h`, `SpacePoint.h` and std headers; `.cxx` adds `PlaneGeo.h`, `<algorithm>`,
  `<cmath>`; MessageLogger is only in the `.cxx`, marked.
- Declarations match definitions (parameter names differ only, which is fine). `make_cfg` is
  static, declared after `Config`; member initialiser order matches declaration order.
- APIs read in `<LArSoft checkout>` (larcorealg and lardataalg at
  `LARSOFT_SUITE_v10_20_00`, lardata `v10_20_00-1`): `HitCreator(recob::Hit const&,
  geo::WireID const&)` (HitCreator.h L321), `WireReadoutGeom::ChannelToWire`
  (L574), `Plane(PlaneID const&)` (L151; braced `{0,0,plane}` selects it, as in the
  original), `PlaneGeo::WireCoordinate(Point_t)`, `WirePitch()`,
  `GetXTicksCoefficient(int,int)` (L89). The base `v10_26_00d02` builds against a newer
  LArSoft than the checkout; these calls are unchanged from the original code, so risk is low.
- Unverified assumption (not central): canvas `art::Ptr::operator*` throws on an unavailable
  product the same way as `operator->`. Canvas sources were not available locally.
- Build: `art_make` globs the new `.cxx` into `HitFinderDUNE`; needs a fresh CMake configure.
  `LIB_LIBRARIES` already cover larcorealg, lardataalg, lardataobj, MessageLogger; the plugin
  links `HitFinderDUNE`. No C++20/23-removed constructs; nothing beyond C++17 used.
- Needs build to confirm: nothing specific; overall compile likelihood high.

## Guide conformance

- Separation checks: `ServiceHandle` only in module (L123, L127, L167); geometry and
  detector properties passed explicitly; no helper receives the event or a handle; nothing
  event-scoped cached across events. Pass.
- Extraction checklist 1 to 5: core describable without callbacks (yes); all inputs in the
  signature (yes); outputs returned (`DisambigResult`, yes); configuration collected outside
  (`make_cfg`, yes); transitional items documented (9 logging lines, yes).
- Binding plan: transform plus `observe` (serial, TTree as serialized resource) is plausible
  and consistent with no purity warnings; inputs const; association blockers named;
  `HitCreator` dependency named. Missing: Phlex-era repository home (finding 3) and the
  library split (finding 7).

## Notes accuracy

- Section 3 "Outputs" claims SP associations are added for each `spPtr` in order; the code
  reverses them in the first loop (part of finding 1).
- Header working tree/branch name `-v1` is stale (finding 4).
- Issue 10 references test files not present (finding 5).
- Off-by-one line reference (finding 8).
- All other claims (section 4 moves, mechanical edits, transitional table, contract, purity,
  CMake) match the code.
