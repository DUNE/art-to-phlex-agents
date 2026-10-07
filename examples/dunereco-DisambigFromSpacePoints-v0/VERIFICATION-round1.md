# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | FAIL |
| Findings | 0 blocker, 1 major, 5 minor, 3 nit |
| Working tree and base | `<worktree>` (branch `phlex-extract/DisambigFromSpacePoints`, uncommitted) against `ffc89e0d97c413cbfc3a1b17d7e278f734ba8cd9` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints/MIGRATION_NOTES.md` (KIT_FEEDBACK.md not read) |
| Verifier / model / date | Claude Code verifier (art-phlex-verify, kit snapshot iter1), claude-opus-5, 2026-09-15 |
| Compilation | none, by design |

## Summary

- The change moves the four private member functions and the inline spacepoint-to-TPC loop
  into five free functions in `DisambigFromSpacePointsAlg.h/.cxx`. It replaces
  `fill_ptr_vector`/`art::Ptr<recob::Hit>` with `*hitsHandle` plus indices, resolves
  `FindManyP<SpacePoint>` into parallel pointer and key vectors at the boundary, and switches
  `hitsFromSp` to `FindMany`. The per-event counters become a `DisambigStats` object that the
  module copies into the TTree branch buffers.
- The event data products are preserved statement for statement: same hit-to-wire decisions,
  same `unordered_map` types, `reserve()` and insertion sequence (so the same output order),
  same association pair order, same drop conditions, same float/double arithmetic. The
  `declare_products`/`produces` calls and FHiCL are unchanged.
- One undocumented behaviour change: with `UseNeighbors: false` and `MonitoringPlots: true`,
  the `hitstats` branch `fNMissedByNeighbors` used to hold values nothing ever wrote. It now
  holds 0. A header comment and the notes claim the opposite (F1). This is the reason for the
  FAIL. The fix is small: either preserve the old behaviour or document the deviation.
- No certain or likely compile errors found by reading. Every new API use was checked against
  local LArSoft and canvas headers, with version caveats listed below.
- Before build and regression: fix F1, and make the art output comparison order-sensitive
  (F2). Build from a fresh CMake configure so `art_make` globs the new `.cxx` (F9).

## Original module in brief

Written before reading the new code or the notes (kept verbatim in
`scratchpad/verifier/original-summary.md`).

DisambigFromSpacePoints reads `recob::Hit` (HitModuleLabel) and `recob::SpacePoint`
(SpModuleLabel) and writes each hit again on a resolved wire. Collection hits go to the first
wire of their channel. For induction hits, each associated spacepoint is mapped to a TPC
through its first collection hit (`spToTPC`, keyed by spacepoint index). A candidate wire in
that TPC scores +1 when the spacepoint's wire coordinate is within one wire pitch, and the TPC
with the strictly highest score wins (ties broken by `unordered_map` iteration order).
Unresolved induction hits can optionally (UseNeighbors) be resolved by a k-nearest
(NumNeighbors) distance score to already-resolved hits in the same cryostat/TPC/plane within
MaxDistance, skipping ExcludeTPCs. Leftover hits are dropped, put on the first allowed wire
("first"), or repeated on every allowed wire ("repeat").

Contract: FHiCL HitModuleLabel, SpModuleLabel, ExcludeTPCs, UseNeighbors, NumNeighbors (below 1
throws `cet::exception` in the constructor), MaxDistance, MoveLeftovers, MonitoringPlots, none
with defaults. Products come from `HitCollectionCreator::declare_products(producesCollector(), "",
true, false)` plus `Assns<recob::Hit, recob::SpacePoint>`. Services: WireReadout (constructor),
TFileService (constructor, only with MonitoringPlots: TTree `hitstats`), and
DetectorPropertiesService (once per event). Output order is `hitToWire` iteration followed by
`hitToNWires` iteration, with Hit-SpacePoint pairs in `spFromHit` order per new hit.
`fNMissedByNeighbors` is reset only inside `resolveUnassigned`.

## Automated checks

`S=$KIT/skills/art-phlex-extract/scripts`, run from the worktree, `D=dunereco/HitFinderDUNE`.

| Check | Command | Result |
|---|---|---|
| Scope | `git status --short`; `git diff --stat <base>`; `git ls-files --others --exclude-standard` | 3 files: `A DisambigFromSpacePointsAlg.cxx` (283 lines), `A DisambigFromSpacePointsAlg.h` (121), `M DisambigFromSpacePoints_module.cc` (+/-372). No untracked files, no build-file changes, nothing outside the module directory. `extraction.patch` equals the worktree diff (ignoring `index` lines). |
| Purity | `check_purity.py $D/DisambigFromSpacePointsAlg.h $D/DisambigFromSpacePointsAlg.cxx` | PASS, 0 errors, 0 warnings, 6 transitional (header include reported at L29, but the `#include` is at L30 and L29 is the marker; known line-offset limitation. `.cxx` L53, 149, 180, 243, 256). |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:<base>:$D/DisambigFromSpacePoints_module.cc --after $D/DisambigFromSpacePoints_module.cc` | `contract unchanged (12 items)`. Manual check of what the tool cannot see: `declare_products(producesCollector(), "", true, false)` base L142 = new L118; `HitCollectionCreator hcol(evt, channelHitWires.isValid(), false)` base L176-180 = new L152-156. Same instance names, same wire-assns flag, no raw-digit assns. |
| Algorithm inventory | `art_inventory.py report $D/DisambigFromSpacePointsAlg.h $D/DisambigFromSpacePointsAlg.cxx` | Only `messagefacility` include (header) and 5 `MessageLogger` uses. No services, event access, Ptr or FHiCL. |
| Module inventory | `art_inventory.py report $D/DisambigFromSpacePoints_module.cc` | Services, getValidHandle, FindOneP/FindManyP/FindMany, Assns, PtrMaker, TFileService, `cet::exception` all in the module. "Member state written inside callbacks" lists `fNHits`/`fNMissed*` at L265-269: these are the intended copies into TTree branch buffers, but see F1. |
| Transitional markers vs notes | `grep -rn PHLEX-TRANSITIONAL $D` | 6 markers (`.h:29`, `.cxx:52, 148, 179, 242, 255`). The notes' table lists 6 items at `.h:30` and `.cxx:53, 149, 180, 243, 256` (the guarded lines). One-to-one match. |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| F1 | major | `DisambigFromSpacePoints_module.cc:268-269`; `DisambigFromSpacePointsAlg.h:54-60` | Undocumented change to `hitstats` TTree output. When `UseNeighbors` is false, the original never writes `fNMissedByNeighbors`. Its values are indeterminate (never initialised) and stay the same every event. The new code fills 0 every event (NSDMI `{0, 0}` plus unconditional copy). The header comment says the members "were reset at the start of every produce() call anyway". MIGRATION_NOTES §4 says "Intentional deviations: none". §8 proposes this exact configuration and calls the TTree "the most direct regression check", so the check would either show a difference nobody expects, or match only by accident. Event data products are not affected, and the shipped config uses `UseNeighbors: true, MonitoringPlots: false`. | Base: resets at L287-289 (`runOnSpacePoints`, always) and L374-375 (`resolveUnassigned`, only under `if (fUseNeighbors)` at L224). Constructor L122-133 never initialises the arrays. New: `stats` is a fresh local per event (module L207), copied at L268-269 whatever `fUseNeighbors` is. | Choose one and write it down: (a) preserve behaviour by copying `nMissedByNeighbors` only `if (fUseNeighbors)`, or (b) keep the zeros and record them in §4 as an intentional deviation that fixes a pre-existing indeterminate-value read. Either way, correct the header comment (`.h:54-56`) and notes §2 item 4. |
| F2 | minor | `MIGRATION_NOTES.md` §8 | The validation plan says the output order is "hash-order, not insertion order" and recommends comparing hit dumps sorted by original key, citing multithreading. That is wrong for this module: the extraction keeps the container types, `reserve(hitsHandle->size())` (same value as `eventHits.size()`) and the insertion sequence. With the same standard library, the output collection order and Assns pair order should be identical. A sorted comparison would hide an ordering regression, and the kit asks for associations that are "identical, not just equivalent". | Base L219, L298/L350, L465 against new module L205, `.cxx` L56/L110, L228. art runs one module instance serially, so nothing reorders within the event. | Compare hits and `Assns<Hit,SpacePoint>` in collection order first. Treat any order difference as a finding. Keep the sorted comparison only as a diagnostic. Cover UseNeighbors true/false and MoveLeftovers `first`/`repeat`/other. |
| F3 | minor | `DisambigFromSpacePoints_module.cc:167, 193-197`; `DisambigFromSpacePointsAlg.cxx:19` | Failure mode differs when association Ptrs point to unavailable products (for example a dropped input branch). `FindMany` stores `nullptr` for such hits, and `BuildSpacePointToTPCMap` then dereferences `h->SignalType()` (null dereference). The original `art::Ptr::operator->` threw `art::Exception(ProductNotFound)`. The new boundary loop also calls `sp.get()` on every spacepoint of every hit up front, where the original only dereferenced spacepoints found in `spToTPC` on a matching TPC. Output is unchanged whenever products are available. | canvas `detail/IPRHelper.h:382` (`item ? item.get() : nullptr`), `Ptr.h:138-141, 144-151, 238-259` (canvas 3.17.0, local rattler cache). | Record in §4. Optionally throw at the boundary if any `hitsPerSpacePoint[i][j]` is null, so the failure stays an exception. |
| F4 | minor | `DisambigFromSpacePointsAlg.h:29-33` | The transitional `messagefacility` include sits in the public header, but only the `.cxx` uses `mf::`. Every includer (the module now, a Phlex registration unit later) inherits the framework dependency. | `grep mf:: DisambigFromSpacePointsAlg.h` finds nothing. Uses are at `.cxx` L53, 149, 180, 243, 256. | Move the include and its marker to the `.cxx`, and update the §6 row. |
| F5 | minor | `MIGRATION_NOTES.md` §4 (suspected pre-existing issues) | Incomplete. Not recorded: (1) the indeterminate `fNMissedByNeighbors` read (F1); (2) the counter arrays are indexed by `plane` with no bounds check. A non-collection hit on plane 2 or higher writes past `nHits[3]`/`nMissedBySpacePoints[2]`/`nMissedByNeighbors[2]`. Both versions use the same member layout, so the effect is preserved, but it is undefined behaviour; (3) hits whose channel maps to no wires are dropped from every counter. | Base L305, L310, L356, L455; new `.cxx` L63, L70, L116, L218. Base L295; new `.cxx` L53. | Add all three to §4. Do not fix them in pass 1. |
| F6 | minor | `MIGRATION_NOTES.md` §2 items 2 and 4, §4 issue 3, "Module selection" | Inaccurate details: item 4 cites the copy at "module produce() L259-263" (actual L265-269); item 2 cites "module ctor L147" (actual L123); §4 issue 3 calls `geo::WireID::InvalidID` a `CryostatID_t` (it is `WireID_t`, `geo_types.h:422-428`, also `unsigned int`, so the conclusion stands); "art_make auto-globs new `.cxx`/`.h` files" (only `.cxx` become library sources; headers are installed by `install_headers()`). | As cited. | Correct the references. |
| F7 | nit | `DisambigFromSpacePoints_module.cc:89-94, 108` | `fCfg` is built from duplicated members instead of a `make_cfg(Config const&)` as `larsoft-boundary-patterns.md` suggests, and `nNeighbors` goes as a separate argument rather than a `cfg` field. Correct, but it leaves two sources for MaxDistance/ExcludeTPCs. | Member order is safe: `fMaxDistance` (L83) and `fExcludeTPCs` (L85) are declared before `fCfg` (L94). | Optional: `make_cfg` and drop the duplicate members. |
| F8 | nit | `MIGRATION_NOTES.md` §7 | Binding plan gaps. `ResolveUnassigned` takes `cryo_tpc_plane_keymap&` non-const only because `allIndHits[cryo][tpc][plane]` (`.cxx:171`) inserts empty entries. A Phlex `transform` gets const inputs, so binding needs a `find`-based lookup (no behaviour change), and the plan does not name it. The plan also labels `det_props` "job/event"; `DataFor(evt)` makes it event-layer. | `.cxx:130, 171`; module L169. | Add both to the blockers column. |
| F9 | nit | `dunereco/HitFinderDUNE/CMakeLists.txt` (unchanged) | `art_make` globs at configure time, so an existing build directory will not see the new `.cxx` without a re-configure. The algorithm also lands in `HitFinderDUNE`, which already links art, fhiclcpp and messagefacility, so "framework-free" holds at source level only. | CMakeLists L2-26. | Mention in the hand-off. Splitting the library is a binding-stage decision. |

