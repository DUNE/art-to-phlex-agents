# Phlex pass 1 (separation and extraction): `DisambigFromSpacePoints`

| | |
|---|---|
| Repository and base | `dunereco` @ `5d619357` (`origin/develop`, "Merge tag 'v10_26_00d02' into develop") |
| Module | `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` (art::`EDProducer`) |
| Working tree | `<worktree>`, branch `phlex-extract/DisambigFromSpacePoints-v1` |
| Guide | phlex-examples `migration/doc` @ 5df307b (v0.1.alpha, 2026-09-09) |
| Phlex target | v0.4.1 (phlex-examples `phlex-v0.4`) |
| Kit | art-to-phlex-agents @ uncommitted (working tree has no commits; files dated 2026-10-04) |
| Agent / model | phlex-extractor (Claude Code subagent), Opus 5.5 (`claude-opus-5-5`) |
| Build status | **NOT COMPILED** (build policy: static work only) |

## 1. What the module computes

Each induction-plane hit sits on a readout channel that maps to several wire segments (the
wires wrap around the APA). The module picks the segment for each hit. Collection hits keep
their single wire. An induction hit takes the wire segment that lies within one wire pitch of
the space points built from it, voting per TPC side. Hits left over are optionally placed by
the distance-weighted score of up to N nearest already-resolved hits on each candidate
segment. Remaining hits are then placed on every allowed segment, on the first allowed
segment, or dropped, by configuration. The output is a new hit collection with corrected wire
IDs, plus copies of the hit-wire and hit-space point associations, and optionally a tree of
per-plane counts of unresolved hits.

## 2. Framework inventory and classification

From `art_inventory.py report` on the original (line numbers are the original file at
`5d619357`; "now" is the working tree).

| # | Construct (original file:line) | Kind | Decision | Where it lives now |
|---|---|---|---|---|
| 1 | `art::EDProducer` base, `DEFINE_ART_MODULE` (L51, L518) | module | boundary | module L53, L235 |
| 2 | validated FHiCL `Config` table, 7 `Atom` + 1 `Sequence` (L53-L66) | configuration | boundary; values copied once into `DisambigFromSpacePointsCfg` by `make_cfg` | module L55-L68, `make_cfg` L91-L100 |
| 3 | `NumNeighbors < 1` check, `cet::exception` (L134-L137) | exception / configuration | boundary (constructor validation) | module L110-L113 |
| 4 | `HitCollectionCreator::declare_products(...)` (L142), `produces<Assns<Hit,SpacePoint>>` (L145) | product output | boundary | module L118, L121 |
| 5 | `ServiceHandle<geo::WireReadout>()->Get()` cached as `fWireReadoutGeom` (L147) | service | data: module keeps the provider pointer (job-scoped, allowed); algorithm receives `geo::WireReadoutGeom const&` | module L123, passed at L181 |
| 6 | `ServiceHandle<TFileService>`, `TTree` "hitstats" and branches (L149-L158), `fTree->Fill()` (L271) | histogram/TTree | boundary | module L125-L134, L228 |
| 7 | `evt.run()`, `evt.id().event()` into `fRun`, `fEvent` (L163-L164) | event metadata | boundary (only used for the monitoring tree) | module L139-L140 |
| 8 | `getValidHandle` hits and space points (L166-L167) | event retrieval | boundary (already modern retrieval; handles still needed for `FindOneP`/`FindManyP`/`PtrMaker`) | module L142-L143 |
| 9 | `FindOneP<recob::Wire>` (L172) | art::Ptr/Assns | boundary: feeds the hit-wire association written by `HitCollectionCreator` | module L148 |
| 10 | `HitCollectionCreator hcol` construction, `emplace_back`, `put_into` (L176, L243, L260, L274) | product output | boundary | module L152, L200, L217, L231 |
| 11 | `std::vector<art::Ptr<recob::Hit>> eventHits` + `fill_ptr_vector` (L186-L187) | art::Ptr | convenience: replaced by `std::vector<recob::Hit> const& eventHits = *hitsHandle` (keys equal indices) | module L161 |
| 12 | `FindManyP<recob::SpacePoint> spFromHit` (L189) | art::Ptr/Assns | boundary: its `art::Ptr`s are written into the output `Assns`; resolved into `std::vector<std::vector<SpacePointRef>>` (key + object pointer) for the algorithm | module L164, L175-L179, L203, L220 |
| 13 | `FindManyP<recob::Hit> hitsFromSp` (L190) | art::Ptr/Assns | convenience for the algorithm (object access only); kept as `FindManyP` so that dereference raises the same art exception, resolved into `std::vector<std::vector<recob::Hit const*>>` | module L165, L170-L174 |
| 14 | `ServiceHandle<DetectorPropertiesService>()->DataFor(evt)` (L192) | service | data: `detinfo::DetectorPropertiesData const&` parameter | module L167, passed at L181 |
| 15 | `art::PtrMaker<recob::Hit>`, `art::Assns` + `addSingle` (L183, L234, L249, L266), `evt.put` (L275) | art::Ptr/Assns, product output | boundary | module L158, L191, L206, L223, L232 |
| 16 | member state written in helpers: `fNHits`, `fNMissedBySpacePoints` (runOnSpacePoints), `fNMissedByNeighbors` (resolveUnassigned) | callback state | per-event scratch for monitoring; algorithm returns `DisambigStats`, module copies into the branch members on the original write paths | alg `DisambigStats`; module L183-L189 |
| 17 | `mf::LogInfo` in `produce` (L222, L227, L232) | logging | transitional: moved into `disambiguateHits` with the step calls, to keep message order relative to the step warnings | alg L336, L342, L348 |
| 18 | `mf::LogWarning` in helpers (L295, L387, L417, L479, L491) | logging | transitional | alg L50, L146, L177, L242, L255 |
| 19 | `art::Ptr` in private helper signatures (L74, L85, L93, L99, L279, L293, L368, L471, L497) | art::Ptr | convenience: helpers take `std::vector<recob::Hit> const&` and use indices | alg file-local helpers |

