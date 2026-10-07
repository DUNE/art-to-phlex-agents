# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **PASS WITH NOTES** |
| Findings | 0 blocker, 0 major, 4 minor, 3 nit |
| Working tree and base | `<worktree-r2>` (branch `phlex-extract/DisambigFromSpacePoints-r2`, uncommitted) against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r2/MIGRATION_NOTES.md` (+ `contract.*.txt`, `extraction.patch`) |
| Verifier / model / date | phlex-verifier (Claude Code subagent), Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- Three files changed, all in `dunereco/HitFinderDUNE/`: the module was rewritten as a boundary, and `DisambigFromSpacePointsAlg.h/.cxx` are new. No build file changed. `art_make` globs the new `.cxx` into `HitFinderDUNE`, which the plugin already links.
- `extraction.patch` matches `git diff 5d619357` in the worktree, apart from `index` lines.
- Product behaviour looks preserved. The four helpers and the spacepoint-to-TPC map moved verbatim with mechanical renames. The `hitToWire` `unordered_map` is still reserved once, filled by the same insert sequence, and moved out, so the output hit and `Assns` order is unchanged. Hit keys equal indices, as `fill_ptr_vector` guarantees.
- The monitoring tree is preserved, including the original quirk that `fNMissedByNeighbors` is never written when `UseNeighbors: false`.
- The only behavioural difference is on corrupt-input error paths: art::Ptr resolution is now eager and goes through `operator*`, so a null Ptr becomes a null dereference instead of an `art::Exception` (minor, M1).
- The notes contain stale material from another run (worktree/branch `-v1`, and a `phlex-tester` test file that does not exist here) and omit the Phlex-era home section (M2, M3). These need fixing before sign-off.
- Before merge: a build, then the regression comparison in notes section 8.

## Original module in brief

*(Written from `git show 5d619357:...` before reading the new code or the notes.)*

`DisambigFromSpacePoints` is a legacy `art::EDProducer`. It reads hits (`HitModuleLabel`), space points and their hit associations (`SpModuleLabel`), and `recob::Wire` associations of the hits. It maps each space point to a TPC through its first collection hit. Then it chooses a wire segment for every hit. A collection hit gets its channel's first wire. An induction hit gets the segment within one wire pitch of its space points, voted per TPC. Optionally, the unresolved hits are placed by a nearest-resolved-neighbour score. Leftover hits are then repeated on every allowed segment, put on the first allowed segment, or dropped. Its contract is: `HitCollectionCreator::declare_products(..., "", true, false)` plus `produces<Assns<Hit,SpacePoint>>`, both put unconditionally. It uses the `WireReadout` and `DetectorPropertiesService` services. If `MonitoringPlots` is set, it also writes an optional `hitstats` TTree from member counters that the private helpers fill as side effects. Output order follows `std::unordered_map` iteration order.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (all MessageLogger: include L17, warnings L50/146/177/242/255, infos L336/342/348) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | contract unchanged (13 items); `contract.before.txt` and `contract.after.txt` are identical. I also compared declarations and puts by hand: same calls, same order, unconditional. |
| Algorithm inventory | `art_inventory.py report <alg .h .cxx>` | Only the framework construct is the MessageLogger (include + 8 calls), all marked |
| Module inventory | `art_inventory.py report <module>` | Framework constructs now sit in the module: services, FHiCL, `FindOneP`/`FindManyP`, `PtrMaker`, `TFileService`, puts. Members written in `produce`: `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` (branch buffers, as before) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -n PHLEX-TRANSITIONAL <alg files>` | 9 markers in the diff (alg .cxx L16, 49, 145, 176, 241, 254, 335, 341, 347), each on the line before the marked construct. Each one matches a row of notes section 6 and the reason holds (logging only). The table has no rows without a marker. |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| M1 | minor | `DisambigFromSpacePoints_module.cc:173`, `:178` | Every Ptr from both `FindManyP`s is now resolved eagerly with `&(*ptr)`. In canvas 3.17 `Ptr::operator*` is `*get()`, and `get()` returns `nullptr` for a null Ptr. The original used `h->` and `sp->`, which call `parentProduct_()` and throw `art::Exception(ProductNotFound)`. A null Ptr in the Hit-SpacePoint `Assns` therefore becomes a null dereference (UB/segfault) in the algorithm instead of an art exception. For space points it also fires for Ptrs the original never touched. Separately, `spFromHit.at(i)` is now called for every hit, so a missing `Assns` throws `LogicError "Invalid FindManyP"` in events where the original might not have (only when every hit has an empty `ChannelToWire`). Both cases need corrupt or unusual input. Notes section 2 row 13 and section 4 claim the dereference "raises the same art exception", which is wrong for null Ptrs. | canvas `Ptr.h` L129-151 and L238-260 (`~/.cache/rattler/cache/pkgs/canvas-3.17.0-h39d6d14_0`); original L201, L210, L328 used `->` | Resolve with `ptr.operator->()` / `&*` only after `if (ptr.isNull()) throw art::Exception(...)`, or use `ptr.operator->()` directly, which throws like the original. Correct the notes' claim. Otherwise, accept and document the change. |
| M2 | minor | `MIGRATION_NOTES.md:7`, `:172` | The notes contain material from another run. The header names worktree `...-DisambigFromSpacePoints-v1` and branch `phlex-extract/DisambigFromSpacePoints-v1`, but this extraction is `-r2`. Issue 10 cites a `phlex-tester` finding pinned in `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`. Neither file exists in this worktree or in the notes directory. | `git -C <wt> branch --show-current` gives `phlex-extract/DisambigFromSpacePoints-r2`. `git status` shows only 3 files. The notes directory holds 4 files. | Fix the header. Drop issue 10, or keep it as an untested observation (the quirk itself, an invalid-TPC collection hit colliding with the sentinel, is real in the code at alg .cxx L296-301). The orchestrator should check where this text came from. |
| M3 | minor | `MIGRATION_NOTES.md` (header, section 7) | The Phlex-era home is missing. The current template asks for a "Phlex-era home" row and a dependency table (`templates/MIGRATION_NOTES.md` L10, L64-69), and `dune-repo-map.md` gives `dune-fd-reco` or `dune-pd-hd` for `dunereco`, depending on which detectors' production jobs run the module. The notes name neither, although section 8 shows the module is used by both FD (`dunefd_disambigfromsp`) and ProtoDUNE-HD (`pdune_disambigfromsp`). The dependency table would be empty (the algorithm files include no other DUNE headers) but should say so. | `grep '#include "dune' <alg files>` finds only the module's own header | Add the home: probably `dune-fd-reco`, with `dune-pd-hd` as the alternative. The deciding question is whether it stays shared between FD and PD-HD. Add the (empty) DUNE dependency table. |
| M4 | minor | `CMakeLists.txt:2-25` (unchanged) | The algorithm is compiled into `HitFinderDUNE`. That library also links art (`art::Persistency_Common`, `art::Framework_Services_Registry`, `art::Utilities`), `larcore::Geometry_Geometry_service`, larsim services, etc., because it also contains other art-era code. So no art library was added, but a future Phlex plugin cannot link this algorithm without pulling in art. The notes say no CMake change is needed but do not record this as a transitional build item. | CMakeLists `LIB_LIBRARIES` | Record the item in notes section 6 or 7. A later pass should split the algorithm into its own SHARED target, linking only `lardataobj::RecoBase`, `larcorealg::Geometry`, `lardataalg::DetectorInfo`, and `messagefacility` until logging goes. |
| N1 | nit | `MIGRATION_NOTES.md:43` | Row 11 says module L161. `eventHits` is at L162. | module L162 | Fix the line reference. |
| N2 | nit | `DisambigFromSpacePointsAlg.cxx:66`, module `:186-189` | The pre-existing UB that notes issue 2 records now has a slightly different visible effect. In the original, an induction hit with `Plane == 2` overflowed `fNMissedBySpacePoints` into the member `fNMissedByNeighbors[0]`, which reaches the tree when `UseNeighbors: false`. Now the overflow lands in `stats.nMissedByNeighbors[0]`, which the module discards on that path. This is UB either way and cannot happen with DUNE geometries (induction planes are 0 and 1). | — | Optionally add one sentence to notes issue 2. |
| N3 | nit | `DisambigFromSpacePointsAlg.h:30-41, 48, 61` | The header uses unqualified `size_t` and includes only `<cstddef>`, which guarantees `std::size_t`. In practice it compiles everywhere LArSoft builds, and it matches the original style. | — | None needed; `std::size_t` if touched again. |

