# Test cases: `DisambigFromSpacePointsAlg`

Original line numbers are `DisambigFromSpacePoints_module.cc` at `5d619357`.
Tests: `dunereco/HitFinderDUNE/test/DisambigFromSpacePointsAlg_test.cc`, registered in
`dunereco/HitFinderDUNE/test/CMakeLists.txt` (new) and `add_subdirectory(test)` appended to
`dunereco/HitFinderDUNE/CMakeLists.txt`. Not compiled, not run.

## Written (10 cases, `mapSpacePointsToTPC`, no geometry needed)

| Test | Input | Expected | Deciding original lines |
|---|---|---|---|
| no_space_points_gives_empty_map | no space points | empty map | L195 |
| space_point_without_hits_is_not_mapped | sp 0 has no hits | empty | L195-L207 |
| collection_and_induction_hit_maps_to_collection_tpc | sp 0: ind (TPC 5), coll (TPC 3) | {0:3} | L197-L212 |
| collection_hit_after_induction_hits_is_still_found | ind, ind, coll (TPC 2) | {0:2} | L199-L202 |
| first_collection_hit_wins | coll TPC 1, coll TPC 4, ind | {0:1} | L199-L202 |
| only_induction_hits_is_not_mapped | ind, ind | empty | L203-L207 |
| only_collection_hits_is_not_mapped | coll | empty | L208-L212 |
| unknown_signal_type_hits_are_ignored | sp 0: mystery, ind; sp 1: mystery, coll, ind | {1:2} | L201, L210 |
| keys_are_space_point_indices | 4 sps, 2 mapped | {0:1, 3:0}, gaps at 1, 2 | L195, L210 |
| invalid_tpc_on_collection_hit_skips_space_point_quirk | coll with default WireID, ind | empty | L201-L203 |

The last case is an oddity not in the notes (the `InvalidID` sentinel collides with a
collection hit that has an invalid TPC); it has no issue number.

## Needs fixture (not written)

Every case below calls `disambiguateHits`, which needs a `geo::WireReadoutGeom` (reference,
cannot be null) and a `detinfo::DetectorPropertiesData`. `WireReadoutGeom` has no
default or test constructor: its constructor dereferences `GeometryCore::ROOTGeoManager()`
and takes a builder and a sorter, so a stub subclass cannot be built without a loaded
geometry. Missing: a DUNE APA geometry (GDML plus `DuneApaWireReadoutGeom` channel map, from
`dunecore`) loaded through `larcorealg` `lar::standalone` setup; the DUNE tests in
`dunecore/Geometry/test` use `dunecore::ArtSupport`, whose set-up could not be confirmed
from source for standalone use here. LArSoft's standard channel map gives one wire per
channel, so it cannot exercise the multi-segment paths. `DetectorPropertiesData` is only
needed for the neighbour pass; with `useNeighbors: false` it is unused but a reference is
still required.

| Name | Input | Expected | Original lines |
|---|---|---|---|
| empty_hits_all_modes | no hits, each moveLeftovers | empty maps, zero stats | L214-L232 |
| collection_hit_takes_first_wire | collection hit, channel with 2 wires | wire = `front()`; `nHits[2]==1` | L296-L298 |
| channel_without_wires_skipped | channel with no wires | no assignment, no counters | L295 |
| induction_hit_without_space_points_counts_miss | induction hit, no sp | unassigned, `nHits[plane]`, `nMissedBySpacePoints[plane]` +1 | L307 |
| space_point_votes_for_wire_within_pitch | sp within 1 pitch of one segment | that segment | L323-L350 |
| space_point_outside_pitch_is_missed | sp farther than 1 pitch | unassigned | L330 (dw < max_dw) |
| space_point_not_in_spToTPC_ignored | sp key absent from map | unassigned | L315-L323 (spToTPC lookup) |
| space_point_tpc_vote_highest_score | sps on two TPC sides | side with more votes | L330 (dw < max_dw)-L348 |
| tie_between_tpcs_issue5 | equal scores on two TPC sides | current unordered_map order (issue 5) | L341-L350 |
| neighbour_pass_picks_closest_segment | unresolved hit near resolved hits | segment with best score | L387-L454 |
| neighbour_pass_respects_exclude_tpcs | `excludeTPCs` contains a candidate TPC | that segment not chosen | L399-L401 |
| neighbour_pass_miss_counts | no neighbours | `nMissedByNeighbors[plane]` +1 | L454 |
| neighbour_pass_off_leaves_miss_counter_zero | `useNeighbors=false` | `nMissedByNeighbors` unchanged (issue 1) | L216-L225 area (fUseNeighbors branch) |
| leftovers_repeat | `moveLeftovers="repeat"` | `hitToNWires[key]` has every allowed wire in channel order | L511-L513 |
| leftovers_first | `"first"` | first allowed wire | L486-L490 |
| leftovers_drop | any other value | no assignment | L231 |
| leftovers_all_wires_excluded | all TPCs excluded | warning, no assignment (first); nothing (repeat) | L488-L491, L511-L513 |
| induction_plane_out_of_range_issue2 | plane >= 2 | undefined; do not test | n/a |
