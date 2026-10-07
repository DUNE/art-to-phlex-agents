# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 0 major, 4 minor, 2 nit |
| Working tree and base | `<worktree-r8>` (branch `phlex-extract/DisambigFromSpacePoints-r8`) against `5d619357` |
| Notes reviewed | `runs/dunereco-DisambigFromSpacePoints-r8/MIGRATION_NOTES.md`, `contract.*.txt`, `extraction.patch` |
| Verifier / model / date | phlex-verifier (Claude Code subagent), Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The change splits the module into a thin art boundary and a framework-free
  `DisambigFromSpacePointsAlg.{h,cxx}` (free functions, file-local helpers). Purity and
  contract checks are clean; `extraction.patch` is byte-identical to `git diff 5d619357`.
- **One behaviour change, not documented:** the per-TPC vote in `runOnSpacePoints` now uses
  `>=` where the original used `>` (alg `.cxx:98` vs base `:343`). On a tie, the new code
  picks the last TPC in `unordered_map` iteration order; the original picked the first. This
  changes the output hit `WireID`s and the neighbour-pass input. The notes call this block
  "moved verbatim". Blocker.
- Everything else matches statement for statement: same `unordered_map` object, `reserve`
  and insertion sequence (output order preserved), same counter write paths including the
  stale `fNMissedByNeighbors` when `UseNeighbors: false`, same log text and order.
- Before a build: restore `>` at alg `.cxx:98`. Then fix the notes (stale `-v1` paths, a test
  file that does not exist, missing Phlex-era home) and add a tie case to the validation plan.

## Original module in brief

