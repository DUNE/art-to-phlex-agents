# Phlex pass 1 (separation and extraction): `DisambigFromSpacePoints`

| | |
|---|---|
| Repository and base | `dunereco` @ `ffc89e0d97c413cbfc3a1b17d7e278f734ba8cd9` (`origin/develop`, fetched 2026-09-15) |
| Module | `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` (art::EDProducer) |
| Working tree | `<worktree>`, branch `phlex-extract/DisambigFromSpacePoints` |
| Guide | phlex-examples `migration/doc` @ 5df307b (v0.1.alpha, 2026-09-09) |
| Kit | art-to-phlex-agents @ uncommitted (repo has no commits at the time of this run) |
| Agent / model | Claude Code EXTRACTOR run, claude-sonnet-5 |
| Build status | NOT COMPILED |

## Module selection

Shortlist, from `python3 art_inventory.py scan dunereco/dunereco duneopdet/duneopdet
dunecalib/dunecalib duneprototypes/duneprototypes dunesim/dunesim --top 40` (run against the
Feb-2026 working trees, then every candidate below was re-read from `origin/develop` before
picking):

| Module | Why considered | Why rejected / picked |
|---|---|---|
| `dunereco/CVN/*`, `RegCNN/*`, `TransformerCVN/*` | Top scores, EDProducer, real callback code | Excluded per task instructions: these packages already keep an `art/` subdirectory separate from framework-free code, and/or are ML inference wrappers. |
| `duneopdet/LowEPDSUtils/SolarOpFlash_module.cc` | EDProducer, flash finding, 1 Assns, 2 services, some `art::Ptr` | Rejected: the real clustering algorithm (`AdjOpHitsUtils::CalcAdjOpHits`, `MakeFlashVector`) already lives in a separate `AdjOpHitsUtils` class outside the module; the module itself only reshapes the result into `recob::OpFlash`. Same problem in `dunereco/LowEUtils/PerPlaneCluster_module.cc` and `SolarEvent_module.cc` (delegate to `LowEUtils`), so the whole "solar" family was set aside. |
| `dunereco/HitFinderDUNE/ShowerHitSeparator_module.cc` | EDProducer, MVA-threshold hit splitter, member `art::Handle`, TFileService diagnostics | Good separation example, but the actual "algorithm" is a single threshold cut on CNN scores computed elsewhere; closer to an ML-inference consumer than a reconstruction algorithm a physicist would point to. Kept as a runner-up. |
| `duneopdet/OpticalDetector/OpFlashFinderDualPhase_module.cc` (and `...VerticalDrift`) | EDProducer, real flash-finding algorithm inline as member functions (`RunFlashFinder`, `AssignHitsToFlash`, `ConstructFlash`, ...), 3 services, 1 Assns | Excellent algorithm candidate, explicitly the kind of module the task calls out ("optical-detector flash/hit finding"). Not picked only because its member functions already take fully explicit parameters (`HitVector`, `geom`, `wireReadout`, `ts`) with no service/event access inside them — separation stage 1 is nearly done already, so it exercises extraction (stage 2) but very little of separation (stage 1). |
| `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` | EDProducer, hit-to-wire disambiguation using `recob::SpacePoint`s, 3 services (`geo::WireReadout`, `detinfo::DetectorPropertiesService`, optional `art::TFileService`), exactly 1 `art::Assns` output, real algorithm as private member functions plus an inline association-resolution loop in `produce()` | **Picked.** Recognisable DUNE reconstruction step (LArSoft/DUNE hit disambiguation from 3D space points, R. Sulej). Exercises real separation work: a *cached `art::FindManyP<recob::SpacePoint>` member-function parameter*, convenience `art::Ptr<recob::Hit>`/`fill_ptr_vector` used only for read access + index, `FindManyP` used where plain `FindMany` suffices, and per-event scratch counters (`fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors`) mutated deep inside the algorithm. Uses `HitCollectionCreator`, `PtrMaker`, and index-based `art::Assns` construction — several LArSoft boundary patterns in one file. 410 non-blank lines (`art_inventory.py report`), inside the requested range. |