## Behaviour-preservation walk-through

Base file `DisambigFromSpacePoints_module.cc@ffc89e0d` (B). New module (M), `DisambigFromSpacePointsAlg.cxx` (A), `DisambigFromSpacePointsAlg.h` (H).

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| B:47-49 keymap typedefs | H:39-41 | identical | Same types, same namespace. No other definitions in DUNE/LArSoft checkouts. |
| B:122-133 member init | M:97-108 | mechanical edit OK | `fCfg{fMaxDistance, fExcludeTPCs}` added last. Declaration order puts its sources first. |
| B:134-137 NumNeighbors check | M:110-113 | identical | Same category and message. |
| B:142 `declare_products(..., "", true, false)` | M:118 | identical | Checked by hand (tool blind spot). |
| B:145 `produces<Assns<Hit,SpacePoint>>` | M:121 | identical | |
| B:147 WireReadout | M:123 | identical | |
| B:149-158 TTree booking | M:125-134 | identical | Same branch addresses (members). |
| B:163-164 fRun/fEvent | M:139-140 | identical | |
| B:166-167 getValidHandle x2 | M:142-143 | identical | |
| B:172 FindOneP<Wire> | M:148 | identical | |
| B:176-180 hcol | M:152-156 | identical | |
| B:183 assns | M:159 | identical | |
| B:186-187 `fill_ptr_vector` | removed; M uses `*hitsHandle` and indices | mechanical edit OK | `Ptr(h,i).key() == i`; no filtering. |
| B:189 FindManyP<SpacePoint> | M:166 | identical | Construction order spFromHit, hitsFromSp kept. |
| B:190 FindManyP<Hit> | M:167 FindMany<Hit> | mechanical edit OK | Same objects; failure mode differs (F3). |
| B:192 detProp DataFor | M:169 | identical | Once per event, same place. |
| B:194-212 spToTPC loop | M:179-184 + A:8-32 | mechanical edit OK | Loop over `spHandle->size()` equals `hitsPerSpacePoint.size()`; `size_t tpc = InvalidID` and its compare unchanged. The map is only used via `find`, so its order is irrelevant. |
| (none) | M:186-198 per-hit SP pointer/key vectors | new boundary code | Same per-hit SP order as `spFromHit.at(i)`; eager `sp.get()` (F3). |
| B:214-217 locals | M:200-203 | identical | Same container types. |
| B:219 `hitToWire.reserve(eventHits.size())` | M:205 `reserve(hitsHandle->size())` | identical | Same value, so same bucket count and iteration order. |
| B:221-222 runOnSpacePoints + LogInfo | M:207-210 | mechanical edit OK | Argument order matches H:80-88. |
| B:224-228 UseNeighbors branch | M:212-217 | mechanical edit OK | |
| B:230-232 MoveLeftovers switch | M:219-221 | mechanical edit OK | Same string compares, same order, same "dropped" log. |
| B:234 PtrMaker | M:223 | identical | |
| B:236-251 hitToWire output loop | M:225-240 | mechanical edit OK | `*(eventHits[key])` → `hitsHandle->at(key)` (same object, `recob::Hit const&` → `HitCreator(Hit const&, WireID const&)`, HitCreator.h:321); `spFromHit.at(eventHits[key].key())` → `.at(key)`. Emplace order and pair order unchanged. |
| B:253-269 hitToNWires output loop | M:242-258 | mechanical edit OK | Same. |
| B:271 `if (fMonitoringPlots && fTree) Fill()` | M:260-271 | CHANGED | Same condition, same position (before `put_into`). `fNHits` and `fNMissedBySpacePoints` identical. `fNMissedByNeighbors` is 0 instead of never-written when UseNeighbors is false (F1). |
| B:274-275 put | M:274-275 | identical | |
| B:287-289 counter reset | A:44-46 | identical | On `stats`. |
| B:291-295 hit loop, cwids, empty → warn/continue | A:48-53 | identical | Same message; hit dropped uncounted in both. |
| B:296-300 collection hit | A:54-58 | mechanical edit OK | `hit.key()` → `i`. |
| B:303-305 induction id/cryo/plane, nHits++ | A:61-63 | identical | `size_t` kept; unchecked index (F5). |
| B:307-311 no SP → unassigned | A:65-71 | mechanical edit OK | `spFromHit.at(key).size()` → `spKeys.size()` (same vector length). |
| B:314-336 SP scoring | A:74-96 | mechanical edit OK | Index-parallel iteration in the same order; `sp.key()` → `spKeys[s]`, `sp->position()` → `spacePoints[s]->position()`; `float sp_wire`, `float dw`, `const float max_dw = 1.`, `<` unchanged. |
| B:337-351 best TPC, indHits, assignment | A:97-111 | identical | Same `unordered_map<size_t,size_t>` and insertion sequence, so same tie-break. `bestId.TPC` key unchanged. |
| B:352-357 no match → unassigned | A:112-117 | identical | |
| B:362 return | A:122 | identical | |
| B:374-377 reset, result map | A:135-138 | identical | On `stats`. |
| B:379-387 per-unassigned setup | A:140-149 | identical | `unsigned int cryo, plane`; `float hitDrift`. |
| B:389-390 dwMax, ddMax | A:151-152 | mechanical edit OK | `fMaxDistance` (const float) → `cfg.maxDistance` (float); still uses plane `{0,0,plane}` and `GetXTicksCoefficient(0,0)`. |
| B:392-401 wire loop, ExcludeTPCs | A:154-163 | mechanical edit OK | `fExcludeTPCs` → `cfg.excludeTPCs`, same `std::vector<size_t>`. |
| B:403-409 planeID, pitches, distBuff, keys | A:165-171 | identical | `operator[]` insertion kept (F8). |
| B:410-438 neighbour distances | A:172-201 | mechanical edit OK | `hitInd->PeakTime()` → `hitInd.PeakTime()`; all float, same `>`/`<`. |
| B:439-452 score and best | A:202-215 | identical | `float score += 1./(1.+d)` kept (double term narrowed per step, as before). |
| B:454-455 result / missed++ | A:217-218 | identical | |
| B:459-465 erase, insert | A:222-228 | identical | Same range insert from `result`, so same `hitToWire` insertion order. |
| B:466 return | A:229 | identical | |
| B:469-493 assignFirstAllowedWire | A:232-258 | mechanical edit OK | `cfg.excludeTPCs`; both warnings kept verbatim. |
| B:495-516 assignEveryAllowedWire | A:260-281 | mechanical edit OK | Comment extended; `assignments[key]` only created when a wire is allowed, as before. |

