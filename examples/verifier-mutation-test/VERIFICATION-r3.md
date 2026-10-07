# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 0 blocker, 1 major, 6 minor, 1 nit |
| Working tree and base | `<worktree-r3>` (branch `phlex-extract/DisambigFromSpacePoints-r3`, uncommitted) against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r3/MIGRATION_NOTES.md` |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The module's four private helpers and the space point to TPC loop moved into
  `DisambigFromSpacePointsAlg.{h,cxx}` as free functions with config, geometry and detector
  properties passed in. The module now resolves the two `FindManyP` associations into plain
  containers, calls `disambiguateHits`, and copies counters back into the TTree buffers.
- The data products should be identical. The single `unordered_map` threaded through all
  passes, its `reserve`, insertion sequence and move-out are preserved, so output hit order and
  association pair order are unchanged. The contract is unchanged and purity is clean.
- One undocumented change to log output: the `assignFirstAllowedWire` warning text was
  rewritten (`"None of wires is allowed for this hit???"` became `"No allowed wire for this
  hit"`). The notes claim the text was kept. `MoveLeftovers: "first"` is the
  `standard_disambigfromsp` default, so this path is reachable on a stock configuration.
  This is the only reason for FAIL.
- Error paths: eager `&*ptr` resolution at the boundary turns a null `art::Ptr` (which used
  to throw `art::Exception`) into a null dereference. This needs corrupt input.
- Before a build: restore the warning text, fix the notes (worktree path, absent test files,
  Phlex-era home), and add a log diff to the validation plan. A fresh CMake configure is
  needed because `art_make` globs the new `.cxx`.

## Original module in brief

