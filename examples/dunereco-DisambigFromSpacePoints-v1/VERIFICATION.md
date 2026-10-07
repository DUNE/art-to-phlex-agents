# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **PASS WITH NOTES** |
| Findings | 0 blocker, 0 major, 2 minor, 4 nit |
| Working tree and base | `<worktree>` against `5d619357` (`Merge tag 'v10_26_00d02' into develop`) |
| Notes reviewed | `examples/dunereco-DisambigFromSpacePoints-v1/MIGRATION_NOTES.md`, `contract.before.txt`, `contract.after.txt`, `extraction.patch` (identical to `git diff 5d619357` of the worktree) |
| Verifier / model / date | phlex-verifier (Claude Code subagent), Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The module now reads config, fetches products, flattens both hit/space point association
  directions into plain containers, calls `dune::disambiguateHits`, and publishes the
  results. The four former private methods and the space point to TPC mapping moved into
  `DisambigFromSpacePointsAlg.{h,cxx}` with only mechanical edits.
- I compared every moved statement with the original. The computation, the product contents,
  the output order and the `hitstats` tree contents are preserved for ordinary input.
- **Output order claim: confirmed.** `hitToWire` is the same `std::unordered_map<size_t,
  geo::WireID>`, reserved to the same size before the first insert, with the same keys
  (`Ptr` key == index), filled by the same sequence of `operator[]` and `insert` calls. It
  leaves `disambiguateHits` by NRVO or implicit move, and both keep the node and bucket
  structure. `hitToNWires`, `tpcScore` and the local `result` map are also unchanged.
  Output hits, hit-wire `Assns` and hit-space point `Assns` therefore come out in the same
  order with the same standard library.
- **Eager space point dereference: acceptable, recommend that the human accepts it.** Values
  are identical. It can only throw where the original did not if an association points into
  a space point product that cannot be read, while `getValidHandle` for the same label has
  already succeeded. Making it lazy would need a callback into the algorithm (a framework
  leak). Using `spHandle` instead would change behaviour in the case behind pre-existing issue
  4. Details in finding 1.
- Contract unchanged; purity PASS with 9 documented transitional logging items whose markers
  match the notes' table one-to-one.
- Before merging: one fresh CMake configure (`art_make` glob), a build, and the regression
  comparison in section 8 of the notes, with association pairs compared in produced order
  (finding 2).

## Original module in brief

Written from `git show 5d619357:...` before I read the new code or the notes.