There are no `consumes<>` calls in the original or in the rewrite (see section 4).

## 3. Extracted algorithm API

`dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h`:

```cpp
namespace dune {
  typedef std::map< unsigned int, std::vector< size_t > > plane_keymap;          // moved from module
  typedef std::map< unsigned int, plane_keymap > tpc_plane_keymap;
  typedef std::map< unsigned int, tpc_plane_keymap > cryo_tpc_plane_keymap;

  struct DisambigFromSpacePointsCfg {     // no default member values
    bool useNeighbors;
    size_t numNeighbors;
    float maxDistance;
    std::string moveLeftovers;
    std::vector< size_t > excludeTPCs;
  };

  struct SpacePointRef { size_t key; recob::SpacePoint const* spacePoint; };

  struct DisambigStats {
    std::array<int, 3> nHits{};
    std::array<int, 2> nMissedBySpacePoints{};
    std::array<int, 2> nMissedByNeighbors{};   // meaningful only when useNeighbors
  };

  struct DisambigResult {
    std::unordered_map< size_t, geo::WireID > hitToWire;
    std::unordered_map< size_t, std::vector<geo::WireID> > hitToNWires;
    DisambigStats stats;
  };

  std::unordered_map< size_t, size_t > mapSpacePointsToTPC(
    std::vector< std::vector< recob::Hit const* > > const& hitsPerSpacePoint);

  DisambigResult disambiguateHits(
    DisambigFromSpacePointsCfg const& cfg,
    std::vector< recob::Hit > const& hits,
    std::vector< std::vector< SpacePointRef > > const& spacePointsPerHit,
    std::vector< std::vector< recob::Hit const* > > const& hitsPerSpacePoint,
    geo::WireReadoutGeom const& wireReadout,
    detinfo::DetectorPropertiesData const& detProp);
}
```

The former private methods `runOnSpacePoints`, `resolveUnassigned`, `assignFirstAllowedWire`,
`assignEveryAllowedWire` are file-local functions in an anonymous namespace in
`DisambigFromSpacePointsAlg.cxx`. They keep their in/out reference parameters, because the
three passes thread one `unordered_map` whose iteration order defines the output hit order
(see section 4). The public entry point returns everything by value.