Written before reading the new code or the notes. `DisambigFromSpacePoints` is an
`EDProducer` that reads hits (`HitModuleLabel`) and space points (`SpModuleLabel`) and their
associations. Each space point is mapped to the TPC of its collection hit. Each induction hit
is then placed on the wrapped wire segment within one wire pitch of its space points, using a
vote per TPC. Hits left over can be placed by a nearest-resolved-neighbour score
(`UseNeighbors`), then repeated on every allowed segment, put on the first allowed segment, or
dropped (`MoveLeftovers`). It writes a new `std::vector<recob::Hit>` through
`HitCollectionCreator` (with hit-wire Assns if the input had them), a copy of the
hit-space point Assns, and optionally a `hitstats` TTree of per-plane counters. Output order
follows `std::unordered_map` iteration of `hitToWire`, then `hitToNWires`. Quirk:
`fNMissedByNeighbors` is written only when `UseNeighbors` is true, so it is indeterminate or
stale otherwise.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (`.cxx` L17, 50, 146, 177, 242, 255, 336, 342, 348) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:<module> --after <module>` | contract unchanged (13 items); `contract.before.txt` and `contract.after.txt` identical |
| Algorithm inventory | `art_inventory.py report <alg files>` | only `MessageLogger` (8 uses, 1 include), all marked transitional |
| Module inventory | `art_inventory.py report <module>` | all framework constructs in the module; member writes in `produce` only (`fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors`) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'`; `grep -rn PHLEX-TRANSITIONAL <new files>` | 9 markers (comment lines 16, 49, 145, 176, 241, 254, 335, 341, 347), each sitting on the line before a logging line that matches a row of the notes' section 6 table, and the reverse. Reason ("logging") holds for all 9. The L255 row misquotes the message text (finding 1). |
| Patch vs tree | `diff <(git diff 5d619357) extraction.patch` | identical |
| Agent-addressed text | grep of the diff and notes | none found |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| 1 | major | `DisambigFromSpacePointsAlg.cxx:255` | Warning text changed from `"None of wires is allowed for this hit???"` to `"No allowed wire for this hit"`. Not listed as a deviation. Notes section 6 (L198) quotes the original text, and the `.cxx` header comment says "mechanical edits only". Reachable on `MoveLeftovers: "first"`, which is the `standard_disambigfromsp` default (`hitfindermodules_dune.fcl:23`). | base L491 vs new L255; `extraction.patch` L261 / L888 | Restore the original string verbatim. |
| 2 | minor | `DisambigFromSpacePoints_module.cc:173`, `:178` | `&(*h)` and `&(*sp)` use `art::Ptr::operator*`, which is `*get()` and yields a null reference for a null `Ptr`. The algorithm then dereferences the null pointer (`.cxx:83` `sp.spacePoint->position()`, `.cxx:299/308` `h->SignalType()`). The original used `->` (`operator->` calls `parentProduct_()`, which throws `art::Exception(ProductNotFound)` when there is no product getter). Notes section 2 #13 ("kept as FindManyP so that dereference raises the same art exception") is false for null `Ptr`s. Needs Assns that contain null `Ptr`s, which is corrupt input. | canvas `Ptr.h` L130-L151, L236-L260 (pixi `larsoft-workspace` source tree; not cross-checked against the exact release dunereco builds with) | Use `h.operator->()` and `sp.operator->()` (or `std::addressof(*ptr)` after an explicit `isNull()` check that throws), and correct the note. |
| 3 | minor | `DisambigFromSpacePoints_module.cc:175-179` | Eager resolution of every space point `Ptr` (documented) also calls `spFromHit.at(i)` for every hit, including collection hits and hits whose channel has no wires. The original called it only for induction hits with wires and in the output loop. If the hit to space point Assns is invalid, `throwIfInvalid` can now fire where the original did not (only when no hit gets assigned), and per-hit warnings that used to precede the throw are no longer emitted. Unusual input. | base L295-L307, L246; canvas `FindManyP.h` L347-L351 | Accept and add the `at()` part to the documented deviation, or resolve lazily. |
| 4 | minor | `MIGRATION_NOTES.md:7`, `:172` | Notes metadata is wrong for this tree. The working tree and branch are given as `...-v1` (actual `...-r3`, branch `phlex-extract/DisambigFromSpacePoints-r3`). Issue 10 cites a `phlex-tester` finding pinned in `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`, and neither exists in the worktree or the notes directory. | `git branch --show-current`; `ls` of `HitFinderDUNE/` and the notes dir | Update the path and branch. Drop issue 10 or attach the test and `TESTS.md`. |
| 5 | minor | `MIGRATION_NOTES.md` section 7 | No Phlex-era home is named. `dune-repo-map.md` maps `dunereco` to `dune-fd-reco` or one of the protoDUNE repos, decided by which production jobs run it. Here both `dunefd_disambigfromsp` and `pdune_disambigfromsp` (PD-HD via `run_wire_filter.fcl`) use it, so the candidates and the deciding question should be stated. The DUNE-include dependency table is trivially complete (only the self-include). | `dune-repo-map.md` L38 | Add the home, or candidates plus the deciding question. |
| 6 | minor | `HitFinderDUNE/CMakeLists.txt:2-25` | The algorithm is globbed into the existing `HitFinderDUNE` library, whose `LIB_LIBRARIES` already link `art::Persistency_Common`, `art::Framework_Services_Registry`, `larsim` services, and others. Nothing was added, but a future Phlex plugin linking this library pulls in art. The notes also do not say that a fresh CMake configure is needed for the `art_make` glob. | CMakeLists L18-L21 | Note it as a pass-2 item (separate framework-free algorithm library). State the reconfigure requirement in the validation plan. |
| 7 | minor | `MIGRATION_NOTES.md` section 8 | The validation plan does not compare log output, so it would not catch finding 1 or the moved `LogInfo` calls. Everything else is good: unsorted product comparison, Assns pairs in produced order, the `first`/`drop`/`UseNeighbors: false`/`ExcludeTPCs` overrides, and the `hitstats` tree. | | Add a diff of the `DisambigFromSpacePoints` MessageLogger category for each configuration. Note that `"first"` is the base default. |
| 8 | nit | `MIGRATION_NOTES.md:43`, `:134` | Line references are off by one: `eventHits` is at module L162 (not L161), and `assignEveryAllowedWire` is at alg L259-L282 (not L283). | | Fix the numbers. |

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| L46-L49 typedefs | `Alg.h:29-32` | identical | same namespace `dune`; no other definitions in dunereco |
| L53-L66 Config | module L55-L67 | identical | names, types and comments unchanged |
| L122-L132 ctor init | module L102-L108, `make_cfg` L91-L100 | mechanical edit OK | every field maps to a same-named config field; no shared-type mixups (`numNeighbors` is `size_t`, `maxDistance` is `float`, as before); init order matches declaration order |
| L134-L158 ctor body | module L110-L134 | identical | `fCfg.numNeighbors` check; same products, service, tree and branches |
| L163-L190 produce prologue | module L139-L165 | mechanical edit OK | `fill_ptr_vector` replaced by `*hitsHandle`; keys equal indices |
| L192 detProp | module L167 | identical | once per event |
| L194-L212 spToTPC | `Alg.cxx:288-312` (via module L170-L174) | mechanical edit OK | same iteration and dereference order over hits; null-Ptr path differs (finding 2) |
| L214-L219 locals, reserve | `Alg.cxx:327-332` | identical | `hitToWire` is now `res.hitToWire`, reserved at the same point before any insert |
| L221-L232 pass sequence, LogInfo, leftovers | `Alg.cxx:334-348` | identical | LogInfo text and order unchanged |
| L278-L363 runOnSpacePoints | `Alg.cxx:30-118` | mechanical edit OK | `hit.key()` became `i`; `sp.key()`/`sp->` became `sp.key`/`sp.spacePoint->`; counters went to `stats` with the same reset points |
| L365-L467 resolveUnassigned | `Alg.cxx:120-227` | mechanical edit OK | `fMaxDistance`/`fExcludeTPCs` became `cfg.*`; all arithmetic types unchanged |
| L469-L493 assignFirstAllowedWire | `Alg.cxx:229-257` | **CHANGED** | warning text at L255 (finding 1) |
| L495-L516 assignEveryAllowedWire | `Alg.cxx:259-282` | identical | |
| L234-L269 output loops | module L191-L226 | mechanical edit OK | `*(eventHits[key])` became `eventHits[key]`; `spFromHit.at(eventHits[key].key())` became `spFromHit.at(key)`; same iteration over `result.hitToWire` then `result.hitToNWires` |
| L271-L275 fill, put | module L228-L232 | identical | unconditional puts |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-L174 | resolves `hitsFromSp` into `Hit const*` | Same `at()` order as before; a null `Ptr` now becomes a null deref instead of `art::Exception` (finding 2) |
| module L175-L179 | resolves `spFromHit` into `SpacePointRef` for every hit | Eager `Ptr` resolution (documented); extra `at()` calls (finding 3); a null `Ptr` becomes a null deref (finding 2) |
| module L181 | `DisambigResult result = disambiguateHits(...)` | prvalue elision; inside, `return res;` gives NRVO or a move, and a move keeps `unordered_map` node order, so ordering is preserved |
| module L184-L189 | copies stats into branch buffers | Same values as the original write sites; `fNMissedByNeighbors` still written only when `useNeighbors`, so the original indeterminate value is preserved (documented, issue 1) |
| `Alg.h:53-57` `std::array{}` value-init | zeroes stats | Not observable: every field is reset before use in the paths that copy it out |