Also checked with no difference found: random draws (none), exceptions (only the constructor one), service data fetched per event (DataFor once), no references into event data kept past `produce()` (the pointer vectors are locals), no member state carried across events that was not carried before.

## Compile-risk review

Checked by reading:

- Declarations (H:68-117) match definitions (A:8, 34, 125, 232, 260) in name, namespace, `const`, references and parameter order. No default arguments. No function bodies in the header.
- Call sites (M:184, 208-209, 214-215, 219, 220) match the parameter lists. `*hitsHandle` is `std::vector<recob::Hit> const&`, `detProp` is `DetectorPropertiesData const`, `fNumNeighbors` is `size_t`.
- `art::FindMany` is visible in the module: `lardata/Utilities/AssociationUtil.h:87-88` includes `FindMany.h` and `FindManyP.h`. `FindMany<T>::at` returns `std::vector<T const*> const&` (canvas `FindMany.h:59, 197`), so M:182 is a valid copy. `art::Ptr<T>::get()` returns `T const*` (canvas `Ptr.h:138`).
- `cryo_tpc_plane_keymap` is used unqualified inside `namespace dune` in the module, and H declares it there.
- Includes per new file: H has `<cstddef> <map> <string> <unordered_map> <vector>`, `WireReadoutGeom.h` (brings `PlaneGeo.h`, `WireReadoutGeom.h:13`), `geo_types.h` (`geo::kCollection/kInduction` :147-148, `WireID` :422-430, `isValid` :194), `DetectorPropertiesData.h` (`GetXTicksCoefficient(int,int)` :89), `Hit.h`, `SpacePoint.h`. A adds `<algorithm>` (`std::remove`) and `<cmath>` (`std::fabs`, float `std::abs`). Include root `"dunereco/..."` is used in 122 other files.
- Overload resolution unchanged from the original: `Plane({0,0,plane})` has one viable overload (`Plane(PlaneID const&)`, :151, because the other takes 2 args); `Plane(cwids[w])` binds `WireID` to `PlaneID const&`; `WireCoordinate(Point_t const&)` returns double (`PlaneGeo.h:704`); `SpacePoint::position()` returns `geo::Point_t` (:48).
- No `const&` parameter is used to call a non-const method: `allIndHits` and `assignments` are non-const where mutated; `wireReadout` and `detProp` methods used are const.
- Language level: nothing beyond C++14 (NSDMI array members in `DisambigStats`). dunereco builds as C++17 or later.
- Build files: unchanged. `art_make(BASENAME_ONLY ...)` globs the new `.cxx` into `HitFinderDUNE`, whose `LIB_LIBRARIES` already list `lardataobj::RecoBase`, `lardataalg::DetectorInfo`, `larcorealg::Geometry`, `messagefacility::MF_MessageLogger`. `MODULE_LIBRARIES` includes `HitFinderDUNE`. No framework library was added.
- Name collisions: none of the five function names, `DisambigStats`, `DisambigFromSpacePointsCfg` or the keymap typedefs appear elsewhere in the local DUNE and LArSoft checkouts (Feb 2026 snapshot).