- Inputs and where the module gets each one:
  - `cfg`: built once in the constructor by `make_cfg(config())`, a `const` member.
  - `hits`: `*hitsHandle` (`getValidHandle<std::vector<recob::Hit>>(HitModuleLabel)`).
  - `spacePointsPerHit`: from `FindManyP<recob::SpacePoint>(hitsHandle, evt, SpModuleLabel)`; for
    each hit, each associated space point as `{ptr.key(), ptr.operator->()}`.
  - `hitsPerSpacePoint`: from `FindManyP<recob::Hit>(spHandle, evt, SpModuleLabel)`; `ptr.operator->()`.
  - `wireReadout`: `*fWireReadoutGeom` (from `ServiceHandle<geo::WireReadout>()->Get()` in the constructor, as before).
  - `detProp`: `ServiceHandle<DetectorPropertiesService const>()->DataFor(evt)` once per event, as before.
- Outputs and how the module publishes each one:
  - `hitToWire`, `hitToNWires`: keys are indices into `hits`. The module loops them in the
    original order, builds `recob::HitCreator(hits[key], wid)`, `hcol.emplace_back(..., channelHitWires.at(key))`,
    and adds `(hitPtrMaker(hcol.size()-1), spPtr)` for each `spPtr` in `spFromHit.at(key)`.
  - `stats`: copied into `fNHits`, `fNMissedBySpacePoints` every event, and into
    `fNMissedByNeighbors` only when `UseNeighbors` is true (the only path where the original wrote it).
- Free function or class, and why: free functions. Setup is cheap (no tables, fitters or
  helper objects); everything per-event is a parameter.
- Re-entrancy: re-entrant. No statics, no mutable members (the former member counters are
  now in the returned `DisambigStats`), no ROOT globals, no random engine. `WireReadoutGeom`
  and `DetectorPropertiesData` are used through `const` calls only. `mf::Log*` is thread-safe.

## 4. Behaviour preservation

- Code moved verbatim (original lines → new file:lines):
  - `produce` L193-L212 (space point → TPC map) → `DisambigFromSpacePointsAlg.cxx` `mapSpacePointsToTPC` L288-L310.
  - `produce` L214-L232 (pass sequence, reserve, `LogInfo`s, leftover switch) → `disambiguateHits` L314-L351.
  - `runOnSpacePoints` L278-L363 → alg L30-L117.
  - `resolveUnassigned` L365-L467 → alg L120-L226.
  - `assignFirstAllowedWire` L469-L493 → alg L229-L256.
  - `assignEveryAllowedWire` L495-L516 → alg L259-L283.
  - typedefs `plane_keymap`, `tpc_plane_keymap`, `cryo_tpc_plane_keymap` L46-L49 → alg header.
- Mechanical edits:
  - `fWireReadoutGeom->` → `wireReadout.`; `fExcludeTPCs` → `cfg.excludeTPCs`; `fMaxDistance` → `cfg.maxDistance`;
    `fUseNeighbors`, `fNumNeighbors`, `fMoveLeftovers` → `cfg.useNeighbors`, `cfg.numNeighbors`, `cfg.moveLeftovers`.
  - `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` → `stats.nHits`, `stats.nMissedBySpacePoints`, `stats.nMissedByNeighbors` (same element types, `int`).
  - `const art::Ptr<recob::Hit>& hit = eventHits[i]` → `const recob::Hit& hit = eventHits[i]`; `hit->` → `hit.`; `hit.key()` → `i`
    (`fill_ptr_vector` makes `Ptr(handle, i)`, so the key is the index).
  - `spFromHit.at(k)` (`std::vector<art::Ptr<SpacePoint>>`) → `spFromHit.at(k)` (`std::vector<SpacePointRef>`); `sp.key()` → `sp.key`; `sp->position()` → `sp.spacePoint->position()`.
  - `auto hits = hitsFromSp.at(i)` (a copy of a `Ptr` vector) → `auto const& hits = hitsFromSp.at(i)` (a reference into the plain vector).
  - module output loops: `*(eventHits[key])` → `eventHits[key]` (a `recob::Hit const&` into `*hitsHandle`); `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)`.
  - Kept: `hitToWire.reserve(eventHits.size())` before the first insert, and the same single `unordered_map` object threaded through all passes and then moved out in `DisambigResult`. `std::unordered_map` iteration order depends on bucket count and insertion history, and it decides the order of the output hits and associations. A move keeps the node structure.
