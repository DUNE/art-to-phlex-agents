# Code review: DisambigFromSpacePoints extraction (v1)

Reviewer: phlex-reviewer. Worktree `<worktree>`, base `5d619357`.
Read independently of VERIFICATION.md. MIGRATION_NOTES.md was consulted only after the code
had been read.

Files reviewed in full:

- `dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.h` (new)
- `dunereco/HitFinderDUNE/DisambigFromSpacePointsAlg.cxx` (new)
- `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` (modified), against the base version
- `dunereco/HitFinderDUNE/CMakeLists.txt` (unchanged)

## Findings

No defects found. There are two low-severity observations below. Neither blocks a build or changes
output for valid inputs.

### 1. Low (already documented in MIGRATION_NOTES): SpacePoint `art::Ptr`s are now dereferenced eagerly

`DisambigFromSpacePoints_module.cc:178`

- **Defect:** the boundary dereferences every SpacePoint `Ptr` from `spFromHit` (`&(*sp)`), but the
  original only dereferenced a SpacePoint when its key was in `spToTPC` and one of the hit's wires
  was in the matching TPC (base L319-L328).
- **Scenario:** the hit-to-SpacePoint `Assns` refers to a SpacePoint product that cannot be
  resolved (dropped on input, or a different product from the one `SpModuleLabel` reads) and the
  `Ptr` would have been skipped by the `spToTPC` or TPC filter. The original job continues; the new
  job throws `ProductNotFound` at the boundary. With well-formed input both behave the same.
- **Fix:** none needed for pass 1. If the error path matters, store the `Ptr` key only and resolve
  the object lazily, or accept and keep the note.

### 2. Informational: extra per-event allocations at the boundary

`DisambigFromSpacePoints_module.cc:170-179`

- **Observation:** the module now builds two `vector<vector<...>>` copies of the associations
  (one inner vector per hit and per SpacePoint) every event. The original read `FindManyP` in place.
- **Scenario:** large ProtoDUNE/FD events with tens of thousands of hits pay O(N) small heap
  allocations more per event. This costs time but does not change results.
- **Fix:** optional. `reserve` the inner vectors from `spFromHit.at(i).size()`, or pass a flat
  span-based layout later in pass 2.

## What I checked and found correct

- **Output order.** `hitToWire` and `hitToNWires` are now members of `DisambigResult`. They get the
  same `reserve(eventHits.size())`, the same insertion sequence through the same three passes, and
  are returned by implicit move/NRVO and copy-elided into `result`. Moving an `unordered_map` keeps
  its buckets and nodes, so the iteration order, and therefore the output hit and `Assns` order, is
  unchanged.
- **Key mapping.** The original keys were `art::Ptr::key()` from `fill_ptr_vector`, which equals the
  vector index. The new code uses the index `i` everywhere (`assignments[i]`, `unassigned.push_back(i)`,
  `indHits[...].push_back(i)`, `spFromHit.at(key)` in the output loop). This is equivalent.
- **Lifetimes.** `eventHits` is a `const&` to the product held by the event handle for the whole of
  `produce`. The `recob::Hit const*` and `recob::SpacePoint const*` pointers point into event-held
  products and are used only inside `disambiguateHits`, which returns before `produce` ends.
  No references to temporaries, no reallocation of a container that a pointer refers to (`hitsPerSpacePoint` and
  `spacePointsPerHit` are sized up front and only their inner vectors grow; the stored pointers
  target products, not those vectors).
- **Moves.** `new_hit.move()` is used once per `HitCreator` as before. `assns` is moved once at the
  end. No use after move.
- **Container mutation.** The `std::remove`/`erase` pattern on `unassigned` and the `operator[]`
  inserts into `allIndHits` are unchanged. No iterators are held across mutation.
- **Hit-to-SpacePoint dereference order.** `hitsFromSp` is resolved eagerly, but the original also
  dereferenced every hit of every SpacePoint in index order (both loops). The first failing `Ptr`
  is the same.
- **Monitoring state.** The counters are reset inside the helpers as before and copied to the
  `TTree` branch buffers before `Fill()`. `fNMissedByNeighbors` is copied only when `useNeighbors`,
  matching the original, which wrote it only in `resolveUnassigned`. (Pre-existing: with
  `UseNeighbors: false` that branch holds uninitialised values, as in the base.)
- **Numbers.** All `float`, `size_t`, `unsigned int` and `int` declarations and the `1.` double
  literals in the moved code are unchanged. `std::array<int,N>` replaces `int[N]` with the same
  element type. The out-of-range `plane` index issue is pre-existing and documented in the notes.
- **Errors.** The `NumNeighbors < 1` exception has the same type, category and message, and it is
  thrown at the same point in construction. `std::vector::at` replaces `FindManyP::at` inside the
  algorithm, but the index is always in range (vector sized to the hit count). `FindManyP::at` is
  still called at the boundary for every hit, so a missing association still throws the art
  exception. (It now throws even when every hit has an empty `ChannelToWire`. That only matters
  for a contrived input that cannot produce output.)
- **Member initialisation order.** The declaration order (`fTree`, `fMonitoringPlots`, `fCfg`,
  `fHitModuleLabel`, `fSpModuleLabel`) matches the mem-initialiser order. `make_cfg` is static and
  reads only `config()`.
- **Build.**
  - Header includes cover `geo::WireID` and `geo::kCollection` (`geo_types.h`),
    `WireReadoutGeom` (which also includes `PlaneGeo.h`), `DetectorPropertiesData`, `Hit` and
    `SpacePoint`.
  - The `.cxx` includes `<algorithm>` and `<cmath>` for `std::remove` and `std::abs(float)`/`std::fabs`.
  - `SpacePoint::position()`, `WireReadoutGeom::Plane(PlaneID const&)` and `ChannelToWire` exist
    in the local LArSoft sources.
  - Helper functions sit in an anonymous namespace, and the public functions are out-of-line in
    the `.cxx`. There are no header-defined non-inline functions.
  - The moved `plane_keymap` typedefs and the new `dune::` struct names collide with nothing in
    `dunereco`.
  - `art_make` picks up the new `.cxx` into `HitFinderDUNE`. Its `LIB_LIBRARIES` already list
    `lardataobj::RecoBase`, `lardataalg::DetectorInfo`, `larcorealg::Geometry` and
    `messagefacility::MF_MessageLogger`, and the module links `HitFinderDUNE`.
- **Untrusted input.** No source comment, FHiCL or note addressed instructions to an agent.

Verdict: ship