## Validation plan

It mostly works as a test. It runs FD and PD-HD jobs (`repeat`) plus overrides for `first`,
`drop`, `UseNeighbors: false` and `ExcludeTPCs`, which covers every branch the extraction
touched. It compares hits and both Assns unsorted, in produced order, which would catch an
ordering regression. It compares `hitstats` with the documented `fNMissedByNeighbors`
exception. It does **not** diff log output, so finding 1 would pass unnoticed (finding 7).
The null-`Ptr` path (finding 2) cannot be exercised with ordinary files. That is acceptable
once the code is fixed.

## Compile-risk review

- API signatures checked against `<LArSoft checkout>` (larcorealg,
  lardataalg, lardataobj, lardata; checkout dated 2026-02-24, not confirmed to be the exact
  release dunereco `5d619357` builds with):
  - `WireReadoutGeom::ChannelToWire(raw::ChannelID_t) const`, `Plane(PlaneID const&) const`;
  - `PlaneGeo::WireCoordinate(Point_t const&)`, `WirePitch()`;
  - `DetectorPropertiesData::GetXTicksCoefficient(int,int) const`;
  - `SpacePoint::position()` returns `geo::Point_t`;
  - `Hit::SignalType/WireID/PeakTime/Channel`;
  - `HitCreator(recob::Hit const&, geo::WireID const&)`.

  All usages match.
