# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 0 major, 7 minor, 3 nit |
| Working tree and base | `<worktree-r4>` against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r4/MIGRATION_NOTES.md` (+ `extraction.patch`, `contract.*.txt`) |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The change moves the four private helpers and the space point to TPC map into a new
  framework-free `DisambigFromSpacePointsAlg.{h,cxx}` (free functions, `DisambigResult`
  returned by value) and leaves the module as boundary code. Only these three files changed;
  `extraction.patch` matches `git diff 5d619357` in the working tree exactly.
- Purity is clean (0 errors, 0 warnings, 9 MessageLogger lines, all marked and all in the
  notes' transitional table). The framework contract is unchanged (13 items, identical).
- Behaviour is preserved statement for statement **except one undocumented numeric change**:
  the neighbour score in `resolveUnassigned` is now computed in `float` (`1.f/(1.f + d)`)
  instead of `double` (`1./(1. + d)`). `UseNeighbors: true` is the production default, so this
  runs in every production job and can flip the wire chosen for a hit when two candidate
  segments have nearly equal scores. This is a one-token revert.
- Output ordering is preserved: same `unordered_map` type, same `reserve`, same insertion
  sequence, moved (not copied) into `DisambigResult`, and the result object is a prvalue in
  the module (guaranteed elision).
- Monitoring tree values are preserved, including the original's never-written
  `fNMissedByNeighbors` when `UseNeighbors: false`.
- Before a build: revert the float literals, then fix the notes (worktree path, missing test
  file reference, Phlex-era home) and run the validation plan.

## Original module in brief

Written from `git show 5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`
before opening the new code or notes.

An `art::EDProducer` that reads a `std::vector<recob::Hit>` (`HitModuleLabel`) and a
`std::vector<recob::SpacePoint>` (`SpModuleLabel`) with their hit/space point associations,
and decides which wire segment each induction hit belongs to (the channel maps to several
wrapped wires). Collection hits take the first wire of their channel. Induction hits vote per
TPC using associated space points whose collection hit fixes the TPC, then (if `UseNeighbors`)
unresolved hits take the segment with the best inverse-distance score of the N nearest
resolved hits, then leftovers are duplicated ("repeat"), put on the first allowed wire
("first"), or dropped. It writes a new hit collection plus hit-wire associations through
`HitCollectionCreator` (declared via `declare_products(..., "", true, false)`) and copies the
hit-space point associations (`produces<Assns<Hit,SpacePoint>>`), both unconditionally. With
`MonitoringPlots` it fills a `hitstats` TTree from member counters. Output order follows
`std::unordered_map` iteration of `hitToWire` then `hitToNWires`. Pre-existing quirk:
`fNMissedByNeighbors` is never written when `UseNeighbors` is false.

## Automated checks

All run from the working tree with `S=$KIT/skills/art-phlex-extract/scripts`.

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings; 9 transitional (cxx L17, 50, 146, 177, 242, 255, 336, 342, 348), all MessageLogger |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:<module> --after <module>` | contract unchanged (13 items); `contract.before.txt` == `contract.after.txt` |
| Algorithm inventory | `art_inventory.py report <alg .h .cxx>` | only `messagefacility` include and 8 `mf::Log*` calls; nothing else |
| Module inventory | `art_inventory.py report <module>` | all framework constructs in the module: EDProducer, FHiCL, getValidHandle, FindOneP/FindManyP, PtrMaker, Assns, TFileService, 3 ServiceHandles, `put`/`put_into`; member writes only `fRun`, `fEvent`, counters, `fTree->Fill` in `produce` |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'` and `grep -rn` on the new files | 9 markers (cxx L16, 49, 145, 176, 241, 254, 335, 341, 347), each directly above a line in the notes' section 6 table; table has exactly 9 rows and each maps to a marker. Reasons hold (logging only). |
| Patch fidelity | `diff extraction.patch <(git diff 5d619357)` (ignoring `index` lines) | identical |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | **blocker** | `DisambigFromSpacePointsAlg.cxx:203` | Neighbour score arithmetic changed from `double` to `float`: `score += 1.f/(1.f + distBuff[i])` replaces original `score += 1./(1. + distBuff[i])` (base L443). The original computes `1 + d` and the quotient in double and rounds once on `+=`; the new code rounds `1.f + d`, the quotient, and the sum in float. Scores feed `if (score > bestScore)` (cxx L207) which picks the output `WireID`, so near-tied candidate segments can resolve differently. Reachable on every production configuration (`standard_disambigfromsp.UseNeighbors: true`, `hitfindermodules_dune.fcl:19`). The notes call this block "moved verbatim" (section 4) and list no such edit. | `extraction.patch` L209 vs L840 | Restore `1./(1. + distBuff[i])` exactly. If a `-Wdouble-promotion`-style motive exists, it belongs in pass 2, documented. |
| 2 | minor | `DisambigFromSpacePoints_module.cc:176-179` | Error-path change not in the notes: the boundary calls `spFromHit.at(i)` for every hit, including collection hits and hits whose channel has no wires, before any algorithm step. The original called it only for induction hits with wires (base L307, L317) and in the output loops (L246, L263). If the `Assns<Hit,SpacePoint>` is missing, `FindManyP::at()` throws the stored `ProductNotFound` (canvas `FindManyP.h` `at()` -> `throwIfInvalid()`): same exception, but now before the "No wires for this channel???" warnings the original emitted first, and also in the corner case where every hit has an empty channel-to-wire map (original then threw nothing and put empty products). Needs a missing association product, so minor. | canvas v3_17_01 `FindManyP.h` L347-L351, `IPRHelper.h` L212-L215 | Document in section 4 "Intentional deviations", or resolve lazily. |
| 3 | minor | `DisambigFromSpacePoints_module.cc:173,178` | `&(*ptr)` is `*get()`, and `Ptr::get()` returns `nullptr` for a null-key Ptr (canvas `Ptr.h` L131-L141), whereas the original `h->` / `sp->` go through `operator->` (L143-L152). A null Ptr inside a `FindManyP` result would now become a null pointer dereferenced in the algorithm (crash) instead of the original's art-side failure. The notes (section 2 row 13, section 4) state dereference "raises the same art exception"; that holds for an unavailable product (`parentProduct_` throws `ProductNotFound`) but not for a null Ptr. Needs corrupt associations. | canvas `Ptr.h` L131-L152, L239-L259 | Use `ptr.operator->()` (or `&*ptr` after an `isNull()` check that throws), or correct the notes. |
| 4 | minor | `MIGRATION_NOTES.md:7` | Wrong working tree and branch: says `...-DisambigFromSpacePoints-v1`, branch `phlex-extract/DisambigFromSpacePoints-v1`; the reviewed tree is `...-r4`. | notes L7 | Correct the header. |
| 5 | minor | `MIGRATION_NOTES.md:172` | Pre-existing issue 10 cites a test `DisambigFromSpacePointsAlg_test.cc` (`invalid_tpc_on_collection_hit_skips_space_point_quirk`) and `TESTS.md`; neither exists in the working tree nor in the notes directory. The claim is unverifiable here. | `git status`, `ls` of both dirs | Remove the reference or add the files to this run. |
| 6 | minor | `MIGRATION_NOTES.md:206-221` | Binding plan does not name a Phlex-era home. The module is configured for FD (`dunefd_disambigfromsp`) and protoDUNE (`pdune_disambigfromsp`) in `hitfindermodules_dune.fcl:61-68`, so per `dune-repo-map.md` the plan should name `dune-fd-reco` (with protoDUNE configuration in `dune-pd-hd`) or give candidates plus the deciding question. Dependency table: the algorithm files include no DUNE art-era header other than their own, so nothing is missing there. | `dune-repo-map.md` mapping row for `dunereco` | Add the home and a one-line dependency statement. |
| 7 | minor | `CMakeLists.txt` (unchanged) / notes section 9 | The new `.cxx` is globbed into the `HitFinderDUNE` library, whose `LIB_LIBRARIES` already list `art::*`, `fhiclcpp`, `messagefacility`, `larsim` services, etc. Nothing was added (fine for pass 1), but a future Phlex plugin cannot link this algorithm without pulling art. The binding plan does not mention the need for a separate framework-free library. | `dunereco/HitFinderDUNE/CMakeLists.txt` | Note it as a pass-2 blocker in the binding plan. |
| 8 | minor | `MIGRATION_NOTES.md:223-240` | Validation plan would only catch finding 1 if a near-tie flip happens in the sampled events; it gives no event count and no explicit pass criterion. Otherwise it is sound (unsorted comparison, all `MoveLeftovers` modes, `UseNeighbors: false`, non-empty `ExcludeTPCs`, `hitstats`). | | State bit-identical output as the criterion, compare per-hit `WireID` and association pairs in produced order over a few thousand FD events with `UseNeighbors: true`, after fixing finding 1. |
| 9 | nit | `MIGRATION_NOTES.md:43` | Says `eventHits` is module L161; it is L162. | | |
| 10 | nit | notes section 9 | `art_make` globs sources at configure time; a fresh CMake configure is needed to pick up the new `.cxx`. Not stated. | | Add one line. |
| 11 | nit | `DisambigFromSpacePointsAlg.h:54-56` | Pre-existing out-of-bounds write (induction hit with `Plane >= 2`, notes issue 2) now spills into `stats.nMissedByNeighbors`, which is copied to the tree only when `useNeighbors`; the original spilled into the `fNMissedByNeighbors` member regardless. UB either way, needs unusual geometry, already noted by the extractor. | | None for pass 1. |

