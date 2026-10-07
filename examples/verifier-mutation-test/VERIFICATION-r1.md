# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 0 major, 5 minor, 2 nit |
| Working tree and base | `<worktree-r1>` (branch `phlex-extract/DisambigFromSpacePoints-r1`, uncommitted) against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r1/MIGRATION_NOTES.md` |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The extraction moves the four private helpers and the space point to TPC mapping into `DisambigFromSpacePointsAlg.{h,cxx}`. The algorithm files are framework-free apart from 9 documented MessageLogger lines. The framework contract (13 items) is unchanged, and `extraction.patch` matches the worktree diff exactly.
- **One behaviour change:** `mapSpacePointsToTPC` dropped the `break` after the first collection hit (`DisambigFromSpacePointsAlg.cxx:299`). Each space point now takes the TPC of its *last* collection hit, not its first. The notes call this block "moved verbatim". With SpacePointSolver input (one collection hit per space point) the output is the same. With any producer that links two collection hits in different TPCs, the output hits change.
- Everything else matches statement for statement: the order of the `unordered_map` operations (same `reserve`, same insertion sequence, the map moved out by NRVO or move), the monitoring write paths (including the original's leaving `fNMissedByNeighbors` unset when `UseNeighbors: false`), log text and order, and exceptions.
- `MIGRATION_NOTES.md` seems to have been carried over from another run: it names a `-v1` worktree and branch, and cites a `phlex-tester` test file and `TESTS.md` that do not exist in this worktree or notes directory.
- Before building: restore the `break`, correct the notes, and add a unit test (or an input) that covers space points with more than one collection hit. Then run the regression plan.

## Original module in brief

Written before reading the new code or the notes.

`DisambigFromSpacePoints` is an `art::EDProducer`. It reads the hits (`HitModuleLabel`), the space points and both directions of the hit and space point association (`SpModuleLabel`), and the hit to wire association (`FindOneP<recob::Wire>`). For each space point it records the TPC of its first collection hit, and only if the space point also has an induction hit. Collection hits keep `ChannelToWire().front()`. Each induction hit votes per TPC for a wire segment within one wire pitch of its space points, and the most-voted TPC's last matching segment wins. Hits still unresolved can then be placed by neighbour scoring (`UseNeighbors`, `NumNeighbors`, `MaxDistance`, `ExcludeTPCs`), and the leftovers go on every allowed segment (`repeat`), on the first allowed one (`first`), or are dropped. Output: a new `std::vector<recob::Hit>` with hit to wire associations through `HitCollectionCreator` (no raw digit associations), `Assns<recob::Hit, recob::SpacePoint>` copied from the original hits, and an optional `hitstats` TTree with per-plane counters. Output order follows `unordered_map` iteration order.

## Automated checks

Run from the worktree, with `S=$KIT/skills/art-phlex-extract/scripts`.

| Check | Command | Result |
|---|---|---|
| Purity | `python3 $S/check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (cxx L17, 50, 146, 177, 242, 255, 336, 342, 348) |
| Contract | `python3 $S/art_inventory.py --repo <wt> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | contract unchanged (13 items); `contract.before.txt` and `contract.after.txt` are identical |
| Algorithm inventory | `python3 $S/art_inventory.py report <alg .h .cxx>` | only `[messagefacility]` include L17 and 8 `MessageLogger` uses |
| Module inventory | `python3 $S/art_inventory.py report DisambigFromSpacePoints_module.cc` | every framework construct is now in the module; member writes are `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors`, `fTree` in `produce` |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -n PHLEX-TRANSITIONAL <alg files>` | 9 markers (cxx L16, 49, 145, 176, 241, 254, 335, 341, 347), each one line above a logging statement. They match the notes' table of 9 in both directions, and each reason (logging) holds |
| Patch fidelity | diff of `+`/`-` lines in `extraction.patch` vs `git diff 5d619357` | identical |
| Scope | `git status --short`; `git ls-files --others` | only the module plus the two new files (intent-to-add) in `dunereco/HitFinderDUNE/`; no build file changes |
| DUNE includes in algorithm | `grep '#include "dune' <alg files>` | only its own header |
| Instructions addressed to agents | grep of the new sources and the notes | none found |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | **blocker** | `DisambigFromSpacePointsAlg.cxx:299` | The `break` after the first collection hit was dropped. A space point is now mapped to the TPC of its **last** collection hit, not its first. When a space point links collection hits in two TPCs, `spToTPC` changes, so the per-TPC votes in `runOnSpacePoints`, the chosen `WireID`s, `indHits`, the neighbour pass, and the output hits and associations all change. The notes (§4, "moved verbatim") hide this. Likelihood: the shipped `reco3d` (SpacePointSolver) links at most one collection hit per space point (`larreco/SpacePointSolver/SpacePointSolver_module.cc:383`, `fCWire`), so standard jobs are unaffected. `SpModuleLabel` is configurable, though, and the pass must be statement for statement. | base L201: `if (h->SignalType() == geo::kCollection) { tpc = h->WireID().TPC; break; }`; new L299: `if (h->SignalType() == geo::kCollection) { tpc = h->WireID().TPC; }` | Restore `break;` and correct notes §4. |
| 2 | minor | `DisambigFromSpacePoints_module.cc:170-179` | The module now resolves all association Ptrs before running the algorithm. Every `art::Ptr<recob::SpacePoint>` of every hit (collection hits too) is dereferenced with `&*sp` up front. The original dereferenced one only at base L328, for induction hits with a matching TPC. If the hit to space point `Assns` is missing, `spFromHit.at(0)` now throws before any algorithm log line, where the original would have logged first and then thrown. The products and the exception are the same. The notes document this (§4) and it needs unusual input. Canvas `Ptr::operator*` semantics (throw versus null) are an **unverified assumption**: no canvas headers in the LArSoft checkout, CVMFS or caches. Base L328 used `sp->` and the new code uses `*sp`, so both go through the same `get()`. | module L178 `SpacePointRef{sp.key(), &(*sp)}` | Accept as documented, or resolve lazily in pass 2. |
| 3 | minor | `MIGRATION_NOTES.md:7`, `:172` | The notes seem to come from another run. L7 gives the worktree as `.../dunereco-phlex-DisambigFromSpacePoints-v1` and the branch as `phlex-extract/DisambigFromSpacePoints-v1`; the actual branch is `phlex-extract/DisambigFromSpacePoints-r1`. Issue 10 (L172) cites "Found by `phlex-tester`", `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`, and none exist in this worktree or notes directory. **Orchestrator:** check whether the r1 extractor read another run's artefacts (independence). | `git branch --show-current`; `find` of the worktree | Rewrite the header table and drop or re-source issue 10. |
| 4 | minor | `MIGRATION_NOTES.md:223-240` (§8) | The validation plan would not catch finding 1: all its jobs use SpacePointSolver input. The rest of the plan is sound (unsorted comparison of products and association pairs, all three `MoveLeftovers` modes, `UseNeighbors: false`, non-empty `ExcludeTPCs`, `hitstats` with the `fNMissedByNeighbors` caveat). | | Add a framework-free unit test of `mapSpacePointsToTPC`: one space point with two collection hits in different TPCs plus one induction hit; expect the first hit's TPC. |
| 5 | minor | `MIGRATION_NOTES.md` §7 | The binding plan names no Phlex-era home (kit step 6, `dune-repo-map.md`). Per the notes, the module runs in FD (`hitfd`) and ProtoDUNE-HD (`hitpdune`) jobs. | no "home" or repo name in §7 | Name `dune-fd-reco` as the likely home, with `dune-pd-hd` as the alternative. The deciding question: is protoDUNE-HD the only production user? |
| 6 | minor | `dunereco/HitFinderDUNE/CMakeLists.txt` (unchanged) | `art_make` builds the algorithm into `HitFinderDUNE`, and its `LIB_LIBRARIES` already link art, `art::Framework_Services_Registry`, larsim service libraries, `messagefacility` and `fhiclcpp`. This is not new, and pass 1 needs no CMake change. But a future Phlex plugin cannot link this library without pulling in art, and the notes do not flag it. | CMakeLists L1-L44 | Record as a pass-2 item: a separate framework-free `SHARED` target for the algorithm. |
| 7 | nit | `DisambigFromSpacePointsAlg.h:22,30-41` | Uses unqualified `size_t` with only `<cstddef>` included (only `std::size_t` is guaranteed). In practice `::size_t` arrives through the LArSoft headers. | | `std::size_t`, or leave it. |
| 8 | nit | `MIGRATION_NOTES.md:43` | The line reference for `eventHits` says module L161; it is L162. | | Fix the reference. |

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L45-49 typedefs | Alg.h L28-32 | identical | same namespace `dune`; no other definitions in dunereco |
| L53-66 Config | module L55-67 | identical | names, types and comments unchanged |
| L122-133 ctor init list | module L102-108 + `make_cfg` L91-100 | mechanical edit OK | same values; the FHiCL tables are validated, so read order does not matter; member init order matches declaration order |
| L134-137 NumNeighbors check | module L110-113 | identical | `fCfg` is set before the check, as `fNumNeighbors` was |
| L142-158 products, geometry, TTree | module L118-134 | identical | |
| L163-167 run, event, handles | module L139-143 | identical | |
| L172-183 FindOneP, hcol, assns | module L148-159 | identical | |
| L186-187 `fill_ptr_vector` | module L162 `*hitsHandle` | mechanical edit OK | `fill_ptr_vector` gives Ptr key == index |
| L189-190 FindManyP | module L164-165 | identical | |
| L192 detProp | module L167 | identical | still once per event |
| L194-212 spToTPC loop | Alg.cxx L288-311 | **CHANGED** | `break` dropped at L299 (finding 1); `auto hits` copy became `auto const&` (fine) |
| L214-219 locals, reserve | Alg.cxx L327-332 | mechanical edit OK | maps now live in `DisambigResult`, created by value-initialisation; `reserve` happens before the first insert as before |
| L221-232 pass sequence and logs | Alg.cxx L334-348 | mechanical edit OK | same order and text; LogInfo moved into the algorithm |
| L234-269 output loops | module L191-226 | mechanical edit OK | `*(eventHits[key])` became `eventHits[key]` (same object); `spFromHit.at(eventHits[key].key())` became `.at(key)` (same index); same iteration of the same maps |
| L271-275 Fill, puts | module L228-232 | identical | |
| L278-363 runOnSpacePoints | Alg.cxx L30-118 | mechanical edit OK | `hit.key()` became `i`; counters became `stats.*`; `sp.key()`/`sp->` became `sp.key`/`sp.spacePoint->` |
| L365-467 resolveUnassigned | Alg.cxx L120-227 | mechanical edit OK | `fMaxDistance`/`fExcludeTPCs` became `cfg.*`; float, int and size_t types unchanged |
| L469-493 assignFirstAllowedWire | Alg.cxx L229-257 | identical except renames | |
| L495-516 assignEveryAllowedWire | Alg.cxx L259-282 | identical except renames | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-174 | builds `hitsPerSpacePoint` with `&*h` for every hit of every space point | none. The original dereferenced every hit too (in loop 1 or loop 2), in the same order |
| module L175-179 | builds `spacePointsPerHit` with `{sp.key(), &*sp}` for all hits | error path only (finding 2) |
| module L184-189 | copies `stats` into the branch members; `fNMissedByNeighbors` only when `useNeighbors` | same values and write conditions as the original; `stats.nMissedByNeighbors{}` zero-initialisation is not copied on the `false` path, so the original indeterminate value is kept |
| Alg.cxx L322 `DisambigResult res{}` and `return res` | value return | NRVO or implicit move keeps the `unordered_map` node and bucket structure, so iteration order is kept; at the call site (module L181) the copy is elided |
| Alg.h L54-56 `std::array<int,N>` | replaces the C arrays | same element type. An out-of-range `plane` is UB either way (notes issue 2) |