`dunereco/HitFinderDUNE/CMakeLists.txt` confirmed the package uses `art_make` (auto-globs new
`.cxx` files into the directory library at configure time; new headers need no CMake listing
either, but because `install_headers()` installs the whole directory, not because `art_make`
globs them -- corrected from round 1's "auto-globs new `.cxx`/`.h` files", F6); `git grep
DisambigFromSpacePoints origin/develop -- '*.fcl'` confirmed the
only user is `dunereco/HitFinderDUNE/hitfindermodules_dune.fcl`'s `standard_disambigfromsp`
(`UseNeighbors: true`, `MonitoringPlots: false`, `MoveLeftovers: "first"` by default), and no
other module in the package reuses `DisambigFromSpacePoints`'s private methods (they were
private member functions, not a shared `*Alg` class), so this is a self-contained, one-module
extraction.

Build note for hand-off (F9, nit): an existing configured build directory will not pick up the
new `DisambigFromSpacePointsAlg.cxx` without a fresh CMake configure, since `art_make`'s glob
runs at configure time. Also, the algorithm's translation unit is compiled into the
`HitFinderDUNE` library, which already links `art::*`, `fhiclcpp::*`, and
`messagefacility::*` for its other (non-extracted) sources -- "framework-free" holds at the
source level (`check_purity.py` PASS) but not at the link level; splitting the algorithm into
its own library target is a binding-stage decision, not done here.

## 1. What the module computes

Given a collection of reconstructed hits (one per waveform peak, ambiguous between several
possible wires because they came from an induction plane) and a collection of 3D space points
built from those hits, assign each induction hit to the single wire consistent with its
associated space points. Collection-plane hits are unambiguous and pass straight through.
Hits with no usable space point are optionally resolved from the wire already assigned to
their nearest neighbors in time and position, and any still left over are either dropped, put
on an arbitrary allowed wire, or duplicated onto every allowed wire, depending on
configuration. The module emits a new hit collection (each hit re-stamped with its resolved
wire) together with its association back to the space points that supported it.

## 2. Framework inventory and classification

Output of `art_inventory.py report` on the original (`git:ffc89e0d9:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`).

| # | Construct (original file:line) | Kind | Decision | Where it lives now |
|---|---|---|---|---|
| 1 | `fhicl::Table<Config>` / `Parameters` (L53-L66) | configuration | boundary | module, unchanged |
| 2 | `art::ServiceHandle<geo::WireReadout>()->Get()` (base L147) | service | data: pointer kept as module member, dereferenced to `geo::WireReadoutGeom const&` at each algorithm call | module ctor L123 (corrected from round 1's "L147", which was the base line; F6) + call sites in `produce()` |
| 3 | `art::ServiceHandle<art::TFileService>`, `TTree* fTree`, branches (L149-L158) | histogram/TTree | boundary (LArSoft "Histograms and TTrees" pattern) | module ctor, unchanged |
| 4 | `fNHits[3]`, `fNMissedBySpacePoints[2]`, `fNMissedByNeighbors[2]` mutated inside `runOnSpacePoints`/`resolveUnassigned` (L287-289, L299, L305, L310, L356, L374-375, L455) | callback state (per-event scratch, mutated deep in the algorithm) | convenience → **removed**: replaced by a local `dune::DisambigStats` returned/threaded through the algorithm calls; module copies `stats.*` into these members only to fill the TTree, **and only on the paths where the original wrote them** (round 2, F1: `fNMissedByNeighbors` is copied only `if (fUseNeighbors)`, matching the original leaving it unwritten otherwise) | `DisambigFromSpacePointsAlg.h/.cxx` (`DisambigStats`); module `produce()` L283-296 copies into the (still TTree-bound) members |
| 5 | `evt.getValidHandle<std::vector<recob::Hit>>` / `<...SpacePoint>>` (L166-167) | event retrieval | boundary | module, unchanged |
| 6 | `art::FindOneP<recob::Wire> channelHitWires` (L172) | association read, needed for output | boundary: kept as `FindOneP` (its `art::Ptr<recob::Wire>` is fed straight into `HitCollectionCreator::emplace_back`, an output association) | module, unchanged |
| 7 | `recob::HitCollectionCreator hcol(...)` (L176-180) | collection helper / product+assns output | boundary | module, unchanged |
| 8 | `std::vector<art::Ptr<recob::Hit>> eventHits; art::fill_ptr_vector(eventHits, hitsHandle);` (L186-187) | art::Ptr, convenience | **convenience, removed**: `eventHits[i].key() == i` always (built from one handle, no filtering), so every use was read access or an index. Replaced by `*hitsHandle` (`std::vector<recob::Hit> const&`) plus plain `size_t` indices. | gone; call sites use `*hitsHandle` directly |
| 9 | `art::FindManyP<recob::SpacePoint> spFromHit` (L189) | ptr-assns, needed for chaining | boundary, kept as `FindManyP`: `art::Ptr<recob::SpacePoint>::key()` is used both to look up `spToTPC` and to attribute output associations | module, unchanged construction; resolved into plain `spacePointsPerHit`/`spKeysPerHit` before being passed to the algorithm |
| 10 | `art::FindManyP<recob::Hit> hitsFromSp` (L190) | ptr-assns | boundary, **kept as `FindManyP`** (round 1 had changed this to `art::FindMany<recob::Hit>` as a convenience simplification -- only `h->SignalType()`/`h->WireID()` are read, `.key()` is never used on these hits, so `FindMany` looked correct by `references/separation.md`'s own rule. Round 2 reverted this per verifier finding F3: `art::FindMany<T>` resolves an association whose product is unavailable into a silent `nullptr` (canvas `detail/IPRHelper.h`'s `item ? item.get() : nullptr`), which `BuildSpacePointToTPCMap` would then dereference unconditionally -- undefined behaviour instead of the original's `art::Exception(errors::ProductNotFound)`, thrown from `art::Ptr<T>::operator->()`/`.get()` (canvas `Ptr.h`) when a `FindManyP` result is dereferenced. See section 4.) | module `produce()`, `FindManyP` (unchanged from base); resolved to `recob::Hit const*` via `.get()` at the boundary before being passed to `BuildSpacePointToTPCMap` |
| 11 | `art::ServiceHandle<detinfo::DetectorPropertiesService const>()->DataFor(evt)` (L192) | service (data) | boundary; already passed as an explicit `detinfo::DetectorPropertiesData const&` parameter to `resolveUnassigned` in the original code, unchanged | module, unchanged |
| 12 | spacepoint→TPC map loop using `hitsFromSp.at(i)` (L193-212), inline in `produce()` | domain computation reaching into a `FindManyP`/`FindMany` result | **extracted**: moved into `dune::BuildSpacePointToTPCMap`, taking a plain `std::vector<std::vector<recob::Hit const*>>` resolved at the boundary | `DisambigFromSpacePointsAlg.cxx` |
| 13 | `int runOnSpacePoints(eventHits, spFromHit, spToTPC, ...)` (L73-80, L278-363), a **private member function whose own parameter list contained `art::FindManyP<recob::SpacePoint> const&`** | algorithm, with an art type leaking into its signature | **extracted and re-parameterised**: `art::FindManyP` parameter replaced by plain `spacePointsPerHit`/`spKeysPerHit` per `references/larsoft-boundary-patterns.md` ("Associations read by the module": pass keys alongside pointers) | `DisambigFromSpacePointsAlg.h/.cxx`, function `RunOnSpacePoints` |
| 14 | `int resolveUnassigned(...)` (L82-89, L365-467) | algorithm | extracted verbatim (see section 4) | `DisambigFromSpacePointsAlg.h/.cxx`, function `ResolveUnassigned` |
| 15 | `void assignFirstAllowedWire(...)` (L91-95, L469-493) | algorithm | extracted verbatim | `DisambigFromSpacePointsAlg.h/.cxx`, function `AssignFirstAllowedWire` |
| 16 | `void assignEveryAllowedWire(...)` (L97-101, L495-516) | algorithm | extracted verbatim | `DisambigFromSpacePointsAlg.h/.cxx`, function `AssignEveryAllowedWire` |
| 17 | `geo::WireReadoutGeom const* fWireReadoutGeom` (L104) | service (data) | boundary member kept as-is per `references/larsoft-boundary-patterns.md` ("the module may keep that member; the algorithm receives the reference") | module, unchanged; dereferenced at each algorithm call |
| 18 | `mf::LogWarning`/`mf::LogInfo` in `produce()` (L222, L227, L232) | logging | boundary, unchanged (not inside extracted code) | module, unchanged |
| 19 | `mf::LogWarning` inside `runOnSpacePoints`/`resolveUnassigned`/`assignFirstAllowedWire` (L295, L387, L417, L479, L491) | logging, deep in algorithm | **transitional** | `DisambigFromSpacePointsAlg.cxx` L53, L149, L180, L243, L256, each marked `// PHLEX-TRANSITIONAL: logging` |
| 20 | `cet::exception` in the constructor (L136) | exception | boundary (constructor, never extracted) | module, unchanged |
| 21 | `art::PtrMaker<recob::Hit>`, `assns->addSingle(...)` (L234-269) | ptr-assns output | boundary, unchanged in shape; indices are now plain `size_t` instead of `.key()` on a removed `art::Ptr` | module, unchanged logic, `hitsHandle->at(key)` replaces `*(eventHits[key])` |
| 22 | `#include "messagefacility/MessageLogger/MessageLogger.h"`, needed only because of item 19 | framework header | transitional; round 1 put this in the public header (`DisambigFromSpacePointsAlg.h`), so every includer inherited the messagefacility dependency even though only the `.cxx` uses `mf::` (verifier F4). Round 2 moved it. | `DisambigFromSpacePointsAlg.cxx` L6, marked `// PHLEX-TRANSITIONAL: logging` |

## 3. Extracted algorithm API

```cpp
namespace dune {

  typedef std::map<unsigned int, std::vector<size_t>> plane_keymap;
  typedef std::map<unsigned int, plane_keymap> tpc_plane_keymap;
  typedef std::map<unsigned int, tpc_plane_keymap> cryo_tpc_plane_keymap;

  struct DisambigFromSpacePointsCfg {
    float maxDistance;
    std::vector<size_t> excludeTPCs;
  };

  struct DisambigStats {
    int nHits[3] = {0, 0, 0};
    int nMissedBySpacePoints[2] = {0, 0};
    int nMissedByNeighbors[2] = {0, 0};
  };

  std::unordered_map<size_t, size_t> BuildSpacePointToTPCMap(
    std::vector<std::vector<recob::Hit const*>> const& hitsPerSpacePoint);

  int RunOnSpacePoints(geo::WireReadoutGeom const& wireReadout,
                       std::vector<recob::Hit> const& eventHits,
                       std::vector<std::vector<recob::SpacePoint const*>> const& spacePointsPerHit,
                       std::vector<std::vector<size_t>> const& spKeysPerHit,
                       std::unordered_map<size_t, size_t> const& spToTPC,
                       std::unordered_map<size_t, geo::WireID>& assignments,
                       cryo_tpc_plane_keymap& indHits,
                       std::vector<size_t>& unassigned,
                       DisambigStats& stats);

  int ResolveUnassigned(DisambigFromSpacePointsCfg const& cfg,
                        geo::WireReadoutGeom const& wireReadout,
                        detinfo::DetectorPropertiesData const& detProp,
                        std::unordered_map<size_t, geo::WireID>& assignments,
                        std::vector<recob::Hit> const& eventHits,
                        cryo_tpc_plane_keymap& allIndHits,
                        std::vector<size_t>& unassigned,
                        size_t nNeighbors,
                        DisambigStats& stats);

  void AssignFirstAllowedWire(DisambigFromSpacePointsCfg const& cfg,
                              geo::WireReadoutGeom const& wireReadout,
                              std::unordered_map<size_t, geo::WireID>& assignments,
                              std::vector<recob::Hit> const& eventHits,
                              std::vector<size_t> const& unassigned);

  void AssignEveryAllowedWire(DisambigFromSpacePointsCfg const& cfg,
                              geo::WireReadoutGeom const& wireReadout,
                              std::unordered_map<size_t, std::vector<geo::WireID>>& assignments,
                              std::vector<recob::Hit> const& eventHits,
                              std::vector<size_t> const& unassigned);
}
```

- **Inputs and where the module gets each one**: `eventHits` from `evt.getValidHandle<std::vector<recob::Hit>>(fHitModuleLabel)`, dereferenced; `spacePointsPerHit`/`spKeysPerHit` resolved at the boundary from `art::FindManyP<recob::SpacePoint> spFromHit(hitsHandle, evt, fSpModuleLabel)`; `hitsPerSpacePoint` resolved from `art::FindManyP<recob::Hit> hitsFromSp(spHandle, evt, fSpModuleLabel)` (both `FindManyP`, each resolved to a raw pointer via `.get()` at the boundary -- see section 4/F3 for why `hitsFromSp` is `FindManyP`, not `FindMany`); `wireReadout` from the module's `fWireReadoutGeom` member (set once in the constructor from `art::ServiceHandle<geo::WireReadout>()->Get()`); `detProp` from `art::ServiceHandle<detinfo::DetectorPropertiesService const>()->DataFor(evt)`; `cfg` built once in the constructor directly from FHiCL (`config().MaxDistance()`/`config().ExcludeTPCs()`; round 2 dropped the round-1 `fMaxDistance`/`fExcludeTPCs` duplicate members per F7); `nNeighbors` from `fNumNeighbors` (FHiCL).
- **Outputs and how the module publishes each one**: `assignments` (`hitToWire`/`hitToNWires`) drive the loop in `produce()` that builds `recob::HitCreator`/`hcol.emplace_back`/`art::Assns<recob::Hit, recob::SpacePoint>`, unchanged from the original. `stats` is copied into the module's `fNHits`/`fNMissedBySpacePoints`/`fNMissedByNeighbors` members (which the TTree branches are bound to) only when `fMonitoringPlots` is set, then `fTree->Fill()`; `fNMissedByNeighbors` specifically is copied only when `fUseNeighbors` is also set (round 2, F1), matching the original leaving that member entirely unwritten when `UseNeighbors` is false. `n` (undisambiguated-hit counts) drives the two `mf::LogInfo` lines exactly as before.
- **Free function or class, and why**: five free functions, mirroring the original four private member functions plus the previously-inline spacepoint→TPC loop. A class was not used because the functions share only `wireReadout`/`cfg`, both cheap to pass by reference per call (no expensive setup to amortise), and keeping them as free functions makes each one's real inputs explicit rather than hidden behind a constructor.
- **Re-entrancy**: all five functions are re-entrant (no mutable statics, no ROOT globals, no random engine); each takes only its own by-reference/by-value arguments and out-parameters. `check_purity.py` raised no `mutable`/`static` warnings.

## 4. Behaviour preservation

- **Code moved verbatim** (original file:line → new file:line, `dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx`):
  - spacepoint→TPC loop, original `produce()` L193-212 → `BuildSpacePointToTPCMap` L8-32 (loop body unchanged; `hitsFromSp.at(i)` → `hitsPerSpacePoint[i]`, `h->` unchanged since both are pointer types).
  - `runOnSpacePoints` body, original L286-362 → `RunOnSpacePoints` L44-122 (arithmetic, control flow, and the `tpcBestWire`/`tpcScore` best-match selection are byte-for-byte identical; only the hit/space-point access syntax changed, see below).
  - `resolveUnassigned` body, original L374-466 → `ResolveUnassigned` L135-229 (identical, including the `distBuff`/`dwMax`/`ddMax` neighbor-distance-in-wires-and-ticks computation and the `//` commented-out `std::abs(hitWire - ...)` line, kept as a comment exactly as in the original).
  - `assignFirstAllowedWire` body, original L475-492 → `AssignFirstAllowedWire` L238-257.
  - `assignEveryAllowedWire` body, original L501-515 → `AssignEveryAllowedWire` L266-280, including the original `// add warning here` comment (see suspected issues below).
- **Mechanical edits**:
  - `fWireReadoutGeom->` (pointer member) → `wireReadout.` (reference parameter) throughout.
  - `fMaxDistance` / `fExcludeTPCs` (implicit `this->` member reads) → `cfg.maxDistance` / `cfg.excludeTPCs` (explicit parameter).
  - `fNHits[i]++` / `fNMissedBySpacePoints[i]++` / `fNMissedByNeighbors[i]++` → `stats.nHits[i]++` / `stats.nMissedBySpacePoints[i]++` / `stats.nMissedByNeighbors[i]++`.
  - `const art::Ptr<recob::Hit> & hit = eventHits[i];` then `hit->X()` → `recob::Hit const& hit = eventHits[i];` then `hit.X()` (`.` replaces `->`, per `references/art-ptr-removal.md` "Method signatures taking `art::Ptr` by const reference").
  - `hit.key()` (always equal to the loop index `i`, since `eventHits` was built by `fill_ptr_vector` from a single handle with no filtering) → the index `i` (in `RunOnSpacePoints`) or `key` (in the other three functions, unchanged name, now a plain `size_t` instead of an `art::Ptr<recob::Hit>::key()` result).
  - `for (const auto & sp : spFromHit.at(hit.key()))` iterating `art::Ptr<recob::SpacePoint>`, using `sp.key()` and `sp->position()` → parallel iteration `for (size_t s = 0; s < spKeys.size(); ++s)` over `spKeysPerHit[i]`/`spacePointsPerHit[i]`, using `spKeys[s]` and `spacePoints[s]->position()` (still `->`, since `spacePoints[s]` is `recob::SpacePoint const*`).
  - `hitsFromSp.at(i)` (`std::vector<art::Ptr<recob::Hit>>`, only ever read via `h->`) → resolved at the boundary into `std::vector<recob::Hit const*>` via `h.get()` per entry (`hitsFromSp` itself stays `art::FindManyP<recob::Hit>`, unchanged type from base -- see F3 below); no syntax change inside `BuildSpacePointToTPCMap` since both `art::Ptr<recob::Hit>` and `recob::Hit const*` use `->`.
  - `recob::HitCreator new_hit(*(eventHits[key]), wid);` → `recob::HitCreator new_hit(hitsHandle->at(key), wid);`.
  - `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)` (identity substitution, since `eventHits[key].key() == key`).
- **Intentional deviations**: none (no type changes, no reordering, no early-return changes,
  no product-output changes). Round 1 had introduced two undocumented deviations from
  boundary-code changes that were not "moving code" -- a TTree-branch write pattern change
  (F1) and a failure-mode change on unavailable associated products (F3) -- both reverted in
  round 2; see items below and "Round 2 changes".
- **Suspected pre-existing issues noticed and not fixed**:
  1. `AssignEveryAllowedWire` (`"repeat"` mode) has `// add warning here` where `AssignFirstAllowedWire`'s equivalent branch calls `mf::LogWarning(...) << "None of wires is allowed for this hit???"`. The `"repeat"` mode silently drops a hit with no allowed wire instead of warning. Present in the original at L505; preserved verbatim, comment kept (`DisambigFromSpacePointsAlg.cxx` L270).
  2. `assignFirstAllowedWire`/`assignEveryAllowedWire` do not consult `fExcludeTPCs` consistently with `resolveUnassigned`: `resolveUnassigned` skips excluded TPCs entirely when scoring neighbors, but `assignFirstAllowedWire` picks "the first allowed wire" only among `cwids` in **channel order**, which is not guaranteed to correlate with proximity to any already-resolved hit; this looks intentional (a last-resort fallback) rather than a bug, but is worth a physicist's confirmation before Phlex binding.
  3. `BuildSpacePointToTPCMap`'s `tpc` variable is declared `size_t` but assigned from `geo::WireID::InvalidID` (a `WireID_t`, i.e. `unsigned int`; `geo_types.h:422-428` -- corrected from round 1's "`CryostatID_t`", F6, though the conclusion is the same since both are `unsigned int`) and compared/assigned via `h->WireID().TPC` (also `unsigned int`); pre-existing implicit narrowing/widening, unchanged.
  4. `ResolveUnassigned`'s `geo::PlaneID const planeID(cryo, tpc, plane);` passes `cryo` (`unsigned int`), `tpc` (`size_t`), `plane` (`unsigned int`) positionally into a constructor typed `(CryostatID_t, TPCID_t, PlaneID_t)`; same implicit conversions as issue 3, pre-existing, unchanged.
  5. **(added round 2, F1/F5)** When `UseNeighbors` is false, the constructor never initialises `fNMissedByNeighbors[2]`, and neither the original nor this extraction ever writes it in that configuration. With `MonitoringPlots: true` and `UseNeighbors: false`, the `hitstats` TTree's `fNMissedByNeighbors` branch holds indeterminate memory content, constant for the life of the job (nothing else touches those bytes either). Base: constructor L122-133 never initialises the array; `resolveUnassigned` (the only writer) only runs `if (fUseNeighbors)` (base L224). Not fixed, to keep this pass a pure move of code; see "Round 2 changes" for how the extraction now reproduces this exactly instead of writing 0.
  6. **(added round 2, F5)** `fNHits`/`fNMissedBySpacePoints`/`fNMissedByNeighbors` are indexed by `plane` (an `unsigned int` read from `geo::WireID`/`geo::PlaneID`) with no bounds check against the arrays' sizes (3 and 2 respectively). A non-collection hit on plane 2 or higher (`fNHits`) or plane 2+ (`fNMissedBySpacePoints`/`fNMissedByNeighbors`, sized for 2 induction planes) writes past the end of the array -- undefined behaviour. Both the base and this extraction share the exact same member/array layout and indexing, so the effect (if any, for a >2-induction-plane detector) is identical. Base: L305, L310, L356, L455; new: `DisambigFromSpacePointsAlg.cxx` L63, L70, L116 (via `stats.nMissedBySpacePoints`), and `ResolveUnassigned`'s `stats.nMissedByNeighbors[plane]++` (L218 in the current file). Not fixed.
  7. **(added round 2, F5)** A hit whose channel maps to no wire at all (`cwids.empty()`) is warned about and skipped (`continue`) in `RunOnSpacePoints`/`ResolveUnassigned`/`AssignFirstAllowedWire`, without incrementing any of `fNHits`/`fNMissedBySpacePoints`/`fNMissedByNeighbors` for that hit -- it is silently absent from every per-event count, not just left unresolved. Base L295 (and the corresponding lines in the other three functions); new `DisambigFromSpacePointsAlg.cxx` L59 (and correspondingly in `ResolveUnassigned`/`AssignFirstAllowedWire`/`AssignEveryAllowedWire`). Pre-existing, unchanged, not fixed.