Needs build to confirm: nothing specific. Likelihood of a compile error judged low.

Unverified assumptions:

- LArSoft headers come from the local checkout at larsoft v10_16_00 (lardata v10_00_16, lardataobj v10_05_00, lardataalg v10_02_01). The dunereco base is v10_24_00d00, which builds against a newer LArSoft. Every LArSoft call in the moved code is the same call the original made. The new-use APIs (`HitCreator(Hit const&, WireID const&)`, `AssociationUtil.h` includes) are assumed unchanged between those versions.
- canvas semantics (`FindMany::at`, `Ptr::get`, the nullptr fill in `IPRHelper`) come from canvas 3.17.0 in `~/.cache/rattler`. That this is the canvas dunereco v10_24 builds with is assumed, not verified.

## Guide conformance

- Separation checks: `ServiceHandle` appears only in the module (constructor L123, L127; `produce` L169). Service values (`WireReadoutGeom const&`, `DetectorPropertiesData const&`) are passed explicitly. No helper receives the event, a handle, `FindManyP` or `art::Ptr`. Nothing event-scoped is cached across events: the members `fRun`/`fEvent`/counters are TTree branch buffers written before each `Fill()`, the accepted Histograms and TTrees pattern (but see F1 on what gets written).
- Extraction checklist 1 to 5: (1) yes, the algorithm reads as hit/spacepoint/geometry logic; (2) yes, every input is a parameter (checked each body for leftover member reads: none); (3) partly, outputs are explicit out-parameters (`assignments`, `indHits`, `unassigned`, `stats`) rather than return values, acceptable for pass 1 and flagged by the notes for binding; (4) yes, `fCfg` is built once in the constructor (F7 nit); (5) yes for logging (6 markers, all listed), but the monitoring-output deviation in F1 is not documented.
- Binding plan: plausible. It uses several `transform`s, names the multiple-output blocker and missing association support, and marks the art output tail as boundary-only. `unlimited` concurrency fits: `check_purity.py` found no statics or mutable state, and `mf::Log*` is thread-safe. Gaps are in F8.