No instructions addressed to an agent were found in the source, FHiCL, comments or notes.

## Behaviour-preservation walk-through

Original to new (base = `5d619357:.../DisambigFromSpacePoints_module.cc`; alg = `DisambigFromSpacePointsAlg.cxx`; mod = new module):

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L45-L49 typedefs | alg .h L29-L32 | identical | moved to public header; no other `plane_keymap` in `dunereco` |
| L53-L66 Config | mod L55-L67 | identical | names, types, comments unchanged |
| L104-L119 members | mod L77-L88 | mechanical edit OK | five config members folded into `const DisambigFromSpacePointsCfg fCfg`; init order matches declaration order |
| L122-L159 constructor | mod L91-L135 | mechanical edit OK | `make_cfg` fills every cfg field from the right FHiCL atom (no same-type swaps: `numNeighbors`<-`NumNeighbors`, `maxDistance`<-`MaxDistance`, `useNeighbors`<-`UseNeighbors`); check, `declare_products`, `produces`, geometry, TTree branches identical |
| L163-L190 produce prologue | mod L139-L165 | mechanical edit OK | `fill_ptr_vector` replaced by `*hitsHandle`; `Ptr(handle,i).key()==i` |
| L192 detProp | mod L167 | identical | once per event |
| L194-L212 spToTPC | alg L288-L312 via mod L170-L174 | identical | same iteration and deref order (see glue table) |
| L214-L219 locals, reserve | alg L327-L332 | identical | same reserve before first insert |
| L221-L232 pass sequence and logs | alg L334-L348 | identical | LogInfo texts and order unchanged |
| L234-L269 output loops | mod L191-L226 | mechanical edit OK | `*(eventHits[key])` -> `eventHits[key]` (same `HitCreator(recob::Hit const&, geo::WireID const&)`, `HitCreator.h` L321); `spFromHit.at(eventHits[key].key())` -> `.at(key)` |
| L271-L275 fill and put | mod L228-L232 | identical | unconditional puts |
| L278-L363 runOnSpacePoints | alg L30-L118 | mechanical edit OK | `hit.key()`->`i`, member counters -> `stats`, `sp.key()`->`sp.key`, `sp->position()`->`sp.spacePoint->position()` |
| L365-L442 resolveUnassigned (search) | alg L120-L198 | mechanical edit OK | cfg fields; same `{0,0,plane}` and `GetXTicksCoefficient(0,0)` quirk kept |
| L443 score sum | alg L203 | **CHANGED** | finding 1 |
| L444-L466 rest | alg L205-L226 | identical | erase loop and `insert` unchanged |
| L469-L493 assignFirstAllowedWire | alg L229-L257 | mechanical edit OK | |
| L495-L516 assignEveryAllowedWire | alg L259-L282 | mechanical edit OK | |
| member counters written in helpers | mod L184-L189 | identical effect | `fNHits`, `fNMissedBySpacePoints` every event (original wrote them every event in runOnSpacePoints); `fNMissedByNeighbors` only when `useNeighbors` |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| mod L91-L100 `make_cfg` | copies FHiCL values | none |
| mod L170-L174 | resolves `hitsFromSp` into `Hit const*` per space point | same deref order as original L197-L211 (first loop then second loop touch every hit of each space point in order); null Ptr case differs (finding 3) |
| mod L175-L179 | resolves `spFromHit` into `SpacePointRef` for every hit | earlier `at()` throw point (finding 2); eager `&*sp` for space points the original might not touch (documented by the notes; null Ptr case, finding 3) |
| mod L184-L189 | copies `DisambigStats` into branch members | same values on the same paths |
| alg L322 `DisambigResult res{}` | zero-initialises stats | stats reset in runOnSpacePoints / resolveUnassigned anyway; `nMissedByNeighbors` zero not copied when `!useNeighbors` |
| alg L350 `return res;` | implicit move of the maps | move keeps bucket array and node order |