## Behaviour-preservation walk-through

Original to new (base = `5d619357:DisambigFromSpacePoints_module.cc`; alg = `DisambigFromSpacePointsAlg.cxx`):

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L46-49 typedefs | alg .h L29-32 | identical | still `namespace dune`; no other TU in the repo defines them |
| L53-66 Config | module L55-67 | identical | names, types, comments unchanged |
| L122-133 member inits | module L102-108 + `make_cfg` L91-100 | mechanical edit OK | each field maps to the right FHiCL name (`UseNeighbors`, `NumNeighbors`, `MaxDistance`, `MoveLeftovers`, `ExcludeTPCs`). Init order matches declaration order. |
| L134-137 NumNeighbors check | module L110-113 | identical | same exception, message, timing (constructor, before `produces`) |
| L142-158 products, geometry, tree | module L118-134 | identical | |
| L163-180 run/event, handles, FindOneP, hcol | module L139-156 | identical | |
| L183 assns | module L159 | identical | |
| L186-187 Ptr vector | module L162 `*hitsHandle` | mechanical edit OK | key == index |
| L189-190 FindManyP x2 | module L164-165 | identical | construction order unchanged |
| L192 detProp | module L167 | identical | still once per event, before the SP loop |
| L194-212 SP→TPC map | alg `mapSpacePointsToTPC` L288-312 | mechanical edit OK | `auto hits` copy became `auto const&`. Same loop, same `break`, same `spToTPC[i]` inserts. Dereference order same; for null Ptr see M1. |
| L214-219 locals + reserve | alg L327-332 | identical | `hitToNWires` is now `res.hitToNWires`, `hitToWire` is `res.hitToWire`, reserve before the first insert |
| L221-232 pass sequence + LogInfo | alg L334-348 | identical | text, category and order unchanged; still inside `produce`'s dynamic extent |
| L236-251 hitToWire output loop | module L193-208 | mechanical edit OK | `*(eventHits[key])` became `eventHits[key]` (same `HitCreator(Hit const&, WireID const&)` overload, lardata `HitCreator.h` L321). `spFromHit.at(eventHits[key].key())` became `spFromHit.at(key)`. The loop iterates the moved-out map, so order is the same. |
| L253-269 hitToNWires loop | module L210-226 | mechanical edit OK | same |
| L271-275 Fill, puts | module L228-232 | identical | still unconditional, same order |
| L278-363 runOnSpacePoints | alg L30-118 | mechanical edit OK | `hit.key()` became `i`. `fNHits`/`fNMissed*` became `stats.*` (int, same reset points). `sp.key()` became `sp.key`, `sp->position()` became `sp.spacePoint->position()`. `tpcBestWire`/`tpcScore` types unchanged, so tie-break order is unchanged. |
| L365-467 resolveUnassigned | alg L120-227 | mechanical edit OK | `fMaxDistance` became `cfg.maxDistance`, `fExcludeTPCs` became `cfg.excludeTPCs`, `nNeighbors` is passed `cfg.numNeighbors`. Floats, `<`/`>` comparisons and `result` map type are identical. |
| L469-493 assignFirstAllowedWire | alg L229-257 | identical (mechanical) | the marker comment between `if {}` and `else` is legal |
| L495-516 assignEveryAllowedWire | alg L259-282 | identical (mechanical) | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-174 | builds `hitsPerSpacePoint` with `&(*h)` | Values identical. For a null Ptr this is a null dereference later instead of an art exception (M1). |
| module L175-179 | builds `spacePointsPerHit` with `{sp.key(), &(*sp)}` for every hit | Eager `spFromHit.at(i)` and eager SP resolution (M1). Pointers are used only within `produce`. |
| module L183-189 | copies `stats` into branch buffers; `fNMissedByNeighbors` only if `useNeighbors` | Same values as the original write sites, including the never-written case. See N2 for the UB corner. |
| alg L322 `DisambigResult res{}` and return | value-initialises stats (zeros) and moves the maps out | Zeros are overwritten on every path the module reads. The move keeps the `unordered_map` node and bucket structure, so iteration order is preserved. |