## Notes accuracy

- §2 item 4 and header `.h:54-56`: "reset at the start of every produce() call anyway" is false for `fNMissedByNeighbors` (F1).
- §4 "Intentional deviations: none" misses the TTree change (F1) and the null-dereference failure mode (F3).
- §4 suspected issues omit the indeterminate counter, the unchecked `plane` indexing and uncounted no-wire hits (F5).
- §8 validation plan misstates the output order and recommends a weaker, sorted comparison (F2).
- Line and type details in §2 items 2 and 4, §4 issue 3, and "Module selection" (F6).
- Confirmed accurate: `eventHits[i].key() == i`; `spFromHit` must stay `FindManyP` for `.key()`; `hitsFromSp` needs only object access; the transitional table matches the markers; `declare_products` is untouched; the only FHiCL user is `hitfindermodules_dune.fcl` (`UseNeighbors: true`, `MonitoringPlots: false`, `MoveLeftovers: "first"`, overridden to `"repeat"` for `dunefd_`/`pdune_disambigfromsp`); re-entrancy claims.

## Notes on the verification procedure

Feedback on `art-phlex-verify` from this run (not about the code):

1. The severity scale has no slot for behaviour changes in non-product outputs (TTree/histogram values, log text), nor for a pass-1 change that quietly replaces undefined or indeterminate behaviour. Step 4 asks for "histogram and TTree fills: same values", but "blocker" covers only physics output and the framework contract, and the "major" list does not mention this case. F1 is rated major by judgement.
2. Step 4 tabulates "every statement of the original", so boundary code with no original counterpart (here the eager `Ptr::get()` and `FindMany` resolution loops) has no row unless the verifier adds one. Add "walk new boundary statements too; compare eager against lazy dereference and null handling". Also name unordered-container iteration order (container type, `reserve`, insertion sequence) explicitly next to "map iteration".
3. Step 7 compares notes claims with code but not the validation plan with the walk-through. Add: "check the validation plan is order-sensitive where ordering was shown to be preserved, and covers each configuration branch". The `report` output's "member state written inside callbacks" also needs a line of guidance: here it lists intended branch-buffer copies. Finally, the skill gives no hint where dependency headers might live beyond LArSoft; canvas was only in a rattler package cache.