## 5. Framework-visible contract

```
$ python3 art_inventory.py --repo <worktree> contract-diff \
    --before git:ffc89e0d9:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc \
    --after  dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc
contract unchanged (13 items)
```

Unchanged (13 items, using the current kit's `art_inventory.py`, fixed since round 1 per
KIT_FEEDBACK.md to also see `declare_products`): module name, base class, the one `callback
produce`, all 8 FHiCL parameters (names, types, and — where present — defaults), the one
explicit `produces<art::Assns<recob::Hit,recob::SpacePoint>>()`, and (new in round 2's tool)
`declare_products recob::HitCollectionCreator(producesCollector(),"",true,false)`.

Round 1 note (superseded): round 1's kit snapshot's `contract` could not see the
`declare_products` call at all, so round 1 recorded a manual diff of the constructor as a
caveat. The current tool sees and matches it directly, so that manual caveat is no longer
needed, though it remains true: the call and its three literal arguments (`""`, `true`,
`false`) are untouched between before and after.

## 6. Transitional items

| file:line | What | Why it stays | How it goes away |
|---|---|---|---|
| `DisambigFromSpacePointsAlg.cxx:6` | `#include "messagefacility/MessageLogger/MessageLogger.h"` | Needed only because the five diagnostic `mf::LogWarning` calls below stay inline in the algorithm (see `references/larsoft-boundary-patterns.md`, "Logging and exceptions": messages deep inside the algorithm keep `mf::Log*` marked transitional rather than being deleted or hoisted). Round 2 (F4): moved here from `DisambigFromSpacePointsAlg.h`, which had no `mf::` use of its own and so needlessly handed the messagefacility dependency to every includer. | Once Phlex settles on a logging facility (spdlog per the guide), replace these five calls and drop the include. |
| `DisambigFromSpacePointsAlg.cxx:59` | `mf::LogWarning("DisambigFromSpacePoints") << "No wires for this channel???";` in `RunOnSpacePoints` | Diagnostic for a channel with no wires at all; fires deep inside the per-hit loop, not summarisable at the boundary without restructuring the return value. | Replace with a framework-agnostic logging call (or accumulate as a diagnostic counter returned to the boundary) once Phlex logging lands. |
| `DisambigFromSpacePointsAlg.cxx:155` | Same message, in `ResolveUnassigned` | Same reasoning. | Same. |
| `DisambigFromSpacePointsAlg.cxx:186` | `mf::LogWarning(...) << "Did not find resolved wire id.";` in `ResolveUnassigned` | Same reasoning; fires inside the neighbor-scoring inner loop. | Same. |
| `DisambigFromSpacePointsAlg.cxx:249` | `"No wires for this channel???"` in `AssignFirstAllowedWire` | Same reasoning. | Same. |
| `DisambigFromSpacePointsAlg.cxx:262` | `"None of wires is allowed for this hit???"` in `AssignFirstAllowedWire` | Same reasoning. | Same. |

`check_purity.py` summary (current kit, fixed since round 1 per KIT_FEEDBACK.md's include
line-number finding): `PASS: 0 error(s)` across both algorithm files; 6 transitional items (5
`mf::LogWarning` plus the include, now all in the `.cxx`), 0 other warnings. Full output:

```
$ python3 check_purity.py dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx
dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h: 0 error(s), 0 warning(s), 0 transitional
dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx: 0 error(s), 0 warning(s), 6 transitional
  TRANS L6     #include messagefacility/MessageLogger/MessageLogger.h  (art MessageLogger)
  TRANS L59    mf::LogWarning  (MessageLogger)
  TRANS L155   mf::LogWarning  (MessageLogger)
  TRANS L186   mf::LogWarning  (MessageLogger)
  TRANS L249   mf::LogWarning  (MessageLogger)
  TRANS L262   mf::LogWarning  (MessageLogger)

PASS: 0 error(s) across 2 file(s)
```

Round 1 note (superseded): round 1's kit snapshot reported the header's include at `L29`
(the marker comment's own line, one above the real `#include` at `L30`) due to a tool
line-attribution bug, documented in KIT_FEEDBACK.md. The current kit's `check_purity.py`
reports the correct line directly (`L6` above, verified against the file), and F4 also moved
the include out of the header entirely, so that bug no longer affects this file either way.

## 7. Phlex binding plan (not implemented)

| Extracted piece | Node | Inputs (creator / layer / suffix) | Output suffix | Layer | Concurrency | Blockers |
|---|---|---|---|---|---|---|
| `BuildSpacePointToTPCMap` | `transform` | `hits_per_spacepoint` (derived below) | `sp_to_tpc` | event | unlimited | none |
| `RunOnSpacePoints` | `transform` | `wire_readout` (job, `provide`d geometry), `hits` (creator=HitModuleLabel module, event, suffix ""), `spacepoints_per_hit`/`spkeys_per_hit` (derived), `sp_to_tpc` (from above) | `hit_to_wire`, `ind_hits`, `unassigned` (3 outputs from one node — a current Phlex gap, see below) | event | unlimited | Phlex nodes currently return one product family; this function's 4 out-parameters (`assignments`, `indHits`, `unassigned`, plus the returned diagnostic count) need either a single aggregate struct product or splitting into per-output nodes. |
| `ResolveUnassigned` | `transform` (conditional on `UseNeighbors`) | `wire_readout`, `det_props` (event layer -- `DataFor(evt)` is called once per event, not once per job; corrected from round 1's "job/event", F8), `hit_to_wire`/`ind_hits`/`unassigned` from `RunOnSpacePoints` | updated `hit_to_wire`/`unassigned` | event | unlimited | Same "several outputs, some mutated in place" shape as above; a predicate/optional-node mechanism for `UseNeighbors` (check current API). Also (F8): `allIndHits[cryo][tpc][plane]` (`DisambigFromSpacePointsAlg.cxx` L171) inserts an empty entry via `operator[]` when a key is absent, so the function needs `cryo_tpc_plane_keymap&` (non-const) even though it never removes entries `RunOnSpacePoints` put there. A Phlex `transform` gets const inputs, so binding needs a `find`-based lookup instead (no behaviour change, since a missing key already means "no neighbours yet" either way) -- not yet reflected in this row's inputs column. |
| `AssignFirstAllowedWire` / `AssignEveryAllowedWire` | `transform`, selected by `MoveLeftovers` (one of the two runs) | `hit_to_wire`/`hit_to_n_wires`, `unassigned` | final `hit_to_wire`/`hit_to_n_wires` | event | unlimited | `MoveLeftovers` is a 3-way FHiCL string switch (`"repeat"`/`"first"`/drop); Phlex has no documented "pick one of N nodes by job configuration" idiom yet in the guide at this commit — plan as configuration-time node selection in the registration file, akin to `GausHitFinder`'s `filter_hits` bool but 3-valued. |
| output association/hit building (module `produce()` tail) | `observe`-adjacent boundary work: builds `art::Assns`/`recob::Hit` from indices | `hit_to_wire`, `hit_to_n_wires`, `hits`, `channel_hit_wires`, `spacepoints_per_hit` | `disambiguated_hits`, `hit_spacepoint_assns` | event | serial (persistable associations not yet supported per the guide, section "Transitional binding issues") | Associations are not yet a first-class Phlex output (guide, 2026-09 gaps list); this whole tail stays boundary-only until that lands. |
| `hitsPerSpacePoint`/`spacePointsPerHit`/`spKeysPerHit` construction (module `produce()`, boundary loops) | `provide`/`transform` shims resolving `FindMany`/`FindManyP` results into plain vectors | `hits`, `spacepoints`, module's association labels | `hits_per_spacepoint`, `spacepoints_per_hit`, `spkeys_per_hit` | event | unlimited | Needs Phlex's answer for "associations read by the module" (guide gap: "persistable associations"); until then this is exactly the kind of boundary-resolution code that stays in an art shim per `references/larsoft-boundary-patterns.md`. |

Overall shape for binding: this module is naturally **several** nodes (a fan of small
`transform`s feeding each other sequentially, matching the "provide plus transform" and
"several kinds of work → several nodes" guidance in `references/binding-crosswalk.md`), not
one. The biggest blocker is that four of the five extracted functions mutate 2-3 output
parameters at once (`assignments` + `indHits` + `unassigned`, or `assignments` alone but keyed
differently for `hitToWire` vs `hitToNWires`) rather than returning one clean product; before
binding, a small redesign bundling these into one result struct per node is recommended
(mechanical, not physics-changing, so it could be a pass-1.5 step rather than binding itself).

## 8. Validation plan

- **FHiCL jobs** (round 2, F2: cover every configuration branch, not just one): run
  `standard_disambigfromsp` (from `hitfindermodules_dune.fcl`) on a small ProtoDUNE-SP or 35t
  sample that already has `gaushit` and `reco3d` (SpacePointSolver) products, once per
  combination of `UseNeighbors` (`true`/`false`) and `MoveLeftovers` (`"first"`/`"repeat"`/
  anything else, to hit the "dropped" branch), i.e. at least 6 jobs; run at least one of them
  with `MonitoringPlots: true` and `UseNeighbors: false` specifically, to check finding F1/issue
  5 (the indeterminate `fNMissedByNeighbors` read) reproduces identically rather than being
  masked by a coincidental zero.
- **Products to compare, in exact collection order, not sorted** (round 2, F2 -- round 1's
  plan wrongly called for sorting by original hit index "because multithreading changes
  order"; that reasoning does not apply here: this is one art module instance running
  serially, `hitToWire.reserve(hitsHandle->size())` uses the same value as the original
  `eventHits.reserve(...)`, and the insertion sequence into `hitToWire`/`hitToNWires` is
  unchanged, so with the same standard library the `std::unordered_map` iteration order --
  and therefore the output `recob::Hit` collection order and the `art::Assns<recob::Hit,
  recob::SpacePoint>` pair order -- should be identical, not just equivalent, between base and
  extracted. Compare in exact order and treat any difference as a finding; a sorted comparison
  is a weaker fallback diagnostic only, never the primary check): the output `recob::Hit`
  collection (values: channel, wire ID, plane, peak time, all copied from the input hit plus
  the new `geo::WireID`) and the `art::Assns<recob::Hit, recob::SpacePoint>` (pair membership
  **and order**), before vs. after, on identical input, for every job above.
  With `MonitoringPlots: true`, additionally dump the `hitstats` TTree (`fNHits`,
  `fNMissedBySpacePoints`, `fNMissedByNeighbors`) per event; these three arrays are exactly
  what moved from members to `DisambigStats`, so they are the most direct regression check for
  the highest-risk edit in this extraction (see F1/"Round 2 changes" for how
  `fNMissedByNeighbors` is now written only when `UseNeighbors` is true, same as base).
- **Unit-test idea for the algorithm**: hand-build 3-4 `recob::Hit`s (2 induction, 1
  collection, on adjacent channels) and 1-2 `recob::SpacePoint`s at hand-picked positions,
  call `RunOnSpacePoints` directly with a real (or a minimal fake) `geo::WireReadoutGeom`, and
  check `assignments`/`indHits`/`unassigned` against hand-computed expectations. This requires
  a concrete detector geometry (even a tiny one) since `WireReadoutGeom` has no trivial
  mock — likely the biggest practical obstacle to a fast unit test for this particular module.

## 9. Checklists

Guide extraction checklist, with evidence:

1. **Core algorithm describable without framework callbacks**: yes — section 1 above describes
   it with no mention of `produce()`/services/FHiCL.
2. **All real inputs in the signature or constructor**: yes — every value each function reads
   is a parameter (`DisambigFromSpacePointsAlg.h` L81-118); verified by re-reading each
   function body in `DisambigFromSpacePointsAlg.cxx` line by line against its parameter list
   (no remaining `this->`/implicit-member reads — the original functions were free-standing
   after removing the class's `private:` members, since none of `runOnSpacePoints`,
   `resolveUnassigned`, `assignFirstAllowedWire`, `assignEveryAllowedWire` used any *other*
   inherited `art::EDProducer` state).
3. **All outputs as return values or explicit output objects**: yes — `assignments`,
   `indHits`, `unassigned`, `stats` are all output parameters; `RunOnSpacePoints`/
   `ResolveUnassigned` additionally return the undisambiguated-hit count via `return`,
   matching the original.
4. **Configuration collected outside the algorithm**: yes — `DisambigFromSpacePointsCfg` is
   built once in the module constructor (`DisambigFromSpacePoints_module.cc` L103,
   `fCfg{config().MaxDistance(), config().ExcludeTPCs()}` -- round 2 dropped the round-1
   `fMaxDistance`/`fExcludeTPCs` duplicate members per F7, so this now reads directly off
   `config()`), no FHiCL type appears in the algorithm files (`check_purity.py`: 0 errors).
5. **Remaining framework assumptions documented as transitional**: yes — section 6, 6 items,
   all `mf::LogWarning`/its include.

Separation checks:

- **`ServiceHandle` only in the module**: yes — `grep -c ServiceHandle
  DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` = 0; both occurrences of
  `art::ServiceHandle` in the module are in the constructor and `produce()` boundary code.
- **Every service-derived value passed explicitly**: yes — `wireReadout` and `detProp` are
  parameters everywhere they're used in the algorithm files.
- **No helper receives the event or a handle**: yes — no `art::Event`, `art::Handle`, or
  `art::ValidHandle` type appears in `DisambigFromSpacePointsAlg.h`/`.cxx`
  (`check_purity.py`'s event-product-retrieval token check: 0 hits).
- **No event-scoped data cached across events**: yes for the algorithm files (they cache
  nothing; every call gets fresh arguments). In the module, `fRun`/`fEvent`/`fNHits`/
  `fNMissedBySpacePoints`/`fNMissedByNeighbors`/`fTree` are still module members, but this is
  unavoidable and intentional: `TTree::Branch` binds by address in the constructor, so the
  bound variables must be members that outlive one `produce()` call. `fRun`/`fEvent` are
  overwritten at the top of every `produce()`; `fNHits`/`fNMissedBySpacePoints` are overwritten
  immediately before `Fill()` on every call where `fMonitoringPlots` is set;
  `fNMissedByNeighbors` is overwritten there only when `fUseNeighbors` is also set (F1 --
  matching the original, which leaves it unwritten, i.e. genuinely holding stale/indeterminate
  content across every event of a `UseNeighbors: false` job, not "cached" in the sense of
  being read back by later logic, just never touched). This is the "Histograms and TTrees"
  boundary pattern from `references/larsoft-boundary-patterns.md`, not a leftover
  scratch-member problem.

Purity check summary (`check_purity.py`): **PASS**, 0 errors / 0 warnings / 6 transitional
(5 `mf::LogWarning` + 1 `#include`), all in `DisambigFromSpacePointsAlg.cxx` since round 2's
F4 fix (`DisambigFromSpacePointsAlg.h` now has 0 transitional items of its own).

## Round 2 changes

Verifier: `VERIFICATION.md`, FAIL, 0 blocker / 1 major / 5 minor / 3 nit. All re-checks below
were run against the current kit (`$KIT`, scripts fixed since round 1
per KIT_FEEDBACK.md's findings on include line numbers, member state in helper functions,
`declare_products` in the contract, and `scan --rev`).

| Finding | Resolution | file:line |
|---|---|---|
| F1 (major) | Fixed. `produce()` now copies `stats.nMissedByNeighbors` into `fNMissedByNeighbors` only `if (fUseNeighbors)`, matching the original's exact write pattern (the array is otherwise never touched, reproducing its pre-existing indeterminate-value read rather than replacing it with 0). Header comment corrected; new "suspected pre-existing issue" 5 added; section 2 item 4, section 3, and the "no event-scoped data cached" separation check updated to describe the conditional copy. | `DisambigFromSpacePoints_module.cc:286-289` (the `if (fUseNeighbors)` guard); comment `DisambigFromSpacePointsAlg.h:56-61`; notes: section 2 item 4, section 3 "Outputs", section 4 issue 5, section 9 |
| F2 (minor) | Fixed. Section 8 validation plan rewritten to require exact-order comparison of the output hit collection and `Assns<Hit,SpacePoint>` pairs (sorted comparison demoted to a fallback diagnostic only), and to run every `UseNeighbors` x `MoveLeftovers` combination, not just one job. | notes: section 8 |
| F3 (minor) | Fixed. Reverted `hitsFromSp` from round 1's `art::FindMany<recob::Hit>` back to `art::FindManyP<recob::Hit>` (matching base exactly), resolved into `std::vector<recob::Hit const*>` at the boundary via `.get()` per entry, mirroring `spFromHit`'s existing treatment. Chose "keep FindManyP" over "check for null and throw" because `art::Ptr<T>::get()` on a `FindManyP` result already throws `art::Exception(errors::ProductNotFound)` for a valid-keyed-but-unavailable product (canvas `Ptr.h`, `operator->()` via `get()`'s `isNull() ? nullptr : operator->()`), reproducing the original's exact failure mode with no new logic; `art::FindMany<T>` cannot do this because it deliberately resolves such cases to a silent `nullptr` (canvas `detail/IPRHelper.h`, `item ? item.get() : nullptr`) before the caller ever sees a pointer. Justification and the residual (accepted, documented) eagerness difference recorded in section 2 item 10 and section 4. | `DisambigFromSpacePoints_module.cc:156-169` (comment), `:171` (`FindManyP` declaration), `:180-189` (boundary resolution loop); notes: section 2 item 10, section 3, section 4 |
| F4 (minor) | Fixed. Moved `#include "messagefacility/MessageLogger/MessageLogger.h"` and its `// PHLEX-TRANSITIONAL: logging` marker from the header to the `.cxx` (the only translation unit that uses `mf::`). | `DisambigFromSpacePointsAlg.h:29-34` (include removed, comment left explaining where it went); `DisambigFromSpacePointsAlg.cxx:5-6` (marker + include added); notes: section 2 item 22, section 6 |
| F5 (minor) | Fixed. Added three "suspected pre-existing issues" to section 4: (5) the indeterminate `fNMissedByNeighbors` read now explicitly recorded (cross-referenced from F1); (6) unchecked `plane` indexing into `fNHits`/`fNMissedBySpacePoints`/`fNMissedByNeighbors`; (7) hits with no wire for their channel are silently absent from every counter, not just left unresolved. | notes: section 4, issues 5-7 |
| F6 (minor) | Fixed. Corrected: section 2 item 2's line reference (module ctor is L123, not L147 -- L147 was the *base* file's line); section 4 issue 3's type name (`geo::WireID::InvalidID` is a `WireID_t`, not `CryostatID_t`; conclusion unchanged since both are `unsigned int`); "Module selection"'s CMake description (`art_make` globs new `.cxx` files; new headers need no listing because `install_headers()` installs the directory, not because `art_make` globs headers). | notes: "Module selection", section 2 item 2, section 4 issue 3 |
| F7 (nit) | Fixed (judged trivial: `fMaxDistance`/`fExcludeTPCs` were read nowhere except to build `fCfg`). Dropped the two duplicate members; `fCfg` is now built directly from `config().MaxDistance()`/`config().ExcludeTPCs()` in the constructor's initialiser list. | `DisambigFromSpacePoints_module.cc:80-90` (members removed, comment updated), `:97-103` (initialiser list); notes: "Module selection" not affected, section 3 and section 9 checklist item 4 updated |
| F8 (nit) | Fixed (notes only, no code change requested). Added the `find`-vs-`operator[]`/non-const-parameter blocker and corrected `det_props`'s layer from "job/event" to "event" in the `ResolveUnassigned` binding-plan row. | notes: section 7, `ResolveUnassigned` row |
| F9 (nit) | Fixed (notes only). Added a "Build note for hand-off" paragraph: reconfigure needed for `art_make` to see the new `.cxx`; the algorithm links into `HitFinderDUNE`, which already links `art`/`fhiclcpp`/`messagefacility` for its other sources, so "framework-free" is source-level only until a binding-stage library split. | notes: "Module selection" (new paragraph after the shortlist table) |

Re-run automated checks (current kit):

```
$ python3 check_purity.py dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx
dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h: 0 error(s), 0 warning(s), 0 transitional
dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx: 0 error(s), 0 warning(s), 6 transitional
  TRANS L6     #include messagefacility/MessageLogger/MessageLogger.h  (art MessageLogger)
  TRANS L59    mf::LogWarning  (MessageLogger)
  TRANS L155   mf::LogWarning  (MessageLogger)
  TRANS L186   mf::LogWarning  (MessageLogger)
  TRANS L249   mf::LogWarning  (MessageLogger)
  TRANS L262   mf::LogWarning  (MessageLogger)
PASS: 0 error(s) across 2 file(s)

$ python3 art_inventory.py --repo <worktree> contract-diff \
    --before git:ffc89e0d9:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc \
    --after  dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc
contract unchanged (13 items)
```

`contract.after.txt` and `extraction.patch` regenerated against this state.
