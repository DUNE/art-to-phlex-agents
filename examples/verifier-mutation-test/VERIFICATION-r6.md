# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 0 blocker, 1 major, 4 minor, 2 nit |
| Working tree and base | `<worktree-r6>` (branch `phlex-extract/DisambigFromSpacePoints-r6`, uncommitted) against `5d619357` |
| Notes reviewed | `runs/dunereco-DisambigFromSpacePoints-r6/MIGRATION_NOTES.md` |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The algorithm (space point vote, neighbour pass, leftover handling, space point to TPC map) moved verbatim into `DisambigFromSpacePointsAlg.{h,cxx}` with mechanical edits only. Every statement of the original callbacks and helpers is accounted for, and the edits are correct.
- Data products should be unchanged. The contract is identical (13 items), the single `hitToWire` `unordered_map` gets the same `reserve` and the same insertion sequence and is moved (not copied, not rebuilt) out of the algorithm, so output hit and association order is preserved.
- One major finding: the module now writes `fNMissedByNeighbors` every event (module L186), including when `UseNeighbors: false`, where the original never wrote it. The notes state the opposite, and the validation plan excludes that branch from comparison, so nothing would catch it. The fix is one `if`.
- Purity is clean apart from 9 documented MessageLogger lines. No compile risks found by reading. LArSoft and canvas APIs used were checked against headers.
- Before a build: fix or document finding 1, correct the notes (wrong worktree/branch, a test file that does not exist), add the Phlex-era home to the binding plan.

## Original module in brief

Written before reading the new code or the notes.

`DisambigFromSpacePoints` is a legacy `art::EDProducer`. Per event it reads hits (`HitModuleLabel`) and space points (`SpModuleLabel`), the hit-wire `FindOneP` and both directions of the hit-space point association. It maps each space point to a TPC using its first collection hit, then assigns each induction hit to the wire segment (of those its channel maps to) that lies within one wire pitch of its space points, voting per TPC. Hits not resolved this way are optionally resolved by a distance score to up to `NumNeighbors` already-resolved hits per candidate segment, and leftovers are put on every allowed segment (`repeat`), the first allowed one (`first`) or dropped. It writes a new hit collection via `HitCollectionCreator` (with hit-wire associations if the input had them) and a copy of the hit-space point associations, in `unordered_map` iteration order. With `MonitoringPlots`, it fills a `hitstats` TTree from member counters; `fNMissedByNeighbors` is only written by `resolveUnassigned`, so with `UseNeighbors: false` it is never written (indeterminate). The constructor throws `cet::exception` if `NumNeighbors < 1`. Defaults in `hitfindermodules_dune.fcl`: `UseNeighbors: true`, `MonitoringPlots: false`, `MoveLeftovers: "first"` (FD and PD prologs override to `"repeat"`).

## Automated checks