- Intentional deviations:
  - **Space point dereference is now eager (error path only).** The boundary resolves every
    `art::Ptr<recob::SpacePoint>` in `spFromHit` with `sp.operator->()` before the algorithm runs
    (module L178). The original dereferenced a space point only when its key was in the TPC
    map and a candidate wire was in that TPC (original L328). The values are identical. The
    difference: if an associated space point lived in a product that is not available, the
    new code throws `art::Exception` (same category) where the original might never have
    touched it. Under normal inputs the pointers point into the `SpModuleLabel` space point
    product that `getValidHandle` has already fetched, so this cannot fire. A human should
    accept this, or ask for lazy resolution.
    `operator->()` is the same code path as the original `sp->`: a null or unavailable `Ptr`
    throws `ProductNotFound` from `parentProduct_()`. Revision 1 used `&(*sp)` here and
    `&(*h)` for the hits (L173). In canvas 3.17 that is `*get()`, which dereferences `nullptr`
    for a null `Ptr` instead of throwing. Both were changed in revision 2, after the
    planted-bug test of the verifier found the problem.
  - `hitsFromSp` is also resolved eagerly (module L173), but the original dereferenced every
    hit of every space point anyway (the first loop dereferences up to the collection hit,
    the second loop all of them), in the same order. The first failing `Ptr` is the same, so
    this is not a deviation.
  - The three `mf::LogInfo` calls moved from `produce` into `disambiguateHits` (text unchanged,
    order relative to the step warnings unchanged).
- Suspected pre-existing issues noticed and **not** fixed:
  1. `fNMissedByNeighbors` is never initialised when `UseNeighbors: false`; with `MonitoringPlots: true` the tree records indeterminate values. Behaviour kept (module writes it only when `useNeighbors`).
  2. `nHits[plane]` and `nMissedBySpacePoints[plane]` (and `nMissedByNeighbors[plane]`) are indexed by `WireID().Plane` with no bound check. A non-collection hit with plane ≥ 2 (≥ 3 for `nHits`) writes out of bounds. In the original that spilled into the neighbouring member; `DisambigStats` keeps the same field order, but the write is undefined behaviour either way.
  3. `resolveUnassigned` computes `dwMax`, `ddMax` from plane `{0, 0, plane}` and `GetXTicksCoefficient(0, 0)` (cryostat 0, TPC 0) for every hit; `dwMax * pitch / pitch` is a round trip. Wrong for detectors where pitch or drift coefficient differ per TPC.
  4. `spToTPC` is keyed by index into the `SpModuleLabel` space point collection, but looked up with `sp.key()` of pointers from the hit→space point association. This assumes both refer to the same product.
  5. In `runOnSpacePoints`, ties in the per-TPC score are broken by `std::unordered_map` iteration order (implementation-defined, stable for a given standard library).
  6. `allIndHits[cryo][tpc][plane]` uses `operator[]` and inserts empty map entries as a side effect (harmless, kept).
  7. `assignEveryAllowedWire` silently skips hits whose channel has no wires ("add warning here" comment).
  8. The module reads products with `getValidHandle`/`FindOneP`/`FindManyP` but declares no `consumes<>`; it relies on art's lax consumes checking.
  9. FHiCL comments: `HitModuleLabel` says "HitPointSolver label." and `ExcludeTPCs` says "inndexes" (text only; not changed because comments are part of the FHiCL description).
  10. Found by `phlex-tester`: a collection hit whose `WireID` has TPC equal to `geo::TPCID::InvalidID` collides with the "no collection hit" sentinel in the space point to TPC map, so that space point is skipped. Pinned in `DisambigFromSpacePointsAlg_test.cc` as `invalid_tpc_on_collection_hit_skips_space_point_quirk`; see `TESTS.md`.

## 5. Framework-visible contract

`art_inventory.py --repo <worktree> contract-diff --before git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc --after dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`:
**contract unchanged (13 items)**. `contract.before.txt` and `contract.after.txt` are identical.

The module declares products only through `declare_products` and `produces<>`, both seen by
the tool. Checked by hand as well: the constructor still calls
`declare_products(producesCollector(), "", true, false)` then
`produces<art::Assns<recob::Hit, recob::SpacePoint>>()`, and `produce` still calls
`hcol.put_into(evt)` then `evt.put(std::move(assns))` unconditionally, on every path. The
`HitCollectionCreator` is still built with `doWireAssns = channelHitWires.isValid()`. FHiCL
names, types and comments are unchanged; none had defaults, and none have now.