## Validation plan

It covers every branch the extraction touched (all `MoveLeftovers` values, `UseNeighbors` on and off, `ExcludeTPCs`, `MonitoringPlots`). It compares products and association pairs unsorted, which suits a claim of identical order. It would **not** detect finding 1, because SpacePointSolver input never puts two collection hits on one space point. See finding 4.

## Compile-risk review

Checked by reading against the LArSoft checkout at `<LArSoft checkout>`. The repository records no tag, so it is unconfirmed that this matches what dunereco `5d619357` builds against.

- `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) -> std::vector<WireID>` (WireReadoutGeom.h:574); `Plane(PlaneID const&) -> PlaneGeo const&` (:151); `PlaneGeo::WireCoordinate(Point_t const&)` (PlaneGeo.h:704); `WirePitch()` (:312); `DetectorPropertiesData::GetXTicksCoefficient(int,int)` (:89); `WireReadout::Get()` (WireReadout.h:36); `HitCreator(recob::Hit const&, geo::WireID const&)` (HitCreator.h:321); `SpacePoint::position() -> geo::Point_t`; `Hit::WireID() const&`, `PeakTime()`, `SignalType()`. All resolve.
- Every identifier in the moved code resolves: the `using` declarations in the anonymous namespace cover `cryo_tpc_plane_keymap`, `DisambigFromSpacePointsCfg`, `DisambigStats`, `SpacePointRef`. `geo::kCollection`/`kInduction`/`WireID::InvalidID` come in through `geo_types.h`/`Hit.h`.
- Includes: `<algorithm>` (for `std::remove`) and `<cmath>` are in the cxx, `PlaneGeo.h` is in the cxx, and the transitional MessageLogger include is in the cxx, not the header. The header declarations match the definitions; there are no default arguments and no non-inline definitions in the header.
- `make_cfg` is a static member taking `Config const&` and called with `config()`; that works. `fCfg` is `const` and passed by `const&`.
- `SpacePointRef{sp.key(), &(*sp)}`: aggregate init from the Ptr key type (an unsigned integer of size_t width), so no narrowing. Needs build to confirm only in the theoretical sense.
- Nothing newer than C++17 is used (no designated initialisers); the algorithm headers have nothing removed in C++20/23.
- Build: `art_make` globs the new `.cxx` into `HitFinderDUNE`, which already links `larcorealg::Geometry`, `lardataalg::DetectorInfo`, `lardataobj::RecoBase` and `messagefacility::MF_MessageLogger`. A fresh CMake configure is needed for the glob. No art library was added (the existing ones are pre-existing, finding 6).
- Unverified assumption: canvas `Ptr` dereference semantics (finding 2). Not central to correctness.

