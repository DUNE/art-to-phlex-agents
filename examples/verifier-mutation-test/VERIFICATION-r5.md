# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 1 major, 5 minor, 2 nit |
| Working tree and base | `<worktree-r5>` (branch `phlex-extract/DisambigFromSpacePoints-r5`, uncommitted) against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r5/MIGRATION_NOTES.md` (plus `contract.*.txt`, `extraction.patch`) |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The module was split into a framework-free `DisambigFromSpacePointsAlg.{h,cxx}` (free
  functions, `DisambigFromSpacePointsCfg`, `DisambigResult`, `DisambigStats`) and a thin art
  module that resolves associations into plain containers and publishes products. The moved
  algorithm bodies are statement-for-statement identical apart from mechanical renames.
- Purity is clean (only the 9 documented MessageLogger transitional items) and the framework
  contract is unchanged (13 items, also checked by hand).
- **Blocker:** `hitToWire.reserve(eventHits.size())` (original L219) was dropped. The
  `std::unordered_map` now grows through rehashes, so its iteration order, and with it the
  order of the output `std::vector<recob::Hit>`, the hit-wire `Assns` and the hit-space point
  `Assns`, changes. `MIGRATION_NOTES.md` says the reserve was kept; it was not.
- The extractor's notes appear partly stale (they name a `-v1` worktree and a test file that
  are not in this worktree), which is how the missing reserve slipped past.
- Before a build: restore the one-line reserve in `disambiguateHits`, fix the notes, then run
  the validation plan, which compares unsorted products and would catch this regression.

## Original module in brief

Written from `git show 5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`
before reading the new code or the notes.

An `art::EDProducer` that reads a hit collection and a space point collection plus the
hit-space point associations in both directions. It maps each space point to a TPC using its
first collection hit, then assigns every collection hit to the channel's first wire and every
induction hit to the wire segment (per TPC vote) within one wire pitch of its space points.
Hits left unassigned are optionally resolved by a distance-weighted score of the N nearest
resolved hits on each candidate segment, then the leftovers go on every allowed wire
("repeat"), the first allowed wire ("first") or are dropped. It writes a new hit collection
(via `HitCollectionCreator`, with hit-wire associations when the input had them) and a copied
`Assns<recob::Hit, recob::SpacePoint>`, in `unordered_map` iteration order of `hitToWire`
then `hitToNWires`. With `MonitoringPlots`, it fills a `hitstats` TTree from member counters
(`fNMissedByNeighbors` only written when `UseNeighbors`). Contract: FHiCL table of 8
parameters, `declare_products(..., "", true, false)`, one `produces<Assns>`, services
`WireReadout`, `DetectorPropertiesService`, `TFileService`.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (`.cxx` L17, L50, L146, L177, L242, L255, L334, L340, L346) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:<module> --after <module>` | contract unchanged (13 items); matches `contract.before.txt` = `contract.after.txt` |
| Algorithm inventory | `art_inventory.py report <algorithm files>` | `.h`: no framework constructs. `.cxx`: only the MessageLogger include and 8 `mf::Log*` calls |
| Module inventory | `art_inventory.py report <module>` | all framework constructs in the module; member writes in `produce` are `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` (monitoring buffers, as before) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -rn PHLEX-TRANSITIONAL` | 9 markers, all MessageLogger, all in `.cxx` (comments at L16, 49, 145, 176, 241, 254, 333, 339, 345). All 9 appear in the notes' table with a valid reason; the table's line numbers for the three `LogInfo` lines are off by 2 (finding 5). No marker without a table row and no row without a marker. |
| Patch vs worktree | `git diff 5d619357` vs `extraction.patch` | identical |
| Agent-addressed instructions in source/notes | grep and reading | none found |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | **blocker** | `DisambigFromSpacePointsAlg.cxx:329-332` | `hitToWire.reserve(eventHits.size())` from original L219 is missing. `hitToWire` (an alias of `res.hitToWire`) starts with the default bucket count and rehashes as `runOnSpacePoints`, `resolveUnassigned` (`insert`) and `assignFirstAllowedWire` fill it. In libstdc++ the iteration order of an `unordered_map` depends on the bucket count and rehash history, so the module's loop at module L193 emits hits, hit-wire pairs and hit-space point pairs in a different order. Data products change on every event with more than a handful of hits. | `grep reserve` finds nothing in the three files; the original reserved before the first insert (base L219) and never exceeded `eventHits.size()` entries, so it never rehashed. Needs build to confirm empirically, but the libstdc++ node-list insertion and rehash logic makes a different order near-certain. | Add `hitToWire.reserve(eventHits.size());` immediately after `auto & hitToWire = res.hitToWire;` and before the `runOnSpacePoints` call. Keep returning `res` by value (a move keeps the node structure). |
| 2 | major | `MIGRATION_NOTES.md:145` | False claim that hides finding 1: "Kept: `hitToWire.reserve(eventHits.size())` before the first insert". Section 4 L130 also lists "reserve" among the moved lines. | The `.cxx` has no reserve. | Correct the notes after restoring the reserve; have the extractor regenerate notes from this worktree rather than a previous run. |
| 3 | minor | `DisambigFromSpacePoints_module.cc:173,178` | Eager `&(*ptr)` resolution. Documented for the unavailable-product case (notes L147-L159). Not documented: for a **null** `art::Ptr`, `operator*` goes through `get()`, which returns `nullptr` (canvas v3_17_01 `Ptr.h` L131-L141), so the new code stores a null pointer and later segfaults in `h->SignalType()` / `sp.spacePoint->position()`, where the original `h->` / `sp->` went straight to `operator->` (L144) and would have raised an art exception from `parentProduct_`. Also, space points are now resolved for every hit, including collection hits. Needs corrupt input (null Ptr in an Assns). | canvas `Ptr.h` read from `/cvmfs/larsoft.opensciencegrid.org/products/canvas/v3_17_01`. | Accept, or resolve with `ptr.operator->()` / `ptr.get()` plus a throw on null, and add the null-Ptr case to the notes' deviation list. |
| 4 | minor | `DisambigFromSpacePointsAlg.h:53-57`, module `:184-189` | Pre-existing UB (notes issue 2) is not preserved in what it records: in the original, an induction-type hit with `Plane == 2` wrote `fNMissedBySpacePoints[2]`, which in practice landed in `fNMissedByNeighbors[0]` and reached the tree when `UseNeighbors: false`. Now it lands in `stats.nMissedByNeighbors[0]`, which the module does not copy when `UseNeighbors: false`. The notes say the field order keeps the same behaviour. Needs a non-collection hit on plane 2, so unusual input. | Layout reasoning; UB either way. | Say so in notes issue 2 (or add a bound check as a documented deviation in a later pass). |
| 5 | minor | `MIGRATION_NOTES.md:7,172,199-201,128-131` | Notes do not match this worktree: header names worktree `...-v1` and branch `phlex-extract/DisambigFromSpacePoints-v1` (actual `-r5`); issue 10 cites a `phlex-tester` finding, `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`, none of which exist in this worktree; transitional table gives `LogInfo` at L336/L342/L348 (actual L334/L340/L346) and section 4 gives `disambiguateHits` L314-L351 with return at L350 (actual L314-L349, return L348). | `git status`, `ls dunereco/HitFinderDUNE/`. | Regenerate the notes from the `-r5` worktree. |
| 6 | minor | `MIGRATION_NOTES.md` section 7 | Binding plan names no Phlex-era home. The module runs in FD (`dunefd_disambigfromsp`) and ProtoDUNE-HD (`pdune_disambigfromsp`) jobs per the notes, so by `dune-repo-map.md` the candidate is `dune-fd-reco` (with the protoDUNE configuration in `dune-pd-hd`). The dependency table is trivially empty (the algorithm includes no other DUNE header), which the notes should state. | `grep '#include "dune'` on the algorithm files: only the self-include. | Add the home and an empty dependency table. |
| 7 | minor | `dunereco/HitFinderDUNE/CMakeLists.txt` (unchanged) | The algorithm is globbed into the existing `HitFinderDUNE` library, which links `art::*`, `larsim` service libraries and `messagefacility`. No framework library was added, so this is acceptable for pass 1, but the algorithm is not yet an ordinary framework-free shared library a Phlex plugin could link. Not mentioned in the notes. | `art_make LIB_LIBRARIES` list. | Note it in the binding plan as a later split into its own target. |
| 8 | nit | `DisambigFromSpacePointsAlg.h:30-41` | Unqualified `size_t` in a public header, relying on `<cstddef>` also declaring `::size_t`. Same as the original module; works with libstdc++. | | `std::size_t` when the file is next touched. |
| 9 | nit | `MIGRATION_NOTES.md` section 8 | Validation plan does not say that a fresh CMake configure is needed so `art_make` picks up the new `.cxx`. | | Add one line. |

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L46-L49 typedefs | `.h` L29-L32 | identical | |
| L122-L137 ctor init, `NumNeighbors < 1` throw | module L102-L113, `make_cfg` L91-L100 | mechanical edit OK | each FHiCL field maps to the same-typed cfg field; no swaps; throw text and type unchanged |
| L139-L158 declare_products, produces, WireReadout, TTree branches | module L115-L134 | identical | |
| L163-L190 run/event, handles, `FindOneP`, `hcol`, `assns`, `FindManyP` x2 | module L139-L165 | identical except L186-L187 | `fill_ptr_vector` replaced by `*hitsHandle`; keys equal indices, so equivalent |
| L192 `detProp` | module L167 | identical | still once per event |
| L194-L212 space point → TPC map | `.cxx` `mapSpacePointsToTPC` L288-L312 | mechanical edit OK | `auto hits` copy → `auto const&`; same loops, same `InvalidID` sentinel, same `operator[]` writes |
| L214-L217 locals | `.cxx` L327-L330 | mechanical edit OK | `hitToWire`/`hitToNWires` now members of `res` |
| **L219 `hitToWire.reserve(eventHits.size())`** | **none** | **CHANGED** | finding 1 |
| L221-L232 pass sequence and `LogInfo`s | `.cxx` L332-L346 | mechanical edit OK | same order, same text, same `MoveLeftovers` comparisons |
| L234-L269 output loops | module L191-L226 | mechanical edit OK | `*(eventHits[key])` → `eventHits[key]`; `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)` (key == index); iteration order identical only if finding 1 is fixed |
| L271-L275 fill, put | module L228-L232 | identical | unconditional puts preserved |
| L278-L363 `runOnSpacePoints` | `.cxx` L30-L118 | mechanical edit OK | `hit.key()` → `i`; `sp.key()` → `sp.key`; `sp->position()` → `sp.spacePoint->position()`; `fNHits`… → `stats.*`; same `tpcScore` tie-break by `unordered_map` order (same container, same insertions) |
| L365-L467 `resolveUnassigned` | `.cxx` L120-L227 | mechanical edit OK | `fMaxDistance`/`fExcludeTPCs` → `cfg.*`; float casts, `{0,0,plane}` lookups, `distBuff` logic, `erase/remove`, `insert` unchanged |
| L469-L493 `assignFirstAllowedWire` | `.cxx` L229-L257 | identical (renames) | |
| L495-L516 `assignEveryAllowedWire` | `.cxx` L259-L282 | identical (renames) | |
| member counters `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` | `DisambigStats` + module L184-L189 | mechanical edit OK | written every event except `fNMissedByNeighbors` only when `UseNeighbors`, as before (indeterminate-value bug kept on purpose); see finding 4 for the UB spill case |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-L174 | `hitsPerSpacePoint[i].push_back(&*h)` for all space points | same Ptrs dereferenced as the original's first loops, same order; null-Ptr case differs (finding 3) |
| module L175-L179 | `spacePointsPerHit` with `{sp.key(), &*sp}` for every hit | eager resolution, documented; null-Ptr case and the extra resolution of collection-hit space points are new (finding 3) |
| module L184-L189 | copy `result.stats` into the branch buffers | same values on the same paths; finding 4 for UB input |
| `.cxx` L322 `DisambigResult res{}` | value-initialises stats | counters are reset before use in each pass, so no visible change; the `nMissedByNeighbors` zero is never copied when `UseNeighbors: false` |
| `.cxx` L348 / module L181 return by value | NRVO or move of the maps | preserves node order |
| `make_cfg` | builds cfg once | no per-event effect |

## Validation plan

The plan in section 8 is a good test for this change. It compares the output hits and both
association products **unsorted**, so it would catch finding 1 at once. It covers
`MoveLeftovers` "repeat", "first" and drop, `UseNeighbors: false`, a non-empty `ExcludeTPCs`,
and `MonitoringPlots: true`, which together exercise every branch the extraction touched.
Excluding `fNMissedByNeighbors` when `UseNeighbors: false` is right. It cannot exercise the
null-Ptr path (finding 3), which is acceptable. Add the fresh CMake configure (finding 9).
The unit-test idea references a test file not present in this worktree (finding 5).

## Compile-risk review

Read against the LArSoft checkout at `<LArSoft checkout>` (lardata v10_00_16,
lardataalg v10_02_01, i.e. larsoft v10_16_00; older than the base's v10_26_00d02 release, so
treat as close but not exact) and canvas v3_17_01 on CVMFS.

- `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) const`, `Plane(PlaneID const&) const`:
  present (`WireReadoutGeom.h` L574, L151). `PlaneGeo::WireCoordinate(Point_t const&)`,
  `WirePitch()`: present (`PlaneGeo.h` L704, L312). `DetectorPropertiesData::GetXTicksCoefficient(int,int) const`:
  present (L89). `HitCreator(recob::Hit const&, geo::WireID const&)`: present (`HitCreator.h` L321).
- Includes: every type used in the new files has an include; `PlaneGeo.h` is in the `.cxx`;
  the transitional MessageLogger include is in the `.cxx`, not the header. The module still
  relies on the same transitive includes for `FindManyP`/`FindOneP`/`PtrMaker` as the original.
- Declarations match definitions (`mapSpacePointsToTPC`, `disambiguateHits`: same types,
  parameter names differ only, which is fine). No default arguments. No functions defined in
  the header. Anonymous-namespace helpers have `using dune::...` for the moved typedefs and
  structs; `geo::WireID::InvalidID` comes through `geo_types.h`.
- `const&` parameters: helpers that mutate take non-const references; `allIndHits[...]`
  `operator[]` is on a non-const reference, as in the original.
- `static make_cfg(Config const&)` with `config()` returning `Config const&`; member init order
  (`fTree`, `fMonitoringPlots`, `fCfg`, labels) matches declaration order.
- No C++20/23-only or removed constructs. Aggregate `SpacePointRef{...}` is C++11.
- Build: `art_make` globs `.cxx` into `HitFinderDUNE` (other `*Alg.cxx` files in this directory
  already rely on it); `LIB_LIBRARIES` already has `larcorealg::Geometry`,
  `lardataalg::DetectorInfo`, `lardataobj::RecoBase`, `messagefacility::MF_MessageLogger`; the
  plugin links `HitFinderDUNE`. Low compile risk overall; needs build to confirm.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `wireReadout` and
  `detProp` passed explicitly; no helper receives the event or a handle; nothing event-scoped
  kept across events (the `SpacePointRef` pointers live only for the call).
- Extraction checklist 1 to 5: (1) yes; (2) yes, all inputs are parameters; (3) yes,
  `DisambigResult` by value; (4) yes, `make_cfg`; (5) yes, 9 logging items, all marked and
  tabled. Checklist answers are right, but item 3's claim of order preservation fails until
  finding 1 is fixed.
- Binding plan: node shapes plausible (event-layer `transform`, `observe` for the tree with a
  serialized ROOT resource, registration-time switch for `MonitoringPlots`); blockers named
  (persistable associations, `HitCreator` art dependency, conditions access); algorithm inputs
  are const; `disambiguateHits` is re-entrant (no statics, const geometry/detprop use).
  Missing Phlex-era home (finding 6).

## Notes accuracy

- L145 and L130: reserve "kept"; it is not (finding 2).
- L7: worktree and branch name `-v1`; actual `-r5` (finding 5).
- L172: cites `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`; not in this worktree (finding 5).
- L199-L201, L49 and L128-L131: line numbers for the `LogInfo` calls and `disambiguateHits` are
  off by 2 at the end of the file (finding 5).
- L164 (issue 2): "keeps the same field order" implies the UB spill is preserved; it no longer
  reaches the tree when `UseNeighbors: false` (finding 4).
- L45 (inventory row 13): "kept as `FindManyP` so that dereference raises the same art
  exception" holds for an unavailable product, not for a null Ptr (finding 3).
- Everything else checked (inventory rows, mechanical-edit list, contract claims, purity
  summary, include list, CMake claim) matches the code.