## 6. Transitional items

`check_purity.py` on the two algorithm files: 0 errors, 0 warnings, 9 transitional.

| file:line | What | Why it stays | How it goes away |
|---|---|---|---|
| `DisambigFromSpacePointsAlg.cxx:17` | `#include "messagefacility/MessageLogger/MessageLogger.h"` | logging inside the algorithm | Phlex logging choice (spdlog), or return the counts/messages |
| `DisambigFromSpacePointsAlg.cxx:50` | `mf::LogWarning` "No wires for this channel???" (runOnSpacePoints) | deep logging, text kept | same |
| `DisambigFromSpacePointsAlg.cxx:146` | `mf::LogWarning` "No wires for this channel???" (resolveUnassigned) | same | same |
| `DisambigFromSpacePointsAlg.cxx:177` | `mf::LogWarning` "Did not find resolved wire id." | same | same |
| `DisambigFromSpacePointsAlg.cxx:242` | `mf::LogWarning` "No wires for this channel???" (assignFirstAllowedWire) | same | same |
| `DisambigFromSpacePointsAlg.cxx:255` | `mf::LogWarning` "None of wires is allowed for this hit???" | same | same |
| `DisambigFromSpacePointsAlg.cxx:336` | `mf::LogInfo` "... hits undisambiguated by space points." | moved from `produce` to keep message order | log at the boundary from `stats` once order no longer matters |
| `DisambigFromSpacePointsAlg.cxx:342` | `mf::LogInfo` "... hits undisambiguated by neighborhood." | same | same |
| `DisambigFromSpacePointsAlg.cxx:348` | `mf::LogInfo` "Remaining undisambiguated hits dropped." | same | same |

No `cet::exception` or other warnings in algorithm code. The `cet::exception` for
`NumNeighbors < 1` stays in the module constructor.

## 7. Phlex binding plan (not implemented)

| Extracted piece | Node | Inputs (creator / layer / suffix [/ stage]) | Output suffix(es) | Layer | Concurrency | Resources | Gate (when) | Blockers |
|---|---|---|---|---|---|---|---|---|
| association adapter: build `spacePointsPerHit` and `hitsPerSpacePoint` | `transform` (or folded into the main lambda) | `gaushit` / event / "" (`std::vector<recob::Hit>`); `reco3d` (FD: `spsolve`) / event / "" (`std::vector<recob::SpacePoint>`); hit↔space point links from the space point solver, as index lists | none if folded in | event | unlimited | none | none | **persistable associations**: Phlex has none. Needs the upstream space point solver to publish `std::vector<std::vector<size_t>>` index lists (or similar) instead of `Assns`. `SpacePointRef` then becomes `{key, &spacepoints[key]}` built inside the node. |
| `disambiguateHits` | `transform` | the hits, the resolved links above, `detinfo::DetectorPropertiesData` (event layer, from a provider or conditions transform), `geo::WireReadoutGeom` (job layer, from a geometry `provide`) | `hits` (a `std::vector<recob::Hit>` built from `hitToWire`/`hitToNWires`), plus `hitstats` (`DisambigStats`) via a `std::tuple` return | event | unlimited | `WireReadoutGeom` as read-only data (or an unlimited resource) | none | building the new hits uses `recob::HitCreator` (`lardata/ArtDataHelper`, art-dependent library): needs a framework-free copy-with-new-WireID helper; output hit-wire and hit-space point `Assns` cannot be written; conditions access for `DetectorPropertiesData` |
| hit-wire and hit-space point association copies | (none yet) | | | event | | | | persistable associations |
| monitoring tree `hitstats` | `observe` | `DisambigStats` from the transform; run and event numbers from the data-cell index | none | event | serial (ROOT `TTree`) | the tree, as a serialized resource | `MonitoringPlots` (registration-time switch, not a predicate) | histogramming/TFileService |

`cfg` (`make_cfg`) becomes a lambda capture built from the jsonnet configuration;
`HitModuleLabel` and `SpModuleLabel` become `config.get<product_selector>(...)`. The
`NumNeighbors < 1` check moves to registration. Layer: the neighbour search spans all hits
of a cryostat/TPC/plane, and the space point vote needs all space points, so there is no
natural lower layer than the event; a per-cryostat `unfold` is possible but not supported by
the code as written. `mapSpacePointsToTPC` is public and could be split into its own
`transform` if another node needs the map.