`DisambigFromSpacePoints` is an `EDProducer` that reassigns DUNE induction hits, whose
channels map to several wire segments, to one segment. It builds a map from space point index
to TPC using each space point's collection hit. For every induction hit it votes per TPC over
its associated space points: a segment counts if the space point projects within one wire
pitch. The TPC with the highest score wins, and ties go by `unordered_map` iteration order.
Collection hits keep `ChannelToWire(...).front()`. Unresolved hits can then be placed by a
distance-weighted score over the N nearest already-resolved hits on each allowed segment
(`UseNeighbors`). Hits still left go on every allowed segment (`"repeat"`), on the first
allowed segment (`"first"`), or are dropped. Contract: consumes `std::vector<recob::Hit>`
(`HitModuleLabel`), `std::vector<recob::SpacePoint>` and the hit-space point `Assns`
(`SpModuleLabel`), and the hit-wire `Assns` (`HitModuleLabel`). It produces a new hit
collection plus hit-wire `Assns` through `HitCollectionCreator` and a copied
`Assns<Hit,SpacePoint>`. When `MonitoringPlots` is set it also fills an optional `hitstats`
TTree from member counters. Uses the `WireReadout` and `DetectorPropertiesService` services.
`fNMissedByNeighbors` is written only when `UseNeighbors` is true.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Scope | `git status --short`, `git diff --stat 5d619357`, `git ls-files --others` | `M DisambigFromSpacePoints_module.cc`; `A DisambigFromSpacePointsAlg.h`, `A DisambigFromSpacePointsAlg.cxx` (staged as new). Nothing outside `dunereco/HitFinderDUNE/`. No build-file changes. |
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: `.h` 0/0/0; `.cxx` 0 errors, 0 warnings, 9 transitional (MessageLogger include + 8 `mf::Log*`) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | `contract unchanged (13 items)`. Also checked by hand: `declare_products(producesCollector(), "", true, false)`, `produces<Assns<Hit,SpacePoint>>()`, `put_into` then `put` unconditionally, FHiCL names, types and comments identical. `contract.before.txt` == `contract.after.txt`. |
| Algorithm inventory | `art_inventory.py report <alg files>` | `.h`: no framework constructs. `.cxx`: only `messagefacility` include and 8 `MessageLogger` uses. |
| Module inventory | `art_inventory.py report DisambigFromSpacePoints_module.cc` | All framework constructs (EDProducer, FHiCL, handles, FindOneP/FindManyP, PtrMaker, Assns, 3 ServiceHandles, TFileService/TTree, put) are in the module. Member writes in `produce`: `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` (monitoring branch buffers, as before). |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -rn PHLEX-TRANSITIONAL <new files>` | 9 markers (`.cxx` L16, 49, 145, 176, 241, 254, 335, 341, 347), each directly above the constructs at L17, 50, 146, 177, 242, 255, 336, 342, 348. These are the 9 rows of the notes' section 6 table, in both directions. All are logging with a valid reason. |
| Patch file | `git diff 5d619357 \| diff - extraction.patch` | identical |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | minor | `DisambigFromSpacePoints_module.cc:175-179` | **Space point `art::Ptr` dereference moved from lazy to eager** (flagged by the extractor). Every `Ptr<SpacePoint>` of every hit is now resolved with `&(*sp)` before the algorithm runs. That includes collection hits, hits whose channel has no wires, and space points not in `spToTPC` or not in a candidate TPC. The original dereferenced only at original L328 (`sp->position()`), and only for those that passed the `spToTPC` and TPC checks. Values used are identical. Error path: canvas 3.17 `Ptr::operator*` → `get()` → `operator->` → `parentProduct_()` throws `art::Exception(errors::ProductNotFound)` when the product is unavailable. That is the same exception type the original's `sp->` would throw, but now reachable for Ptrs the original never touched, and it fires before any "No wires for this channel???" warnings the original would have logged first. It can only happen if the `Assns` under `SpModuleLabel` points to a space point product that cannot be read, while `getValidHandle<std::vector<recob::SpacePoint>>(SpModuleLabel)` has already succeeded. SpacePointSolver writes the space points and the `Assns` together, so ordinary input cannot reach this. A null `Ptr` would now be `*nullptr` (UB, in practice a null `spacePoint` that is dereferenced later only on the original's path) where the original threw from `parentProduct_`. `Assns` do not hold null Ptrs in practice. Dereferencing also fills the transient `RefCore` product-pointer cache of the Ptrs stored in `FindManyP`. Those Ptrs are later copied into the output `Assns`, but persistence writes only `ProductID` and key, so the product is unaffected. | Original L317-L328; module L175-L179; alg `.cxx` L157-L168 (concatenated numbering: L242-L253); `~/.cache/rattler/cache/pkgs/canvas-3.17.0-h39d6d14_0/include/canvas/Persistency/Common/Ptr.h` L130-L150, L238-L262 | **Accept** as documented (notes section 4, "Intentional deviations"). Lazy resolution would need a callback or `art::Ptr` in the algorithm, which defeats the extraction. Resolving through `(*spHandle)[key]` instead would *change* values in the case of pre-existing issue 4 (association pointing at a different product), so the current eager `&*sp` is the more faithful choice. Optional: add one sentence to the notes about the null-Ptr sub-case. |
| 2 | minor | `MIGRATION_NOTES.md` §8 | The validation plan says to compare the hit vector unsorted, which is right. For `Assns<Hit,Wire>` and `Assns<Hit,SpacePoint>` it only says "key pairs" and does not say *in produced order*. The ordering claim (output order set by `unordered_map` iteration) is the main risk this extraction carries, and a sorted or set-wise pair comparison would hide a regression there. The plan also has no case that hits the per-TPC score tie, where `tpcScore` iteration order decides the result. | notes L193-L198 | State that both `Assns` are compared pair by pair in stored order, with no sorting. Use `UseNeighbors: false` + `MoveLeftovers: "repeat"` (largest `hitToNWires`) as one of the configurations. Ordinary FD/PD-HD events with many space points will hit ties by themselves. |
| 3 | nit | module L170-L179 | New, undocumented sub-case: `spFromHit.at(i)` is now called for *every* hit (original: only for induction hits with wires, plus every output hit). If the hit-space point `Assns` were missing (`FindManyP` invalid → `throwIfInvalid` → `LogicError`), the new code throws in more events. The only event where the original did not also throw is one with zero space points *and* where every hit's channel has no wires (nothing assigned, nothing output). Unreachable in practice. | canvas `FindManyP.h` L347-L351, L377-L385 | Optional one-line mention in the notes, or no action. |
| 4 | nit | alg `.h` L53-L57; module L184-L189 | Pre-existing UB note (notes issue 2) is accurate but incomplete. For an induction hit with `Plane == 2`, `nMissedBySpacePoints[2]` spills into `nMissedByNeighbors[0]` in both versions. In the original, with `UseNeighbors: false`, the spill went into the *member* `fNMissedByNeighbors[0]`, built up across events and was recorded in `hitstats`. Now it goes into `stats.nMissedByNeighbors[0]`, which the module discards when `useNeighbors` is false. Unreachable in DUNE geometries, where induction planes are 0 and 1, and UB either way. | original L305, L310; alg `.cxx` L145, L150 (L60, L65 in file numbering) | Add one clause to issue 2 in the notes. No code change in pass 1. |
| 5 | nit | `dunereco/HitFinderDUNE/CMakeLists.txt` | The algorithm is globbed into the existing `HitFinderDUNE` library. That library already links `art::*`, `canvas`, `fhiclcpp`, `MF_MessageLogger` and larsim services, which are pre-existing and needed by sibling files. Nothing was added, so this conforms for pass 1. A future Phlex plugin that links `HitFinderDUNE` would still pull in art. `art_make` globs at configure time, so a fresh CMake configure is needed. | CMakeLists L1-L42 | Note it for pass 2: split out a framework-free algorithm library (`SHARED`) when binding to Phlex. Mention the fresh configure in the build instructions. |
| 6 | nit | `MIGRATION_NOTES.md` §2-§4 | Some line references are off by 1-2: `eventHits` is module L162 (notes L161); the stats copy is L184-L189 (notes L183-L189); `mapSpacePointsToTPC` is `.cxx` L288-L312 (notes L288-L310); `runOnSpacePoints` ends at L118 (notes L117). | file contents | Refresh line numbers. |

## Behaviour-preservation walk-through

Algorithm `.cxx` line numbers are file-local (header not counted).

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L45-L49 typedefs | alg `.h` L28-L32 | identical | Same names in `dune`; no collisions in dunereco/dunecore/duneprototypes/duneana/dunesw |
| L53-L66 `Config` | module L55-L67 | identical | Names, types, comments unchanged |
| L122-L133 ctor init list | module L102-L108, `make_cfg` L91-L100 | mechanical edit OK | Each field maps to the right config entry (`useNeighbors`, `numNeighbors`, `maxDistance`, `moveLeftovers`, `excludeTPCs`). Declaration order `fMonitoringPlots, fCfg, fHitModuleLabel, fSpModuleLabel` matches init order. |
| L134-L137 `NumNeighbors < 1` throw | module L110-L113 | mechanical edit OK | Same type, category, message, and still before `declare_products` |
| L142-L158 declare/produces/geometry/TTree | module L118-L134 | identical | |
| L163-L183 run/event, handles, `FindOneP`, `hcol`, `assns` | module L139-L159 | identical | |
| L186-L187 `fill_ptr_vector` | module L162 `*hitsHandle` | mechanical edit OK | `fill_ptr_vector` makes `Ptr(h,i)`, so key == index; same size, so `reserve(eventHits.size())` is the same |
| L189-L190 `FindManyP` x2 | module L164-L165 | identical | |
| L192 `detProp` | module L167 | identical | once per event |
| L193-L212 `spToTPC` loop | alg `mapSpacePointsToTPC` L288-L312 | mechanical edit OK | `auto hits` (Ptr vector copy) → `auto const& hits` (raw pointers). Same iteration, same early `break`/`continue`, same `operator[]` insert order |
| L214-L219 locals + `reserve` | alg L327-L332 (`res.hitToWire`, `res.hitToNWires`) | mechanical edit OK | Same container types, same `reserve` before any insert |
| L221-L222 `runOnSpacePoints` + `LogInfo` | alg L334-L336 | identical | Message text and category unchanged |
| L224-L228 `UseNeighbors` branch + `LogInfo` | alg L338-L343 | identical | |
| L230-L232 leftover switch | alg L345-L348 | identical | Same string compares, same "dropped" `LogInfo` |
| L278-L363 `runOnSpacePoints` | alg L30-L118 | mechanical edit OK | `hit->` → `hit.`; `hit.key()` → `i`; `fNHits`/`fNMissedBySpacePoints` → `stats.*` (int); `sp.key()` → `sp.key`; `sp->position()` → `sp.spacePoint->position()`. Same zeroing at entry, same loop bounds and `<`/`>` comparisons, same `float` arithmetic, same `tpcScore` tie-breaking by `unordered_map` iteration |
| L365-L467 `resolveUnassigned` | alg L120-L227 | mechanical edit OK | `fMaxDistance`, `fExcludeTPCs` → `cfg.*`; geometry via reference; `hitInd->PeakTime()` → `hitInd.PeakTime()`. `(0,0,plane)` and `GetXTicksCoefficient(0,0)` quirk kept. Same local `result` map, erase loop and `insert` |
| L469-L493 `assignFirstAllowedWire` | alg L229-L257 | mechanical edit OK | Both warnings kept |
| L495-L516 `assignEveryAllowedWire` | alg L259-L282 | mechanical edit OK | Silent skip kept |
| L236-L251 hitToWire output loop | module L193-L208 | mechanical edit OK | `*(eventHits[key])` → `eventHits[key]` (same object); `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)` (same index); `auto sps` still a copy of the same Ptrs, still added in the same order |
| L253-L269 hitToNWires output loop | module L210-L226 | mechanical edit OK | as above |
| L271-L275 fill, put | module L228-L232 | identical | Tree fill still after the counters are set; puts unconditional |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L91-L100 `make_cfg` | Copies validated FHiCL values into a POD | None. Every field is assigned, so no indeterminate config value. |
| module L170-L174 `hitsPerSpacePoint` | Resolves `hitsFromSp` Ptrs into `recob::Hit const*` | None on ordinary input. The original already dereferenced every hit of every space point (the first loop has no `break` when no collection hit exists; otherwise the second loop dereferences all of them), in the same SP-major order, so the first failing Ptr and the exception are the same. Confirms the notes' claim. |
| module L175-L179 `spacePointsPerHit` | Resolves `spFromHit` Ptrs into `{key, const*}` | Values identical. Eager error path, see findings 1 and 3. |
| module L184-L189 stats copy | Writes `fNHits`, `fNMissedBySpacePoints` every event, and `fNMissedByNeighbors` only when `useNeighbors` | Same write sites as the original (runOnSpacePoints writes always; resolveUnassigned only when UseNeighbors). The indeterminate `fNMissedByNeighbors` with `UseNeighbors: false` is kept, not "fixed". |
| alg L322 `DisambigResult res{}` + `return res` | Value-initialised result returned by value | `stats` arrays start at zero but are explicitly zeroed by the helpers before use, as before. NRVO or implicit move keeps `unordered_map` node/bucket structure, so iteration order is preserved. `DisambigResult result = disambiguateHits(...)` is guaranteed elision (C++17). |
| alg `mapSpacePointsToTPC` public function | Split out of `produce` | Called once, in the same position in the sequence (before `runOnSpacePoints`) |

Checked and found unchanged: random draws (none); state lifetime (no member became local
or the reverse except the per-event counters, which reach the same members); signed and
unsigned types (`size_t` keys and TPCs, `unsigned int` cryo/plane in `resolveUnassigned`,
all as before); exceptions (no new throws in the algorithm); log text and categories (all
`"DisambigFromSpacePoints"`, same order relative to one another); service data fetched once
per event as before; no references into event data kept past `produce`
(`SpacePointRef::spacePoint` and `recob::Hit const*` live only inside the call).

## Validation plan

The plan in notes section 8 is mostly sound. It builds the base and the branch in the same
environment and covers FD (`dunefd_disambigfromsp`) and PD-HD (`pdune_disambigfromsp`).
It adds overrides for `"first"`, `"drop"`, `UseNeighbors: false` and a non-empty
`ExcludeTPCs`, so every branch the extraction touched is exercised, and it compares hits
unsorted plus the `hitstats` tree, correctly excluding `fNMissedByNeighbors` when
`UseNeighbors: false`. Gap: association pairs must explicitly be compared in stored order
(finding 2). Neither eager-dereference error path can be exercised with ordinary input,
which is consistent with its classification.

## Compile-risk review

Checked by reading, against the local LArSoft checkout `<LArSoft checkout>`
(`larcorealg` @ `b170a9c`, develop, 2025-08-25) and canvas 3.17.0 from `~/.cache/rattler`.
These may not be the exact versions `v10_26_00d02` builds against. The APIs used are
long-standing and the module code that uses them is unchanged.

- `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) const`, `Plane(PlaneID const&) const`
  (the braced `{0,0,plane}` selects this overload because the other `Plane` takes two
  arguments), `PlaneGeo::WireCoordinate(Point_t const&)`, `WirePitch()`,
  `DetectorPropertiesData::GetXTicksCoefficient(int,int) const`,
  `recob::SpacePoint::position()`, and `recob::HitCreator(recob::Hit const&, geo::WireID
  const&)` are all present.
- Includes: the `.h` has every type it uses (`WireReadoutGeom.h`, `geo_types.h`,
  `DetectorPropertiesData.h`, `Hit.h`, `SpacePoint.h`, `<array> <map> <string>
  <unordered_map> <vector> <cstddef>`). The `.cxx` adds `PlaneGeo.h`, `<algorithm> <cmath>
  <utility>`. The transitional MessageLogger include sits in the `.cxx`, not the header.
  None of `lardataobj`, `larcorealg`, `lardataalg` or `larcoreobj` pulls in art.
- Name lookup: the anonymous-namespace helpers are found by unqualified lookup from inside
  `namespace dune` (no `dune::` names shadow them); the `using dune::...` declarations
  inside the anonymous namespace are valid.
- Declarations match definitions (`mapSpacePointsToTPC` and `disambiguateHits`: same types,
  only parameter names differ). No functions are defined in the header. No `const&` misuse.
  No move-only copies. No C++20 features. The header is safe under C++23.
- `static DisambigFromSpacePointsCfg make_cfg(Config const&)` used in the mem-initializer:
  valid.
- Build: no `CMakeLists.txt` change is needed because `art_make` globs the `.cxx` into
  `HitFinderDUNE`, whose `LIB_LIBRARIES` already includes `lardataobj::RecoBase`,
  `larcorealg::Geometry`, `lardataalg::DetectorInfo` and `messagefacility::MF_MessageLogger`.
  The plugin links `HitFinderDUNE`. Needs a fresh configure. Needs build to confirm:
  nothing specific; residual risk is low.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `wireReadout`
  and `detProp` passed explicitly; no helper receives the event or a handle; nothing
  event-scoped is cached across events (members hold config, the job-scoped geometry
  provider pointer, the `TTree*`, and branch buffers rewritten each event as before).
- Extraction checklist 1 to 5: 1 yes (free function, no callback dependency); 2 yes (hits,
  both association directions, geometry, detector properties, cfg); 3 yes (`DisambigResult`
  by value; internal helpers keep out-params privately); 4 yes (`make_cfg`, `const` member);
  5 yes (9 logging items, table matches markers).
- Binding plan: plausible. It uses a `transform` for `disambiguateHits` at event layer with
  unlimited concurrency (the code is re-entrant: no statics or mutable state, only `const`
  geometry and detector-property calls, and thread-safe `mf::Log*`). `observe` for `hitstats`
  is serial with the tree as a serialized resource. It correctly names the blockers:
  persistable `Assns` (input and output), the art-dependent `HitCreator` library, conditions
  access for `DetectorPropertiesData`, and the geometry provider. `MonitoringPlots` is
  treated as a registration-time switch rather than a predicate, which is right. There is no
  unfold or fold, and the notes explain why the event is the natural layer.

## Notes accuracy

- Ordering claim (section 4, "Kept"): **correct**.
- Eager space point dereference (section 4, "Intentional deviations"): **correct** as far as
  it goes. It leaves out the null-Ptr sub-case (finding 1) and the `FindManyP`-invalid
  sub-case (finding 3).
- "`hitsFromSp` ... not a deviation": **correct** (checked against original L199-L211).
- Pre-existing issue 2: accurate but incomplete (finding 4).
- Line references off by 1-2 in a few places (finding 6).
- No instructions addressed to an agent found in the source, comments, FHiCL, or notes.
