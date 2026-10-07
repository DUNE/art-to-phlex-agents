# Test review: `DisambigFromSpacePointsAlg_test`

Reviewer: phlex-reviewer (test-review mode). Read-only; nothing compiled or run.
Base: `5d619357`, original `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`.
Worktree: `<worktree>`.

## What I checked

- All 10 written cases against `git show 5d619357:...module.cc` L195-L212. Every trace comment
  points at the right lines, and every expected value matches what the original loop produces
  for the given input (I hand-traced each one, including `unknown_signal_type_hits_are_ignored`
  and `keys_are_space_point_indices`).
- Order: `mapSpacePointsToTPC` returns an `unordered_map` used only for lookup, so no iteration
  order needs asserting. The one place where position in the input matters (first collection hit
  wins, L199-L202) is pinned by `first_collection_hit_wins`, and the "position doesn't matter"
  side by `collection_hit_after_induction_hits_is_still_found` and the ind-before-coll input in
  `collection_and_induction_hit_maps_to_collection_tpc`.
- Compile: `recob::Hit` 19-argument constructor (`lardataobj/RecoBase/Hit.h:103`) matches the
  argument list and types in `makeHit` and in the quirk test; `geo::kMysteryType` exists
  (`geo_types.h:149`); `geo::WireID(c, t, p, w)` is constexpr (`geo_types.h:439`); a default
  `geo::WireID()` has `TPC == TPCID::InvalidID` (`geo_types.h:315, 433`), and since every
  `InvalidID` is `numeric_limits<unsigned int>::max()`, the `size_t tpc` comparison in the alg
  makes the quirk test's expected value correct. No sign-compare or narrowing warnings under
  dunereco's `DIAGS CAUTIOUS WERROR -pedantic`.