## Validation plan

The plan in notes section 8 would catch the changes I looked for. It runs the FD (`repeat`, `spsolve`) and PD-HD (`repeat`) configurations, with overrides for `first`, drop, `UseNeighbors: false` and non-empty `ExcludeTPCs`, which covers every branch the extraction touched. It compares hits and both `Assns` unsorted, in produced order, which is right because the extraction claims identical order. It covers `hitstats` and correctly excludes `fNMissedByNeighbors` when `UseNeighbors: false`. Two small gaps: the plan does not compare log output (the three `LogInfo` calls moved), and it cannot exercise M1 (corrupt input only), which is acceptable. The unit-test idea is reasonable but has not been implemented, despite issue 10's reference (M2).

## Compile-risk review

Read against `<LArSoft checkout>` (larcorealg `b170a9c`, develop 2025-08-25; this checkout uses the `WireReadout`/`WireReadoutGeom` split, as dunereco v10_26 does) and canvas 3.17.0 source from the rattler cache. Whether these exactly match the release that `5d619357` builds against needs a build to confirm.

- `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) const` (L574), `Plane(PlaneID const&) const` (L151), `PlaneGeo::WireCoordinate(Point_t const&)` (L704), `WirePitch()` (L312), `DetectorPropertiesData::GetXTicksCoefficient(int,int) const` (L89), `SpacePoint::position()` returning `geo::Point_t`, and `HitCreator(Hit const&, WireID const&)`: all present and called through const references with const methods.
- Includes: `geo::kCollection`/`kInduction` and `WireID::InvalidID` come from `geo_types.h` (included); `PlaneGeo.h` is in the `.cxx`, and the transitional MessageLogger include is also in the `.cxx`, not in the header. `<algorithm>` covers `std::remove`, and `<cmath>` covers `fabs`/`abs(float)`.
- Declarations match definitions: `mapSpacePointsToTPC` and `disambiguateHits` have the same signatures and namespace; only the parameter names differ, which is fine. No functions are defined in the header. The anonymous-namespace helpers are defined before use.
- Module: `static make_cfg` is declared and defined; `fCfg` is const and initialised in order. No `this` capture or move-only copies. `SpacePointRef{sp.key(), &(*sp)}` is plain aggregate initialisation.
- Language: nothing beyond C++17. No constructs removed in C++20/23 in the header.
- Build: no CMake change needed for art_make, but a fresh configure is required to glob the new `.cxx`. The library mix is covered in M4.
- Overall compile risk: low.