## Guide conformance

- Separation checks: `ServiceHandle` appears only in the module (L123, 127, 167). `wireReadout` and `detProp` are passed explicitly. No helper receives the event or a handle. Nothing event-scoped persists across events: the branch buffers are rewritten every event, and `fNMissedByNeighbors` keeps its original behaviour.
- Extraction checklist 1 to 5: met. A config struct (1), free-function extraction (2), all inputs explicit (3), outputs returned in `DisambigResult` (4), framework registration only in the module TU, and transitional logging documented (5).
- Binding plan: plausible. An event-layer `transform` with `unlimited` concurrency fits: the algorithm takes const inputs and keeps no mutable state, and `check_purity.py` gave no concurrency warnings. An `observe` with `serial`/serialized-resource for the TTree fits too. The association and `HitCreator` blockers are named. No unfold, filter or fold is planned, so those rules do not apply. The Phlex-era home is missing (finding 5).

## Notes accuracy

- §4 "Code moved verbatim: `produce` L193-L212 → `mapSpacePointsToTPC`" is false (finding 1, rated blocker because it hides a product change).
- L7 worktree and branch (`-v1`), and issue 10's `phlex-tester`, `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`, do not match this run (finding 3).
- §7 has no Phlex-era home (finding 5). The CMake section does not mention that the hosting library links art (finding 6).
- The other claims checked out: inventory, contract, the transitional table, the deviation for eager space point dereferencing, and pre-existing issues 1-9.