- CMake: `cet_test` returns early when `BUILD_TESTING` is off (cetmodules `CetTest.cmake:367`),
  and `cet_cmake_env()` includes CTest, so the unconditional `add_subdirectory(test)` is safe.
  `USE_BOOST_UNIT` finds and links `Boost::unit_test_framework` itself, so dunereco's top-level
  `find_package(Boost COMPONENTS system)` is not a problem. `dunereco::<LIBRARY_NAME>` is the
  pattern other dunereco packages use for sibling libraries (`dunereco::CVN_func`,
  `dunereco::AnaUtils`), so `dunereco::HitFinderDUNE` is the right target. `larcoreobj::headers`
  and `lardataobj::RecoBase` exist (used by larreco and lardataobj's own tests). This would be
  the first `cet_test` in dunereco; LArSoft's `lardataobj/test/RecoBase/CMakeLists.txt` uses the
  same form.
- The "needs fixture" reasoning in `TESTS.md` against `dunecore/Geometry/test`,
  `dunecore/ArtSupport/ArtServiceHelper.h` and `lardataalg/DetectorInfo/DetectorPropertiesData.cc`.

No defect in the 10 written test cases. Findings below are about the notes, the fixture plan
and one build-hygiene point.

## Findings (most severe first)

### 1. The "needs fixture" verdict is too pessimistic: `disambiguateHits` can be tested today

- **Where:** `TESTS.md:28-38`.
- **Defect:** It says the DUNE geometry set-up through `dunecore::ArtSupport` "could not be
  confirmed for standalone use" and that `DetectorPropertiesData` needs a loaded detector. Both
  are buildable from source already in the tree.
- **Scenario:** All 18 geometry-dependent cases stay unwritten, so the three passes that carry
  the real risk (TPC vote, neighbour pass, leftovers) go into the human build with no
  characterization at all.
- **Fix:** two pieces, both used elsewhere in DUNE:
  1. **Wire readout.** `ArtServiceHelper::load_services(std::istream&)`
     (`dunecore/ArtSupport/ArtServiceHelper.h:117`) is what `test_GeometryDune.cxx:227-246`,
     `test_WireSelector.cxx:121-132` and four `DuneCommon/Service/test` tests use:
     ```cpp
     std::stringstream cfg;
     cfg << "#include \"geometry_dune.fcl\"\n"
         << "services.Geometry: @local::dune10kt_1x2x6_geo\n"
         << "services.WireReadout: @local::dune_wire_readout\n";
     ArtServiceHelper::load_services(cfg);
     auto const& wr = art::ServiceHandle<geo::WireReadout>()->Get();
     ```
     `dune_wire_readout` (`geometry_dune.fcl:676`) is `DUNEWireReadout`, the APA map with
     wrapped induction wires, so `ChannelToWire` returns several `WireID`s on U/V channels: the
     multi-segment paths the notes say the LArSoft standard map cannot reach. Pick one U channel
     with `cwids.size() > 1` in a setup step, place space points at the centre of
     `wr.Wire(cwids[k])` (so `WireCoordinate` gives the wire number and `dw == 0 < 1`), and
     assert `hitToWire[i] == cwids[k]`. CMake: add `dunecore::ArtSupport`, `larcore::headers`,
     `larcorealg::Geometry`, `ROOT::Geom` as in `dunecore/Geometry/test/CMakeLists.txt`.
  2. **Detector properties.** No service needed. `DetectorPropertiesData` has a public
     constructor `(DetectorProperties const&, double xTicksCoef, offsets, driftDirection)`
     (`DetectorPropertiesData.h`), the constructor only stores the reference
     (`DetectorPropertiesData.cc` ctor), and `GetXTicksCoefficient(t, c)` reads only
     `fXTicksCoefficient * fDriftDirection.at(c).at(t)` (`.cc:142-145`). That is the only
     `detProp` call in the alg (`.cxx` L234, L249). A test-local fake `detinfo::DetectorProperties`
     with its 19 pure virtuals returning 0 plus
     `DetectorPropertiesData{fake, 0.08, {}, {{-1., 1., -1., 1., ...}}}` (one entry per TPC of
     cryostat 0; L234 always reads `(0, 0)`, so it must not be empty or `.at` throws) gives
     full control over `ddMax` and `driftPitch`.
- **Caveat:** the local `dunecore` checkout is `v10_17_02d00`; dunereco is `v10_26_00d02`.
  Check that `ArtServiceHelper` and `dune_wire_readout` are unchanged at the matching dunecore
  tag before writing the tests. Runtime needs `geometry_dune.fcl` on `FHICL_FILE_PATH` and the
  GDML on `FW_SEARCH_PATH`, both standard in a dunesw environment.

### 2. The fixture plan never pins the hit-to-wire iteration order that the notes say decides output order

- **Where:** `TESTS.md:40-59` (fixture table); notes `MIGRATION_NOTES.md:103, 145`.
- **Defect:** The notes say `hitToWire` iteration order (one `unordered_map`, `reserve` before the
  first insert, moved out) sets the order of output hits and associations, but no planned case
  checks it.
- **Scenario:** A later change that copies `hitToWire` into a fresh map, drops the `reserve`, or
  inserts in a different sequence keeps every key-value assertion green while reordering the
  output hit collection.
- **Fix:** add one fixture case that builds the same input and compares the iteration sequence of
  `res.hitToWire` with a reference `unordered_map` filled by the original insertion sequence
  (collection hits in hit order, then SP-resolved, then neighbour `insert`, then `"first"`
  leftovers) after the same `reserve(hits.size())`. This is standard-library dependent; label it
  so. `leftovers_repeat` should also assert the full vector, not membership, since L513 appends
  in `cwids` order.

### 3. Test comment and `TESTS.md` say the sentinel quirk has no issue number; the notes now call it issue 10

- **Where:** `DisambigFromSpacePointsAlg_test.cc:174`; `TESTS.md:21, 23-24`.
- **Defect:** `MIGRATION_NOTES.md:172` lists it as issue 10 and names this test, so the "no issue
  number in the notes" text is stale.
- **Scenario:** A reader looking up the quirk from the test finds no cross-reference and may
  treat it as untriaged.
- **Fix:** say "issue 10" in the comment and in both places in `TESTS.md`. Consider renaming the
  case `..._issue10` to match the `tie_between_tpcs_issue5` convention.

### 4. Fixture table line references are off, and one expected value cannot be traced to the original

- **Where:** `TESTS.md:48, 53, 54, 57`.
- **Defect / fix:**
  - `space_point_not_in_spToTPC_ignored`: lookup and `continue` are L319-L320, not L315-L323.
  - `neighbour_pass_miss_counts`: the increment is L455, not L454.
  - `neighbour_pass_off_leaves_miss_counter_zero`: the branch is L224-L228, not "L216-L225 area".
    The expected value comes from the extraction, not the original: with `UseNeighbors: false`
    the original never writes `fNMissedByNeighbors` (issue 1, indeterminate), while
    `DisambigStats{}` value-initialises to zero. Mark the row "pins the extraction, original is
    indeterminate" so nobody reads it as an equivalence check.
  - `leftovers_drop`: the drop branch is L232; L231 is the `"first"` branch.
- **Scenario:** When the tester writes these cases, they copy wrong lines into the trace comments
  and the next reviewer cannot match them.

### 5. Test target relies on transitive PUBLIC links for headers it includes directly (uncertain)

- **Where:** `dunereco/HitFinderDUNE/test/CMakeLists.txt:5-9`.
- **Defect:** The test includes `DisambigFromSpacePointsAlg.h`, which pulls in
  `larcorealg/Geometry/WireReadoutGeom.h` and `lardataalg/DetectorInfo/DetectorPropertiesData.h`.
  It gets those include paths only because `art_make`'s `LIB_LIBRARIES` are PUBLIC on
  `HitFinderDUNE` (`CetMakeLibrary.cmake:291-292`).
- **Scenario:** It builds as written. It breaks only if HitFinderDUNE's link list later becomes
  PRIVATE or drops those entries. I could not construct a present-day failure, so treat this as
  hygiene.
- **Fix:** add `larcorealg::Geometry` and `lardataalg::DetectorInfo` to the test's `LIBRARIES`.
  The fixture tests will need them anyway (finding 1).

## Verdict

Verdict: ship. The 10 written tests and the CMake changes are correct as written. Fix finding 3
as a one-line edit, and revisit the fixture plan (findings 1, 2 and 4) before calling the alg
tested.
