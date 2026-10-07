# Static verification: `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **FAIL** |
| Findings | 1 blocker, 1 major, 5 minor, 1 nit |
| Working tree and base | `<worktree-r9>` against `5d619357` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints-r9/MIGRATION_NOTES.md` |
| Verifier / model / date | phlex-verifier, Opus 5.5 (`claude-opus-5-5`), 2026-10-04 |
| Compilation | none, by design |

## Summary

- The module was split into a thin art producer and free functions in
  `DisambigFromSpacePointsAlg.{h,cxx}`. The framework contract is unchanged, purity is clean
  apart from 9 documented MessageLogger items, and almost every moved statement is identical.
- **One statement was dropped.** In `assignFirstAllowedWire` the `ExcludeTPCs` loop is gone
  (`DisambigFromSpacePointsAlg.cxx:249-250`). With `MoveLeftovers: "first"` (the
  `standard_disambigfromsp` default) and a non-empty `ExcludeTPCs`, leftover hits are now put
  on a wire segment in an excluded TPC. That changes the output hits and both association
  products. The notes call this function "moved verbatim".
- The same deletion leaves `const size_t tpc` unused (line 247). dunereco builds with
  `DIAGS CAUTIOUS WERROR` (top-level `CMakeLists.txt:22-23`), so `-Wunused-variable` is very
  likely a hard error.
- The notes' line numbers past line 249 of the `.cxx` are one too high everywhere, consistent
  with this line being removed after the notes were written. `extraction.patch` matches the
  working tree byte for byte, so the patch also lacks the line.
- Before any build: restore
  `for (auto t : cfg.excludeTPCs) { if (t == tpc) { allowed = false; break; } }` between
  `bool allowed = true;` and `if (allowed)` in `assignFirstAllowedWire`, then re-verify.
  Everything else reviewed is behaviour-preserving or a documented, accepted deviation.

## Original module in brief

Written before reading the new code or the notes.

`DisambigFromSpacePoints` is an `EDProducer` that rewrites every hit with a definite
`geo::WireID`. Collection hits take the channel's first wire. Induction hits vote per TPC using
the space points associated with them (a segment is a match within 1 wire pitch of the space
point's wire coordinate; the space point's TPC comes from one of its collection hits). Hits left
unresolved are optionally placed with a nearest-neighbour score over already resolved hits in
the same cryostat/TPC/plane, skipping `ExcludeTPCs`. Leftovers go on every allowed segment
(`"repeat"`), on the first allowed segment (`"first"`), or are dropped. Output: a new
`std::vector<recob::Hit>` plus hit-wire `Assns` via `HitCollectionCreator`, a copied
`Assns<recob::Hit, recob::SpacePoint>`, and, with `MonitoringPlots`, a `hitstats` TTree of
per-plane counts. Output order is the iteration order of two `std::unordered_map`s. The
contract is 8 validated FHiCL parameters, `declare_products(..., "", true, false)`, one
`produces<Assns<Hit,SpacePoint>>`, and services `WireReadout`, `DetectorPropertiesService`,
`TFileService`. Quirk: `fNMissedByNeighbors` is never written when `UseNeighbors` is false.

## Automated checks

Paths: `S=$KIT/skills/art-phlex-extract/scripts`, `D=<wt>/dunereco/HitFinderDUNE`.

| Check | Command | Result |
|---|---|---|
| Scope | `git status --short`; `git diff --stat 5d619357` | 3 files: `DisambigFromSpacePointsAlg.cxx` (A, +352), `DisambigFromSpacePointsAlg.h` (A, +85), `DisambigFromSpacePoints_module.cc` (M). Nothing outside the module directory. No `CMakeLists.txt` change. |
| Patch vs tree | `diff extraction.patch <(git diff 5d619357)` | identical |
| Purity | `check_purity.py $D/DisambigFromSpacePointsAlg.h $D/DisambigFromSpacePointsAlg.cxx` | PASS: 0 errors, 0 warnings, 9 transitional (all MessageLogger) |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:5d619357:<module> --after <module>` | contract unchanged (13 items); `contract.before.txt` = `contract.after.txt` |
| Algorithm inventory | `art_inventory.py report <alg files>` | only `messagefacility` include and 8 `mf::Log*` calls |
| Module inventory | `art_inventory.py report <module>` | all framework constructs in the module; member writes in `produce` only: `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints`, `fNMissedByNeighbors` (L184-L188) |
| Transitional markers vs notes | `git diff 5d619357 \| grep '^+.*PHLEX-TRANSITIONAL'` | 9 markers (`.cxx` 16, 49, 145, 176, 241, 253, 334, 340, 346), one per logging item; all 9 are in the notes' table with a valid reason. The table's line numbers for the last four are off by one (254, 335, 341, 347 in the tree). |
| Agent-addressed instructions | grep of patch, notes, contract files | none found |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| F1 | **blocker** | `DisambigFromSpacePointsAlg.cxx:249-250` | `ExcludeTPCs` filter dropped from `assignFirstAllowedWire`. With `MoveLeftovers: "first"` and non-empty `ExcludeTPCs`, a leftover hit now goes on the first segment even in an excluded TPC; where the original would have taken a later segment or logged "None of wires is allowed for this hit???" and dropped the hit, the new code emits a hit, its hit-wire association and its hit-space point associations. Data products change. The notes (section 4, "moved verbatim", and checklist item 2) say otherwise, so the notes hide the change. `cfg` is now an unused parameter of this function. | Base L486-L488 has `bool allowed = true; for (auto t : fExcludeTPCs) {...} if (allowed) {...}`; tree L249-L250 has only `bool allowed = true; if (allowed) {...}`. `extraction.patch` hunk at patch L255-L256 vs removed lines L882-L884. In-repo FHiCL: `standard_disambigfromsp` uses `"first"` (`hitfindermodules_dune.fcl:23`); all in-repo `ExcludeTPCs` are `[]`, so in-repo jobs do not hit it, but any override (the FHiCL comment at L19 invites one for TPCs with no drift) does. | Restore `for (auto t : cfg.excludeTPCs) { if (t == tpc) { allowed = false; break; } }` between L249 and L250. Then update the notes' line numbers. |
| F2 | major | `DisambigFromSpacePointsAlg.cxx:247` | `const size_t tpc = cwids[w].TPC;` is now unused (consequence of F1). dunereco sets `cet_set_compiler_flags(DIAGS CAUTIOUS WERROR ...)` (`CMakeLists.txt:22-23`); CAUTIOUS includes `-Wall`, so `-Wunused-variable` becomes an error with GCC and Clang. | Tree L247 vs no later use of `tpc` in L244-L251. | Fixed by F1. Needs build to confirm; high likelihood. (cetmodules flag definitions not read: outside the allowed read set.) |
| F3 | minor | `DisambigFromSpacePoints_module.cc:173`, `:178` | Boundary glue resolves `art::Ptr`s with `&(*h)` / `&(*sp)` where the original used `h->` / `sp->`. Space points are now dereferenced for every association, not only those that pass the TPC-map and TPC checks (documented in notes section 4). Separately, `Ptr::operator*` and `operator->` may differ on a null `Ptr` (throw versus null return); not documented. | Base L201, L210, L328 vs tree L173, L178. | Accept as documented error-path deviation; add the `operator*` vs `operator->` null behaviour to the notes. Unverified assumption: canvas `Ptr.h` was not available in the allowed read set. Only reachable with corrupt or unusual input. |
| F4 | minor | `MIGRATION_NOTES.md:7`, `:172` | Header names working tree `...-DisambigFromSpacePoints-v1`, branch `phlex-extract/DisambigFromSpacePoints-v1`; the reviewed tree is `...-r9`. Pre-existing issue 10 cites `phlex-tester`, `DisambigFromSpacePointsAlg_test.cc` and `TESTS.md`; none exist in the worktree or the notes directory. | `find <wt> -name 'DisambigFromSpacePointsAlg_test*' -o -name TESTS.md` returns nothing; notes dir has only notes, contract files, patch. | Correct the header; drop or substantiate issue 10. |
| F5 | minor | `MIGRATION_NOTES.md:50`, `:199-201`, `:248`, `:43` | Line numbers off by one: `LogWarning` at 254 (notes 255), `LogInfo` at 335/341/347 (notes 336/342/348), `return res` at 349 (notes 350), `assignEveryAllowedWire` L258-L281 (notes L259-L283), `eventHits` at module L162 (notes L161). Consistent with one `.cxx` line removed after the notes were written (F1). | Compare notes against tree. | Regenerate line references after the F1 fix. Ask how the line came to be removed after the notes were drafted. |
| F6 | minor | `MIGRATION_NOTES.md:225-236` | Validation plan lists `MoveLeftovers: "first"` and "a non-empty `ExcludeTPCs`" as separate overrides. F1 shows only together, and only when a leftover hit's first segment is in an excluded TPC. In-repo configs all have `ExcludeTPCs: []`. | Plan text. | Run `"first"` + non-empty `ExcludeTPCs` (choose a TPC present in the wrapped segments of the sample) together, and `"repeat"` + non-empty `ExcludeTPCs`, `UseNeighbors` true and false. Keep the unsorted comparison. |
| F7 | minor | `MIGRATION_NOTES.md` section 7 | No Phlex-era home repository named. `dune-repo-map.md` maps `dunereco` to `dune-fd-reco` (or a protoDUNE repo when only one uses it). In-repo FHiCL uses this module for FD (`dunefd_disambigfromsp`) and ProtoDUNE (`pdune_disambigfromsp`, `run_wire_filter.fcl:43`). | Notes section 7. | Name `dune-fd-reco` as the candidate, with the deciding question: which detectors' production jobs in `dunesw` run it. No DUNE art-era includes in the algorithm files, so no dependency table entries are missing. |
| F8 | nit | `DisambigFromSpacePointsAlg.cxx:253` | `// PHLEX-TRANSITIONAL` comment sits between the `if` body and its `else`. Valid C++, but odd to read. | Tree L252-L254. | Optional: move it above L252. |

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| typedefs L46-L49 | `.h` L29-L32 | identical | No other `plane_keymap` etc. in `dunereco/`. |
| Config L53-L66 | module L55-L68 | identical | names, types, comments unchanged |
| ctor init L122-L132 | module L102-L108, `make_cfg` L91-L100 | mechanical edit OK | each Atom maps to the same-typed cfg field; no shared-type swap (`useNeighbors` bool, `numNeighbors` size_t, `maxDistance` float, `moveLeftovers` string, `excludeTPCs` vector) |
| `NumNeighbors < 1` throw L134-L137 | module L110-L113 | identical | |
| `declare_products`, `produces` L142-L145 | module L118-L121 | identical | |
| geometry handle L147 | module L123 | identical | |
| TFileService/TTree L149-L158 | module L125-L134 | identical | branches still bound to module members |
| `fRun`, `fEvent`, handles L163-L167 | module L139-L143 | identical | |
| `FindOneP<Wire>`, `hcol`, `assns` L172-L183 | module L148-L159 | identical | |
| `fill_ptr_vector` L186-L187 | module L162 | mechanical edit OK | `std::vector<Hit> const&`; key = index |
| `FindManyP` x2 L189-L190 | module L164-L165 | identical | |
| `detProp` L192 | module L167 | identical | same position relative to the TPC-map loop |
| spToTPC loop L194-L212 | `.cxx` `mapSpacePointsToTPC` L287-L311 | mechanical edit OK | `Ptr` copy → reference to `Hit const*` vector; same order |
| locals, reserve L214-L219 | `.cxx` L326-L331 | identical | maps now members of `res`; same reserve before first insert |
| `runOnSpacePoints` call + LogInfo L221-L222 | `.cxx` L333-L335 | mechanical edit OK | |
| `UseNeighbors` branch L224-L228 | `.cxx` L337-L342 | mechanical edit OK | `fNumNeighbors` → `cfg.numNeighbors` |
| leftover switch L230-L232 | `.cxx` L344-L347 | mechanical edit OK | same string compares, same order |
| `hitPtrMaker`, hitToWire loop L234-L251 | module L191-L208 | mechanical edit OK | `*(eventHits[key])` → `eventHits[key]`; `spFromHit.at(eventHits[key].key())` → `spFromHit.at(key)`; iterates `result.hitToWire`, the same map object moved out (move keeps node order) |
| hitToNWires loop L253-L269 | module L210-L226 | mechanical edit OK | as above |
| `Fill`, `put_into`, `put` L271-L275 | module L228-L232 | identical | unconditional, same order |
| `runOnSpacePoints` L278-L363 | `.cxx` L30-L118 | mechanical edit OK | `fNHits` etc. → `stats.*` (`int`); `hit.key()` → `i`; `sp.key()`/`sp->` → `sp.key`/`sp.spacePoint->`; `fWireReadoutGeom->` → `wireReadout.`; float/size_t types unchanged |
| `resolveUnassigned` L365-L467 | `.cxx` L120-L227 | mechanical edit OK | `fMaxDistance` → `cfg.maxDistance`, `fExcludeTPCs` → `cfg.excludeTPCs`; `<`/`>` and float casts identical; `result` map and erase/insert unchanged |
| `assignFirstAllowedWire` L469-L493 | `.cxx` L229-L256 | **CHANGED** | ExcludeTPCs loop (base L487) missing: F1 |
| `assignEveryAllowedWire` L495-L516 | `.cxx` L258-L281 | mechanical edit OK | exclude loop present (L277) |
| `DEFINE_ART_MODULE` L518 | module L235 | identical | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| module L170-L174 | builds `hitsPerSpacePoint` with `&(*h)` for every hit of every space point | Same Ptrs dereferenced in the same order as base L197-L211 (which dereferenced all of them). Only difference is `operator*` vs `operator->` on a null Ptr (F3). |
| module L175-L179 | builds `spacePointsPerHit` with `{sp.key(), &(*sp)}` for every hit | Calls `spFromHit.at(i)` for all hits (original only for induction hits with wires; harmless for a valid `FindManyP`). Dereferences every space point eagerly (documented; F3). |
| module L181 | calls `disambiguateHits` | none |
| module L184-L189 | copies `stats` into branch members; `fNMissedByNeighbors` only when `useNeighbors` | Matches the original write sites: `fNHits`/`fNMissedBySpacePoints` every event, `fNMissedByNeighbors` only on the neighbour path, so its stale/indeterminate value with `UseNeighbors: false` is preserved, as documented. |
| `.cxx` L321 `DisambigResult res{}` | value-initialises stats | Not observable: the module does not copy `nMissedByNeighbors` when `useNeighbors` is false. |
| `.cxx` L349 `return res` | NRVO or implicit move | Move of `unordered_map` keeps nodes and bucket array, so iteration order is unchanged. |