- canvas `Ptr`/`FindManyP` were read from the pixi `larsoft-workspace` source tree (version
  not matched to the build).
- Every identifier in the moved code resolves: `using dune::...` sits in the anonymous
  namespace, and `geo::`/`recob::`/`detinfo::` come in through the header includes. The
  includes cover `<algorithm>` (`std::remove`) and `<cmath>` (`std::fabs`). No transitional
  framework include appears in the public header.
- The declaration and definition of `mapSpacePointsToTPC` and `disambiguateHits` match.
  Parameter names differ, which is harmless. No functions are defined in the header. No
  move-only copies or lambdas. No C++20-only constructs; the aggregate init
  `SpacePointRef{sp.key(), &(*sp)}` has no narrowing.
- No symbol collisions in dunereco for the new public names.
- Build: `art_make` globs the `.cxx` into `HitFinderDUNE`, which already links
  `larcorealg::Geometry`, `lardataalg::DetectorInfo`, `lardataobj::RecoBase` and
  `messagefacility::MF_MessageLogger`. The plugin links `HitFinderDUNE`. This needs a fresh
  configure (finding 6).
- Residual risk is low. Unqualified `size_t` in the header relies on the global name from
  `<cstddef>`/std headers, as the original did.

## Guide conformance

- Separation checks: `ServiceHandle` appears only in the module (L123, L127, L167). The
  geometry and `detProp` are passed explicitly. No helper receives the event or a handle.
  Nothing event-scoped is cached across events (`SpacePointRef` pointers live only for the
  call).
- Extraction checklist 1 to 5: met. The core is describable without callbacks; all inputs are
  in the signature; outputs are returned in `DisambigResult`; config is collected in
  `make_cfg`; the 9 logging items are transitional and marked. The internal helpers keep
  reference out-parameters, but they are file-local, which is justified.
- Binding plan: plausible. Event-layer `transform` with unlimited concurrency fits the
  re-entrant code: no statics, and const geometry and `detProp`. The `hitstats` `observe` is
  `serial` with the tree as a serialized resource, and `MonitoringPlots` is a
  registration-time switch. Blockers are named: persistable associations, `HitCreator` from
  an art-dependent library, and conditions access. No unfold or fold is planned, so the
  layer, move and `send()` rules do not apply. The Phlex-era home is missing (finding 5).

## Notes accuracy

- Section 6 L198 and the `.cxx` header comment claim the warning text was kept and the edits
  were mechanical only. False (finding 1).
- Section 2 #13 says `FindManyP` dereference "raises the same art exception". This does not
  hold for null `Ptr`s with `operator*` (finding 2).
- The worktree path and branch are given as `-v1`; the test file and `TESTS.md` are cited but
  absent (finding 4).
- Off-by-one line references (finding 8).
- All other claims checked against the code hold: the contract, the 9 transitional rows, the
  stats write paths, ordering preservation, and the eager space point deviation.