Written before reading the new code or the notes. `DisambigFromSpacePoints` is an
`EDProducer` that reads a hit collection and a SpacePoint collection. It maps each induction
SpacePoint to a TPC through its first collection hit. Then it assigns each hit to a wire
segment: a collection hit gets its first wire. An induction hit gets the segment within one
wire pitch of its SpacePoints, voting per TPC; a tie goes to the first TPC in iteration order
because the test is strict `>`. Optionally, it resolves leftovers from the distance-weighted
scores of the N nearest resolved hits. Then it places the remaining hits on every allowed
segment ("repeat"), on the first allowed segment ("first"), or drops them. It writes a new
`std::vector<recob::Hit>` (in `unordered_map` iteration order), a hit-wire `Assns` through
`HitCollectionCreator`, and a copied `Assns<Hit,SpacePoint>`. With `MonitoringPlots`, it
fills a `hitstats` TTree from member counters. `fNMissedByNeighbors` is written only when
`UseNeighbors` is true. Contract: 8 FHiCL parameters with no defaults; `declare_products(...,
"", true, false)` plus one `produces<Assns>`; no `consumes`.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (all MessageLogger) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:<module> --after <module>` | contract unchanged (13 items); `contract.before.txt` == `contract.after.txt` |
| Algorithm inventory | `art_inventory.py report <alg files>` | only `messagefacility` include and 8 `mf::Log*` calls (marked transitional) |
| Module inventory | `art_inventory.py report <module>` | framework constructs concentrated in module; member writes in `produce` only (`fRun`, `fEvent`, counters, `fTree`) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -rn` on new files | 9 markers at `.cxx` L16, 49, 145, 176, 241, 254, 335, 341, 347; each covers the next line, matching the 9 rows of notes section 6 (L17, 50, 146, 177, 242, 255, 336, 342, 348). Both directions match; reasons hold. |
| Patch consistency | `diff <(git diff 5d619357) extraction.patch` | identical |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | **blocker** | `DisambigFromSpacePointsAlg.cxx:98` | Tie-break in the per-TPC SpacePoint vote changed from `>` to `>=`. When two TPCs have equal scores, the new code picks the last one in `tpcScore` iteration order, the original the first. This changes the output hit's `WireID`, which `indHits[cryo][TPC]` bucket the hit joins (neighbour pass input for other hits), and so the produced `std::vector<recob::Hit>` and both `Assns`. Ties are an ordinary case for wrapped induction channels with SpacePoints on both APA sides. Not in the notes; section 4 lists `runOnSpacePoints` as "moved verbatim", and pre-existing issue 5 describes the tie-break as unchanged. | base `DisambigFromSpacePoints_module.cc:343` `if (score.second > maxScore)`; new `.cxx:98` `if (score.second >= maxScore)` | Restore `>`. Add a two-TPC tie case to the unit test and validation plan. |
| 2 | minor | `MIGRATION_NOTES.md:172` | Pre-existing issue 10 cites `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md` "found by phlex-tester". Neither file exists in the worktree or the notes directory. Stale text from another round. | `find <wt> -name '*DisambigFromSpacePoints*'` gives only the module and the two Alg files; no `TESTS.md` anywhere | Remove the reference, or keep the quirk as an unconfirmed observation. |
| 3 | minor | `MIGRATION_NOTES.md:7` | Working tree and branch given as `...-v1` / `phlex-extract/DisambigFromSpacePoints-v1`; the reviewed tree is `...-r8`, branch `phlex-extract/DisambigFromSpacePoints-r8`. | `git branch --show-current` | Correct the header. |
| 4 | minor | `MIGRATION_NOTES.md` section 7 | Binding plan names no Phlex-era home. `dune-repo-map.md` maps `dunereco` to `dune-fd-reco` (or protoDUNE-specific repos). The notes say FD (`hitfd`) and ProtoDUNE-HD (`hitpdune`) both run it, so the plan should give candidates and the deciding question. The DUNE-include dependency table is trivially empty (`grep '#include "dune'` finds only the module's own header); say so. | section 7 text; `references/dune-repo-map.md:38` | Add "home: `dune-fd-reco`, unless ProtoDUNE-HD needs it outside FD; deciding question: which production FHiCL runs it". |
| 5 | minor | `DisambigFromSpacePoints_module.cc:175-179` | Documented deviation: every SpacePoint `Ptr` is dereferenced eagerly, and `spFromHit.at(i)` is now called for every hit, collection hits too. With a null or unresolvable `Ptr`, `*sp` dereferences a null pointer (canvas `Ptr::operator*` returns `*get()`, `get()` gives `nullptr` when `isNull`); the original reached `sp->` only for matching TPCs. With an invalid `FindManyP` (association product missing), `at()` now throws before the first `LogInfo`, not after. Values on normal input are identical. Needs unusual input. | canvas v3_17_01 `Ptr.h:130-152`, `FindManyP.h:347-351` | Accept as documented, or resolve lazily. Mention the log-order change in notes section 4. |
| 6 | nit | `MIGRATION_NOTES.md:43` | Inventory row 11 cites module L161 for `eventHits`; it is L162. | module L162 | Update. |
| 7 | nit | `CMakeLists.txt` (unchanged) | The algorithm `.cxx` is globbed into `HitFinderDUNE`, which already links art, canvas, FHiCL and MessageLogger for the other files. Nothing was added, but a future Phlex plugin linking this library inherits art. | `LIB_LIBRARIES` list | For binding, move the algorithm to its own library. Note this in the binding plan. |

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| ctor L122-L159 (config, NumNeighbors check, declare_products, produces, geometry, TTree) | module L102-L135, `make_cfg` L91-L100 | mechanical edit OK | each FHiCL field to the same-typed `cfg` field (`bool`, `size_t`, `float`, `string`, `vector<size_t>`); no same-type mix-up; member init order matches declaration order |
| produce L163-L192 (run/event, handles, FindOneP, hcol, assns, FindManyP x2, detProp) | module L139-L167 | identical | `fill_ptr_vector` replaced by `*hitsHandle`; keys equal indices |
| produce L193-L212 (spToTPC) | alg `mapSpacePointsToTPC` L288-L312 | mechanical edit OK | `auto hits` copy becomes `auto const&`; `h->` on `Hit const*` |
| produce L214-L219 (locals, reserve) | alg `disambiguateHits` L322-L332 | identical | same container types, `reserve(eventHits.size())` before first insert |
| produce L221-L232 (passes, LogInfo, leftover switch) | alg L334-L348 | identical | same text, same order |
| runOnSpacePoints L287-L336 | alg L41-L91 | mechanical edit OK | `hit.key()` becomes `i`; `sp.key()`/`sp->` become `sp.key`/`sp.spacePoint->` |
| runOnSpacePoints L337-L348 (tie-break) | alg L92-L103 | **CHANGED** | `>` became `>=` (finding 1) |
| runOnSpacePoints L349-L362 | alg L104-L117 | identical | |
| resolveUnassigned L365-L467 | alg L120-L227 | mechanical edit OK | `nNeighbors` = `cfg.numNeighbors` as before; float math, casts and comparisons unchanged; `result` map, erase loop and `insert` unchanged |
| assignFirstAllowedWire L469-L493 | alg L229-L257 | mechanical edit OK | |
| assignEveryAllowedWire L495-L516 | alg L259-L282 | mechanical edit OK | |
| produce L234-L269 (output loops) | module L191-L226 | mechanical edit OK | `*(eventHits[key])` becomes `eventHits[key]`, same `HitCreator(Hit const&, WireID const&)` overload; `spFromHit.at(eventHits[key].key())` becomes `.at(key)`, equal; iteration over `result.hitToWire` keeps order (moved-out `unordered_map`) |
| produce L271-L275 (Fill, put_into, put) | module L228-L232 | identical | |
| counters written in helpers | alg `DisambigStats`, module L183-L189 | mechanical edit OK | `fNHits`, `fNMissedBySpacePoints` copied every event (original wrote them every event); `fNMissedByNeighbors` only when `useNeighbors`, so stale/indeterminate values are preserved |
| typedefs L46-L49 | alg header L29-L32 | identical | no clashing typedefs elsewhere in `dunereco/` |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-L174 | resolves `hitsFromSp` into `Hit const*` lists | same dereference set and order as the original mapping loop; none |
| module L175-L179 | resolves `spFromHit` into `SpacePointRef{key, &*sp}` for every hit | finding 5 (error paths only); `key_type` is `std::size_t` (canvas `Ptr.h:78`), no narrowing |
| module L183-L189 | copies `DisambigStats` into branch members | matches original write paths. Side note: an out-of-bounds `nMissedBySpacePoints[2]` write (notes issue 2, UB) used to spill into `fNMissedByNeighbors[0]`, which reached the tree when `UseNeighbors: false`; now the spill stays in `stats`. UB either way |
| alg L322 `DisambigResult res{}`, L350 `return res` | value-initialised result, returned by NRVO or move | moving `unordered_map` keeps nodes and order; none |
| `DisambigStats` `{}` initialisers | zero-initialise counters | not visible: module only copies `nMissedByNeighbors` when the algorithm wrote it |

## Validation plan

Mostly sound. It runs FD and ProtoDUNE-HD workflows, overrides `MoveLeftovers` to
`first`/`drop`, `UseNeighbors: false` and a non-empty `ExcludeTPCs`, compares products
unsorted in produced order, and includes the `hitstats` tree. It would probably catch
finding 1 on a real FD sample, but only if ties occur in the chosen events. Add an explicit
unit test with two TPCs scoring equally for one hit, which pins the first-in-iteration-order
choice. The claim that comparisons should run unsorted is correct for this extraction, since
the `unordered_map` operations are unchanged.

## Compile-risk review

Checked by reading:

- Identifiers: all former members map to `cfg.*`, `wireReadout`, `stats.*`; typedefs visible
  through the header; `using dune::...` inside the anonymous namespace resolves.
- Includes: header has `WireReadoutGeom.h`, `geo_types.h`, `DetectorPropertiesData.h`,
  `Hit.h`, `SpacePoint.h`, std headers; `.cxx` adds `PlaneGeo.h`, `<algorithm>`, `<cmath>`;
  MessageLogger only in the `.cxx`. Module includes the new header.
- Declarations match definitions (`mapSpacePointsToTPC`, `disambiguateHits`); the single call
  site (module L181) matches. No functions defined in headers. Aggregates and `std::array`
  are C++17-clean and fine under C++23.
- APIs against LArSoft checkout (tags `LARSOFT_SUITE_v10_20_00`; dunereco base is
  v10_26_00d02, so a newer LArSoft is likely the real target): `WireReadoutGeom::ChannelToWire`
  (L574), `Plane(PlaneID const&)` (L151; the braced `{0,0,plane}` call is unambiguous since
  the other overload takes two arguments), `PlaneGeo::WireCoordinate`, `WirePitch`,
  `DetectorPropertiesData::GetXTicksCoefficient(int,int)`, `HitCreator(Hit const&, WireID
  const&)` (L321). All calls are the same as the original's, so version skew is low risk.
  canvas v3_17_01 from CVMFS for `Ptr` and `FindManyP`.
- Build: `art_make` globs the new `.cxx` into `HitFinderDUNE`, whose `LIB_LIBRARIES` already
  covers every dependency; the plugin links `HitFinderDUNE`. A fresh CMake configure is needed.
- Needs build to confirm: nothing specific; residual risk is low.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `wireReadout`
  and `detProp` passed explicitly; no helper receives the event or a handle; nothing
  event-scoped kept across events (the `SpacePointRef` pointers die with `produce`).
- Extraction checklist 1 to 5: met (1 framework-free description, 2 explicit inputs, 3
  outputs returned in `DisambigResult`, 4 configuration via `make_cfg`, 5 transitional
  logging documented).
- Binding plan: node shapes plausible (event-layer `transform`, `observe` for the tree marked
  `serial` with the tree as a serialized resource; inputs const; re-entrant algorithm
  consistent with no purity warnings). Blockers named (persistable associations,
  `HitCreator` dependency, conditions). Missing the Phlex-era home (finding 4) and the
  library split (finding 7).

## Notes accuracy

- Section 4 "moved verbatim" for `runOnSpacePoints` and issue 5 are wrong given the `>=`
  change (finding 1, which this hides; hence blocker, not minor).
- Header paths say `-v1` (finding 3); issue 10 cites nonexistent test files (finding 2);
  row 11 line number off by one (finding 6).
- Issue 2's implication that the out-of-bounds spill behaves the same is not quite true when
  `UseNeighbors: false` (walk-through side note); UB either way.
- No instructions addressed to agents found in source, comments, FHiCL or notes.