Loop bounds, `<`/`<=`, signed/unsigned, early `continue`s, map types and insertion order all match apart from finding 1. No random draws. No histograms. No state carried across events beyond config, geometry pointer and the tree buffers (rewritten every event, as before).

## Validation plan

Covers every branch the extraction touched (all three `MoveLeftovers` modes, `UseNeighbors`
on and off, non-empty `ExcludeTPCs`, `MonitoringPlots`), compares products unsorted (correct,
since order should be identical), includes both association products and `hitstats`, and
correctly excludes `fNMissedByNeighbors` when `UseNeighbors: false`. It would detect finding 1
only if a near-tie flip occurs in the sample; see finding 8. Error paths (missing
associations) are not exercised; acceptable for minor findings.

## Compile-risk review

Checked by reading:

- Every identifier in moved code resolves: cfg fields, `stats`, `wireReadout`, typedefs via the
  header, `using dune::...` inside the anonymous namespace.
- Includes: `WireReadoutGeom.h`, `PlaneGeo.h` (cxx), `geo_types.h`, `DetectorPropertiesData.h`,
  `Hit.h`, `SpacePoint.h`, `<array> <map> <string> <unordered_map> <vector>` (h),
  `<algorithm> <cmath> <utility>` (cxx). MessageLogger include is in the `.cxx` only.