Other step-4 checks: no random draws; no early returns added; product puts unconditional as
before; message text and order unchanged (the three `LogInfo`s moved into the algorithm, same
sequence relative to the warnings); `detProp` fetched once per event as before; the `Hit const*`
and `SpacePoint const*` pointers live only within `produce`.

## Validation plan

The plan builds both refs in one environment, runs FD and ProtoDUNE-HD jobs, compares hits and
both association products **unsorted** (right, since order is claimed identical), and covers
`hitstats` with the documented exception. It would catch F1 only if `"first"` and a non-empty
`ExcludeTPCs` are run together on events where a leftover hit's first segment lies in an
excluded TPC (F6). The unit-test idea does not exercise the leftover modes; a case with
`"first"` and an excluded first-segment TPC would pin F1 cheaply.

## Compile-risk review

Checked by reading:

- All identifiers in moved code resolve: former members became `cfg.*`, `stats.*` or
  parameters; typedefs are in the header in `namespace dune` and pulled into the anonymous
  namespace by `using`.
- Includes: `WireReadoutGeom.h`, `PlaneGeo.h`, `geo_types.h`, `DetectorPropertiesData.h`,
  `Hit.h`, `SpacePoint.h` all exist in the LArSoft checkout (`larcorealg` develop `b170a9c`,
  2025-08-25; whether this matches dunereco's build release is not established).
  `WireReadoutGeom::ChannelToWire`, `Plane(PlaneID const&)`, `GetXTicksCoefficient(int,int)`,
  `HitCreator(Hit const&, WireID const&)` signatures confirmed. The MessageLogger include is in
  the `.cxx` only.
- Declaration and definition of `disambiguateHits` and `mapSpacePointsToTPC` match; call site
  matches. No header-defined functions. No move-only copies. No C++20-only constructs.
- Build: `art_make` globs the new `.cxx` into `HitFinderDUNE`, which already links
  `lardataobj::RecoBase`, `larcorealg::Geometry`, `lardataalg::DetectorInfo`,
  `messagefacility`; the plugin links `HitFinderDUNE`. A fresh CMake configure is needed.
  The library also holds art-dependent code, so it is not yet an art-free library a Phlex
  plugin could link alone; acceptable for pass 1.
- **F2**: unused `tpc` under `-Wall -Werror`: needs build to confirm, high likelihood.
- `cfg` unused in `assignFirstAllowedWire`: only `-Wunused-parameter` (`-Wextra`), not in
  CAUTIOUS; disappears with the F1 fix.
- Unverified: canvas `Ptr::operator*` vs `operator->` null semantics (F3).

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (L123, L127, L167); `wireReadout` and
  `detProp` passed explicitly; no helper receives the event or a handle; no event data cached
  across events. Pass.
- Extraction checklist 1 to 5: 1 yes; 2 yes; 3 yes (`DisambigResult` by value); 4 yes
  (`make_cfg`); 5 yes (9 logging items, table matches markers). The checklist evidence is
  undermined only by the false "verbatim" claim in F1.
- Binding plan: event-layer `transform` for `disambiguateHits`, `observe` for `hitstats` with
  serial concurrency for ROOT, blockers named (no persistable associations, `HitCreator` is
  art-side, conditions for `DetectorPropertiesData`). Algorithm inputs are const; re-entrancy
  claim holds (no statics or mutable members; `mf` thread-safe). Plausible. Missing Phlex-era
  home repository (F7).

## Notes accuracy

- Section 4 "assignFirstAllowedWire L469-L493 → alg L229-L256" listed under "moved verbatim":
  false; one statement missing (F1).
- Header worktree/branch name `-v1` vs reviewed `-r9` (F4).
- Pre-existing issue 10 refers to a tester, test file and `TESTS.md` that are not present (F4).
- Line numbers after `.cxx` L249 are one too high throughout sections 2, 4, 6 and 9 (F5).
- Everything else checked (contract, purity counts, inventory mapping, deviation list,
  pre-existing issues 1 to 9) matches the code.