## Guide conformance

- Separation checks: `ServiceHandle` appears only in the module (L123, L127, L167). `wireReadout` and `detProp` are passed explicitly. No helper receives the event or a handle. Nothing event-scoped is cached across events (only the `TTree` branch buffers, rewritten every event as before).
- Extraction checklist 1-5: (1) yes; (2) yes, all inputs are parameters; (3) yes, `DisambigResult` is returned by value (internal reference out-parameters are file-local); (4) yes, `make_cfg` in the module; (5) yes, 9 transitional logging items documented.
- Binding plan: plausible. The main transform is at event layer (the neighbour search and SP vote span the event). The monitoring `observe` is serial with the tree as a serialized resource. The plan names the real blockers: no persistable associations in Phlex, `HitCreator` living in an art-dependent library, and `DetectorPropertiesData` provisioning. `purity` gave no concurrency warnings, consistent with "unlimited". The plan has no Phlex-era home (M3).

## Notes accuracy

- Wrong worktree/branch in the header, and a reference to non-existent tester artefacts (M2).
- The claim that eager dereference "raises the same art exception" does not hold for null Ptrs (M1).
- Line drift in row 11 (N1).
- Phlex-era home and dependency table are missing (M3). The art-linked library is not recorded (M4).
- Everything else matches the code: the mechanical-edit list, the transitional table, the contract, issues 1-9, the CMake statement, and the binding blockers.
- No instructions addressed to an agent were found in the source, FHiCL comments or notes.