Run from the worktree root with `S=$KIT/skills/art-phlex-extract/scripts`.

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (all MessageLogger, `.cxx` L17, 50, 146, 177, 242, 255, 336, 342, 348) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | contract unchanged (13 items); `contract.before.txt` and `contract.after.txt` identical |
| Algorithm inventory | `art_inventory.py report <alg .h> <alg .cxx>` | header: no framework constructs; `.cxx`: only the MessageLogger include and 8 `mf::Log*` calls |
| Module inventory | `art_inventory.py report DisambigFromSpacePoints_module.cc` | all framework constructs in the module; member state written in `produce` only: `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` (L184-L186) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -rn PHLEX-TRANSITIONAL <alg files>` | 9 markers, all in `.cxx`, all logging; each matches a row of notes section 6 and vice versa. Reason holds (logging only). |
| Extraction patch | `diff extraction.patch <(git diff 5d619357)` (ignoring `index` lines) | identical |
| Scope | `git status --short`, `git diff --stat 5d619357` | 3 files, all in `dunereco/HitFinderDUNE/`: module modified, `DisambigFromSpacePointsAlg.{h,cxx}` added (intent-to-add). No `CMakeLists.txt` change (not needed, see compile review). |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | major | `DisambigFromSpacePoints_module.cc:186` (and comment at L183); `MIGRATION_NOTES.md` L118-L119, L163, L235 | `fNMissedByNeighbors` is copied from `result.stats` every event, unconditionally. With `UseNeighbors: false`, `DisambigStats` is value-initialised (`res{}`, alg `.cxx` L322; `nMissedByNeighbors{}` in `.h` L56), so the `hitstats` branch now records `{0,0}` where the original recorded whatever indeterminate value the member held (it was never written on that path). This is an undocumented change to a TTree branch. The notes say the opposite ("into `fNMissedByNeighbors` only when `UseNeighbors` is true (the only path where the original wrote it)" and "Behaviour kept"), the module comment at L183 says "written where the original algorithm wrote them", and the validation plan excludes this branch when `UseNeighbors: false`, so the change is hidden from every check. Reachable only with `MonitoringPlots: true` and `UseNeighbors: false`, which no prolog in this repository sets (dunesw overrides not read, out of scope). | original L224-L228 (only call site of `resolveUnassigned`, the only writer, L374-L375, L455); new module L184-L186 has no `if` | Guard L186 with `if (fCfg.useNeighbors)`, which restores the original write site and matches the notes. Or keep the zeroing, list it as an intentional deviation in section 4, fix the L183 comment and the notes. |
| 2 | minor | `DisambigFromSpacePoints_module.cc:173`, `:178` | Eager resolution at the boundary changes some error paths. (a) `&(*sp)` / `&(*h)` use `Ptr::operator*`, which is `*get()`, and `get()` returns `nullptr` for a null `Ptr` (canvas v3_17_01 `Ptr.h` L131-L141). The original used `operator->`, which goes through `parentProduct_()` and throws an `art::Exception`. A null `Ptr` in the association would now be undefined behaviour instead of an exception. (b) Space points of collection hits, and of induction hits that never reach the wire-distance test, are now resolved, which the original never did. (c) `spFromHit.at(i)` is now called for every hit; if the association is invalid and no hit reaches the original call sites (for example every channel maps to no wires), the new code throws where the original did not. All need corrupt or unusual input. The notes document (b) but claim the failure is the same `art::Exception` category, which is not true for (a). | canvas `Ptr.h` `operator*` / `get` / `operator->`; `FindManyP::at` calls `throwIfInvalid()` (`FindManyP.h` L347-L350); original L201, L210, L307, L317, L328, L246 | Use `sp.operator->()` (or `sp.get()` plus an explicit throw on null) to keep the throwing path, or document (a) and (c) next to (b) in section 4. |
| 3 | minor | `MIGRATION_NOTES.md` L7, L172 | Notes do not describe this pass. The header gives worktree `...-DisambigFromSpacePoints-v1` and branch `phlex-extract/DisambigFromSpacePoints-v1`; the actual tree is `-r6` on branch `phlex-extract/DisambigFromSpacePoints-r6`. Pre-existing issue 10 cites a `phlex-tester` result pinned in `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`; neither exists in the worktree or the notes directory. | `git -C <wt> branch --show-current`; `ls dunereco/HitFinderDUNE \| grep -i test` (empty) | Correct the header; remove issue 10 or mark it as from another run until the test exists here. |
| 4 | minor | `MIGRATION_NOTES.md` section 7 | The binding plan does not name a Phlex-era home. Per `dune-repo-map.md`, `dunereco` code goes to `dune-fd-reco`, or to `dune-pd-hd`/`dune-pd-vd`/`dune-pd-sp` when only one protoDUNE uses it, decided by which production jobs run it. This module is used by the FD prolog (`dunefd_disambigfromsp`) and the PD prolog (`pdune_disambigfromsp`, used in `WireFilter/run_wire_filter.fcl` and, by file name, in ProtoDUNE-SP and -HD reco FHiCL in dunesw), so the candidate is `dune-fd-reco` with the deciding question "is it shared by FD and protoDUNE production?". The dependency table is trivially complete: the algorithm files include no DUNE art-era headers other than their own. | `grep '#include "dune' <alg files>` returns only the own header | Add a home row: `dune-fd-reco` (candidate), deciding question as above. |
| 5 | minor | `dunereco/HitFinderDUNE/CMakeLists.txt` (unchanged); notes section 7 | The algorithm is compiled into the existing `HitFinderDUNE` library, whose `LIB_LIBRARIES` include art persistency, art service registry and larsim BackTracker/ParticleInventory service libraries (needed by the other sources in that directory). A future Phlex plugin linking `HitFinderDUNE` would pull in art. Fine for pass 1 (the module must still build), but the binding plan should say the algorithm needs its own framework-free shared-library target before binding. | `CMakeLists.txt` `art_make(... LIBRARY_NAME HitFinderDUNE LIB_LIBRARIES ... art::Persistency_Common ... art::Framework_Services_Registry ...)` | Add a binding-plan blocker: split `DisambigFromSpacePointsAlg` into its own `SHARED` target linking only `larcorealg::Geometry`, `lardataalg::DetectorInfo`, `lardataobj::RecoBase` (and MessageLogger while transitional). |
| 6 | nit | `MIGRATION_NOTES.md` sections 2, 3, 9 | Several module line references are off by one to three lines (for example L161 for `eventHits` is L162; stats copy "L183-L189" is L184-L186; `emplace_back` "L200, L217" are L197, L214; `put_into`/`put` "L231, L232" are L228, L229; `DEFINE_ART_MODULE` "L235" is L232). | module file as it stands | Refresh line numbers. |
| 7 | nit | `DisambigFromSpacePointsAlg.h:29-32` | The `plane_keymap` typedefs are now public API in namespace `dune` although only the `.cxx` uses them. No collision found in `dunereco`, and identical typedef redeclarations would be legal anyway. | `grep -rn plane_keymap dunereco` (only these files) | Optional: move them into the `.cxx` anonymous namespace. |

No instructions addressed to an agent were found in the source, comments, FHiCL or notes.

## Behaviour-preservation walk-through

Original to new (original line numbers at `5d619357`; "alg" is `DisambigFromSpacePointsAlg.cxx`, "mod" is the new module):

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L46-L49 typedefs | `.h` L29-L32 | identical | |
| L53-L66 `Config` | mod L55-L67 | identical | names, types, comments unchanged; contract tool agrees |
| L104-L119 members | mod L77-L88 | mechanical edit OK | five config members folded into `const DisambigFromSpacePointsCfg fCfg`; branch buffers kept as members with the same types, so branch addresses and leaf lists are unchanged |
| L122-L133 ctor init list | mod L102-L108, `make_cfg` L91-L100 | mechanical edit OK | each FHiCL value mapped to the right field (`UseNeighbors`→`useNeighbors`, `NumNeighbors`→`numNeighbors`, `MaxDistance`→`maxDistance`, `MoveLeftovers`→`moveLeftovers`, `ExcludeTPCs`→`excludeTPCs`); no same-type mix-up; init order matches declaration order |
| L134-L137 `NumNeighbors < 1` throw | mod L110-L113 | identical | same type and text |
| L142-L158 products, geometry, TTree | mod L118-L134 | identical | |
| L163-L167 run/event, handles | mod L139-L143 | identical | |
| L172-L183 `FindOneP`, `hcol`, `assns` | mod L148-L159 | identical | |
| L186-L187 `fill_ptr_vector` | mod L162 `*hitsHandle` | mechanical edit OK | `fill_ptr_vector` builds `Ptr(handle, i)`, key = index; all `hit.key()` uses become `i` or `key` |
| L189-L190 `FindManyP` x2 | mod L164-L165 | identical | |
| L192 `detProp` | mod L167 | identical | once per event, as before |
| L194-L212 space point to TPC map | alg L288-L312 `mapSpacePointsToTPC`, fed by mod L170-L174 | mechanical edit OK | `auto hits = hitsFromSp.at(i)` copy → `auto const& hits` reference; same loops, same `break`, same `continue`, same sentinel. Dereference order of the hit `Ptr`s is unchanged in substance (see finding 2 for null `Ptr`) |
| L214-L219 locals, `reserve` | alg L327-L332 | mechanical edit OK | `hitToWire`/`hitToNWires` are references into `res`; `reserve(eventHits.size())` before the first insert, as before |
| L221-L222 `runOnSpacePoints` + `LogInfo` | alg L334-L336 | identical | `LogInfo` text unchanged, still after the step's warnings |
| L224-L228 `if (fUseNeighbors)` neighbour pass + `LogInfo` | alg L338-L343 | identical | `fNumNeighbors` passed as `cfg.numNeighbors` |
| L230-L232 leftover switch | alg L345-L348 | identical | string compares unchanged |
| L234-L251 `hitToWire` output loop | mod L188-L205 | mechanical edit OK | iterates `result.hitToWire`, which is the same map object moved out (NRVO or move; libstdc++ move keeps buckets and node list). `*(eventHits[key])` → `eventHits[key]`, the same `recob::Hit const&` passed to `HitCreator(recob::Hit const&, geo::WireID const&)` (lardata `HitCreator.h` L321). `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)`, same index, same `art::Ptr`s into the output `Assns` |
| L253-L269 `hitToNWires` output loop | mod L207-L223 | mechanical edit OK | as above |
| L271-L275 Fill, `put_into`, `put` | mod L225-L229 | identical | unconditional on every path |
| L287-L289 counter resets | alg L41-L43 | mechanical edit OK | `stats.*` |
| L291-L360 `runOnSpacePoints` loop | alg L45-L115 | mechanical edit OK | same loop bound, same `continue` on empty `cwids` (warning kept), `hit.key()`→`i`, `sp.key()`→`sp.key`, `sp->position()`→`sp.spacePoint->position()`; `max_dw`, `float` types, `<` comparisons, `tpcBestWire`/`tpcScore` local `unordered_map`s with the same operations, tie-break by iteration order unchanged; `indHits[cryo][bestId.TPC][plane].push_back` same |
| L362 return | alg L117 | identical | |
| L374-L456 `resolveUnassigned` loop | alg L132-L216 | mechanical edit OK | `fMaxDistance`→`cfg.maxDistance`, `fExcludeTPCs`→`cfg.excludeTPCs`, geometry by reference; `dwMax`/`ddMax` from plane `{0,0,plane}` and `GetXTicksCoefficient(0,0)` kept (pre-existing issue 3); `distBuff`, `maxd2` scan, `score += 1./(1.+d)` (double into float) unchanged; `bestId.isValid` gate unchanged |
| L458-L466 erase, insert, return | alg L218-L226 | identical | `result` iteration order drives `assignments.insert` order into `hitToWire`, unchanged |
| L469-L493 `assignFirstAllowedWire` | alg L229-L257 | mechanical edit OK | warnings kept |
| L495-L516 `assignEveryAllowedWire` | alg L259-L282 | mechanical edit OK | silent skip kept |
| L518 `DEFINE_ART_MODULE` | mod L232 | identical | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| mod L91-L100 `make_cfg` | copies validated FHiCL values into the config struct once | none |
| mod L170-L174 | resolves `hitsFromSp` into `vector<vector<Hit const*>>` | same dereferences the original made, earlier; null `Ptr` now UB instead of a throw (finding 2) |
| mod L175-L179 | resolves `spFromHit` into `vector<vector<SpacePointRef>>` for every hit | resolves more space point `Ptr`s and calls `at()` for every hit; error paths only (finding 2) |
| mod L184-L185 | copies `nHits`, `nMissedBySpacePoints` into branch members | same values the original wrote every event; OK |
| mod L186 | copies `nMissedByNeighbors` into branch members | **changes `hitstats` when `UseNeighbors: false`** (finding 1) |
| alg L322 `DisambigResult res{}` | value-initialises the result | source of the zeros in finding 1; otherwise none |
| alg L325 `mapSpacePointsToTPC` returns by value | | `spToTPC` used only through `find`, iteration order irrelevant |

Other items from the checklist: no random draws; no early return in `produce`; products put under the same conditions; service data fetched once per event as before; no event pointers kept beyond `produce` (`SpacePointRef` and `Hit const*` vectors are locals); `std::array` indexing by `plane` has the same unchecked out-of-bounds behaviour as the C arrays (pre-existing issue 2).

## Validation plan

Mostly good: it covers `repeat`, `first` and `drop`, `UseNeighbors: false`, non-empty `ExcludeTPCs`, FD and ProtoDUNE-HD, compares hits and both association pair lists unsorted (correct, since identical order is claimed), and includes one `MonitoringPlots: true` run. Gaps: it excludes `fNMissedByNeighbors` when `UseNeighbors: false` on the grounds that the module preserves the original behaviour, which is exactly where the code changed (finding 1); after the fix the exclusion is right, since the original value is indeterminate. It does not ask for the `MonitoringPlots: true` run to be combined with each override, which is needed for the `hitstats` comparison to cover the `UseNeighbors: false` path. Log-text comparison is not mentioned; the three `LogInfo` lines moved, so a quick diff of `DisambigFromSpacePoints` log lines would confirm order. The unit-test item is an idea only; issue 10 refers to a test that does not exist here (finding 3).

## Compile-risk review

Checked by reading, no compiler run:

- Every identifier in moved code resolves: former members are `cfg.*`, `stats.*` or parameters; typedefs come from the header; `geo::kCollection`, `geo::kInduction`, `geo::WireID::InvalidID` from `geo_types.h`; `std::fabs`, `std::abs(float)` from `<cmath>`; `std::remove` from `<algorithm>`.
- APIs against the local LArSoft checkout (`<LArSoft checkout>`, larcorealg `b170a9c` 2025-08-25, lardata `bd7f63a` 2026-01-06; not confirmed to be the exact version dunereco builds against): `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) const` returns `std::vector<WireID>` (L574); `Plane(PlaneID const&) const` (L151), and the 3-element brace init can only bind `PlaneID` (the other overload takes `TPCID, View_t`); `PlaneGeo::WireCoordinate(Point_t const&) const` and `WirePitch() const` (L704, L312); `DetectorPropertiesData::GetXTicksCoefficient(int, int) const` (L89, `size_t`→`int` as before); `HitCreator(recob::Hit const&, geo::WireID const&)` (L321). canvas v3_17_01 from CVMFS for `Ptr` and `FindManyP`.
- Declarations match definitions (`mapSpacePointsToTPC`, `disambiguateHits`: same parameter types, namespace `dune`, parameter names differ, which is legal). No functions defined in the header. File-local helpers in an anonymous namespace; no name clash in `dunereco`.
- `const&` parameters are used only with const methods (`ChannelToWire`, `Plane`, `GetXTicksCoefficient`, `Hit` accessors). `allIndHits` and `assignments` remain non-const where `operator[]` and `insert` are used.
- `SpacePointRef{sp.key(), &(*sp)}`: aggregate init, `Ptr::key()` is `std::size_t`, `&*sp` is `recob::SpacePoint const*`. `DisambigResult res{}` and `return res;` fine (all members movable).
- Includes: the public header has only LArSoft data/geometry headers; the transitional MessageLogger include is in the `.cxx`, not the header. Include style matches the repository (`dunereco/HitFinderDUNE/...`).
- Build files: `art_make(BASENAME_ONLY LIBRARY_NAME HitFinderDUNE ...)` globs `*.cxx`, so the new file joins `HitFinderDUNE`, which already links `larcorealg::Geometry`, `lardataalg::DetectorInfo`, `lardataobj::RecoBase`, `messagefacility::MF_MessageLogger`; the plugin links `HitFinderDUNE`. A fresh CMake configure is needed for the glob to pick up the new file. No art/FHiCL library was added for the algorithm (but see finding 5).
- No C++20/23 removals in the header.

Needs build to confirm: nothing specific; residual risk is low.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `WireReadoutGeom` and `DetectorPropertiesData` passed explicitly; no helper takes the event or a handle; nothing event-scoped cached across events (`fRun`, `fEvent` and branch buffers are rewritten per event, as before). Pass.
- Extraction checklist 1 to 5: (1) describable without callbacks, yes; (2) all inputs in the signature, yes; (3) outputs returned in `DisambigResult`, yes (file-local helpers keep reference out-parameters internally to thread one map, acceptable and documented); (4) configuration collected in the module, yes; (5) remaining framework use documented as transitional, yes (9 logging items, table matches markers both ways). Pass.
- Binding plan: node shapes plausible (association adapter + `transform` returning hits and stats, `observe` for the tree, `serial` with the tree as a serialized resource, `MonitoringPlots` as a registration-time switch rather than a predicate). Blockers named: no persistable associations, `HitCreator` in an art-dependent library, conditions access. Algorithm inputs are const. Missing: the Phlex-era home (finding 4) and the need for a separate framework-free library target (finding 5).

## Notes accuracy

- Section 3 L118-L119 and section 4 issue 1: claim `fNMissedByNeighbors` is written only when `UseNeighbors`; the code writes it unconditionally (finding 1, hides a behaviour change).
- Section 4 "Intentional deviations": says the eager dereference throws the same `art::Exception` category; true for an unavailable product, not for a null `Ptr` (finding 2).
- Header L7: worktree and branch name `-v1`, actual `-r6` (finding 3).
- Section 4 issue 10: cites `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`, which do not exist here (finding 3).
- Line references off by a few lines in sections 2, 3, 9 (finding 6).
- All other claims checked (contract, transitional table, verbatim moves, mechanical edits, `reserve` and map threading, CMake, API signatures) match the code.