## 8. Validation plan

- Build `dunereco` at `5d619357` and on this branch in the same environment.
- Jobs: `workflow_reco_dune10kt.fcl` path containing `hitfd` (`dunefd_disambigfromsp`,
  `MoveLeftovers: "repeat"`, `SpModuleLabel: "spsolve"`), and a ProtoDUNE-HD job with
  `hitpdune` (`pdune_disambigfromsp`, `MoveLeftovers: "repeat"`), e.g.
  `standard_reco_protodunehd_MC.fcl`. Add overrides for `MoveLeftovers: "first"` and
  `"drop"`, `UseNeighbors: false`, and a non-empty `ExcludeTPCs`.
- Same input file and event range, `MonitoringPlots: true` in one run.
- Compare: the output `std::vector<recob::Hit>` (unsorted, because the output order should be
  identical: same `unordered_map` operations, same standard library), the
  `Assns<recob::Hit, recob::Wire>` and `Assns<recob::Hit, recob::SpacePoint>` key pairs, and the
  `hitstats` tree (excluding `fNMissedByNeighbors` when `UseNeighbors: false`, issue 1). A
  product-dump analyzer or `art::EventDump` plus text diff is sufficient.
- Unit test idea: with a LArSoft geometry test environment for the 1x2x6 workspace, build a
  few `recob::Hit`s on one wrapped induction channel and one space point near one segment;
  check `disambiguateHits` picks that segment, and that with no space points the neighbour
  pass picks the segment closest to resolved neighbours.

## 9. Checklists

Guide extraction checklist, with evidence:

1. Core algorithm describable without framework callbacks: yes. Section 1 describes it with no art terms; `disambiguateHits` (`DisambigFromSpacePointsAlg.h` L75-L81) has no callback dependency.
2. All real inputs in the signature or constructor: yes. Hits, both association directions, wire readout geometry, detector properties and configuration are parameters (`DisambigFromSpacePointsAlg.h` L75-L81). No member or service access remains in the `.cxx`.
3. All outputs as return values or explicit output objects: yes. `DisambigResult` returned by value (`.h` L60-L64, `.cxx` L350); the former member counters are `DisambigStats`. Internal file-local helpers still use reference out-parameters to thread one `unordered_map` (order-preserving), not exposed.
4. Configuration collected outside the algorithm: yes. `make_cfg` in the module (module L91-L100), stored as `const DisambigFromSpacePointsCfg fCfg` (module L86).
5. Remaining framework assumptions documented as transitional: yes, 9 `PHLEX-TRANSITIONAL` logging items, section 6.

Separation checks:

- `ServiceHandle` only in the module: yes (module L123, L127, L167; none in the algorithm files).
- Every service-derived value passed explicitly: yes, `wireReadout` and `detProp` (module L181).
- No helper receives the event or a handle: yes.
- No event-scoped data cached across events: yes. Members are configuration, the job-scoped
  geometry provider pointer, the `TTree*` and its branch buffers (rewritten every event, as before).

Purity check summary (`check_purity.py`): **PASS**, 0 errors / 0 warnings / 9 transitional.

Static checks done instead of compiling: every type in the new files has an include
(`WireReadoutGeom.h`, `PlaneGeo.h`, `geo_types.h`, `DetectorPropertiesData.h`, `Hit.h`,
`SpacePoint.h`, `<array> <map> <unordered_map> <string> <vector> <algorithm> <cmath>`); the
typedefs moved out of the module are visible through the header include; the single call site
of `disambiguateHits` (module L181) matches the declaration; `WireReadoutGeom::ChannelToWire`,
`Plane(PlaneID)`, `PlaneGeo::WireCoordinate(Point_t)`, `WirePitch()` and
`DetectorPropertiesData::GetXTicksCoefficient(int,int)` checked against the local LArSoft
checkout. CMake: `art_make` globs the new `.cxx` into `HitFinderDUNE`, whose `LIB_LIBRARIES`
already has `lardataobj::RecoBase`, `larcorealg::Geometry`, `lardataalg::DetectorInfo` and
`messagefacility::MF_MessageLogger`; the plugin already links `HitFinderDUNE`. No
`CMakeLists.txt` change.