- Declarations match definitions for `mapSpacePointsToTPC` and `disambiguateHits` (parameter
  names differ, types identical). No functions defined in the header.
- APIs checked against LArSoft checkout `<LArSoft checkout>` (larcorealg
  `develop` @ b170a9c, 2025-08-25): `WireReadoutGeom::ChannelToWire(raw::ChannelID_t)`,
  `Plane(PlaneID const&)` (the `{0,0,plane}` brace call is unambiguous against the two-argument
  `Plane(TPCID const&, View_t)`), `DetectorPropertiesData::GetXTicksCoefficient(int,int)`,
  `HitCreator(recob::Hit const&, geo::WireID const&)`. The same calls existed in the original,
  so a version mismatch with the `v10_26_00d02` release would affect both equally.
- canvas semantics read from CVMFS UPS `canvas v3_17_01` (`Ptr.h`, `FindManyP.h`,
  `detail/IPRHelper.h`); the release's exact canvas version was not confirmed, but these
  semantics are long-standing.
- No move-only copies, no lambdas, no C++20 features; `std::array` aggregates with `{}` are
  fine in C++17 and C++23.
- Build: `art_make` globs the new `.cxx` into `HitFinderDUNE`, which already links
  `lardataobj::RecoBase`, `larcorealg::Geometry`, `lardataalg::DetectorInfo`,
  `messagefacility::MF_MessageLogger`; the plugin links `HitFinderDUNE`. No CMake change needed.
- Needs build to confirm: nothing specific; overall compile risk is low.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `wireReadout` and
  `detProp` passed explicitly; no helper receives the event or a handle; nothing event-scoped
  cached. Pass.
- Extraction checklist 1 to 5: 1 yes; 2 yes (all inputs are parameters); 3 yes (`DisambigResult`
  by value; internal out-parameters are file-local); 4 yes (`make_cfg`); 5 yes (9 transitional
  logging items, matched). Pass.
- Binding plan: node shapes plausible (event-layer `transform`, `observe` for the tree with a
  serialized ROOT resource; `MonitoringPlots` as registration-time switch rather than a
  predicate is reasonable). No fold/unfold/filter planned. Concurrency `unlimited` consistent
  with zero purity warnings and const-only geometry/detProp use. Blockers named (associations,
  `HitCreator`, conditions). Missing: Phlex-era home (finding 6) and the art-linked library
  (finding 7).

## Notes accuracy

- Section 4 "moved verbatim" / "mechanical edits" omits the float literal change (finding 1).
- Section 2 row 13 and section 4: "same art exception" not true for null Ptrs (finding 3);
  the eager `spFromHit.at()` error-path move is not listed (finding 2).
- Header worktree/branch wrong (finding 4); test file reference unverifiable (finding 5);
  one line number off by one (finding 9).
- All other claims checked (contract, transitional table, `reserve`, map move, stats write
  paths, pre-existing issues 1 to 9, CMake) match the code.
