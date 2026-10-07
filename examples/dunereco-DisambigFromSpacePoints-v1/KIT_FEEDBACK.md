# Kit feedback: DisambigFromSpacePoints, v1 re-run

Extractor run on `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` at `5d619357`,
static only. Read: `agents/phlex-extractor.md`, `AGENTS.md`, `skills/art-phlex-extract/SKILL.md`,
all five references, the template, and both scripts. `examples/` and the old run were not read.

## Unclear, wrong, or slow

1. **The FHiCL grep in SKILL.md step 1 fails in zsh.**
   `grep -rn "module_type: *<Module>" --include=*.fcl <repo>` is unquoted. In zsh it aborts with
   `no matches found: --include=*.fcl` before grep runs. Repro:
   `zsh -c 'cd /tmp && grep -rn x --include=*.fcl .'`. Fix: `--include='*.fcl'`. I lost one
   tool call to this.

2. **The FHiCL grep searches only the module's repository, which misses the configurations that matter.**
   In dunereco the module appears only in the prolog `standard_disambigfromsp`. Production
   jobs live in `dunesw` (`workflow_reco_dune10kt.fcl`, `protoDUNE_*`, `standard_reco_protodunehd_*`)
   and all of them use `MoveLeftovers: "repeat"`, which the prolog default (`"first"`) hides.
   Suggest: also grep for the prolog names (`@local::<prolog>`) across sibling repositories
   (`dunesw`, `duneprototypes`) when they are checked out.

3. **Step 1 snapshots `contract.before.txt` from the working tree, but step 8 diffs against `git:<base>:`.**
   If the worktree is not exactly at the base, or the extractor has already edited it, the
   before file is wrong. I regenerated it with
   `python3 $S/art_inventory.py --repo <wt> contract git:5d619357:<module path> > contract.before.txt`.
   Suggest that step 1 show the `git:<base>:` form.

4. **Deliverables disagree between the manager and the skill.**
   The manager prompt listed MIGRATION_NOTES, the two contracts and KIT_FEEDBACK. SKILL.md
   deliverable 4 also requires `extraction.patch`. I produced it anyway. The orchestrate skill
   should pass the same list.

5. **Unordered-container iteration order is not covered.**
   SKILL.md step 5 says "a `std::map`'s iteration order is behaviour". Here the output hit
   order and the association order come from iterating a `std::unordered_map`. That order
   depends on bucket count (`reserve(eventHits.size())`) and insertion history across three
   passes. The rule "outputs returned by value, no out-parameters" pushes toward splitting the
   passes into functions that each return a new map and merge at the end, which would silently
   reorder the output. I kept one map threaded through file-local helpers with reference
   parameters and moved it out once. Suggest adding: "`std::unordered_map`/`unordered_set`
   iteration order is behaviour too: keep the same container object, the same `reserve`, and
   the same insert sequence; a move preserves it, a copy or merge into a new container may not."
   This was the most important decision in the run, and the kit did not prompt it.

6. **Eager versus lazy `art::Ptr` dereference has no recommended pattern.**
   `art-ptr-removal.md` (kit note) and SKILL.md step 4 correctly warn that resolving pointers
   up front moves the throw. They give two options: keep the dereference where it was, or
   check for null and throw. In extracted code the first option is impossible, because the
   algorithm cannot hold an `art::Ptr`. The second needs `art::Exception` in the algorithm or a
   change of exception type. Both references also say "confirm in the canvas version", but no
   canvas source is available locally (only LArSoft repositories under `<LArSoft checkout>`),
   so I could not check whether `Ptr::get()` returns null or throws. I resolved space points
   eagerly with `&*ptr` (same exception type) and recorded it as an error-path deviation for
   a human. Suggest: (a) record the actual canvas behaviour of `operator*`, `operator->` and
   `get()` in the reference, and (b) name an accepted pattern, for example "resolve eagerly
   with `*ptr` at the boundary and record it as an error-path deviation when the pointers
   point into a product the module already fetched with `getValidHandle`".

7. **Logging placement conflicts with message order.**
   `larsoft-boundary-patterns.md` says summary messages that use boundary values should be
   logged in the module. The module's three `LogInfo` summaries sit between algorithm passes
   that themselves emit `LogWarning`s. Logging them at the boundary would need the passes
   called separately from the module (orchestration at the boundary) or would reorder the log.
   I moved them into the algorithm as transitional. The kit should say which matters more:
   log order or a thin algorithm.

8. **`art_inventory.py report` has noise in "member state written outside constructors".**
   `fNHits in runOnSpacePoints` is listed three times for L287 (one per statement on the
   line), and `L271 fTree in produce` is reported as a write when the line is `fTree->Fill()`
   (a call through the pointer, not a write to `fTree`). Repro:
   `python3 $S/art_inventory.py --repo <wt> report git:5d619357:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`
   (or the working-tree path at base). The report also does not flag members that are read
   (TTree branches) but never initialised, which is how the `fNMissedByNeighbors`
   indeterminate-value issue arose. A "member never initialised in the constructor but bound
   to a TTree branch" check would have found it directly.

9. **The contract does not cover helper constructor arguments or put conditions.**
   It lists `declare_products(...)` arguments, but not `HitCollectionCreator hcol(evt, doWireAssns, doRawDigitAssns)`,
   which also decides whether the hit-wire association is filled. Section 5 asks for a hand
   check only when products are declared some other way. Suggest it also say to check the
   collection helper's constructor arguments and every `put`/`put_into` path by hand.

10. **The template's "Kit @ sha" cannot be filled.** The kit working tree has no commits:
    `git -C $KIT rev-parse --short HEAD` gives `fatal: Needed a single revision`. I wrote
    "uncommitted". If runs are meant to be comparable, the orchestrator should record a kit
    commit or a content hash.

11. **No binding-plan pattern for consumed associations or art-dependent output helpers.**
    `binding-crosswalk.md` lists "persistable associations" as a gap, but this module
    *consumes* associations (both directions) as essential inputs and builds its output with
    `recob::HitCreator` (in `lardata/ArtDataHelper`, an art-dependent library). A standard
    plan row for "association input becomes an upstream index-list product" and a note that
    `HitCreator`-style copy helpers need a framework-free equivalent would have saved time
    and made plans across modules consistent.

12. **The agent file names `model: sonnet`; this run was Opus.** The notes header records what
    actually ran. If the measurement compares models, the orchestrator should state the model
    in the dispatch.

## Load-bearing (worked well)

- SKILL.md step 3 rule "keep the write sites of members that feed monitoring output" mapped
  directly onto `fNMissedByNeighbors` being written only when `UseNeighbors` is true. Without
  it the obvious refactor (always copy the returned stats) would have changed the tree.
- "Keep exactly: types, container types, early `continue`, log text" plus "move code, don't
  rewrite" kept the helper bodies to mechanical edits, which makes the diff reviewable.
- `larsoft-boundary-patterns.md` "Validated configuration" (`make_cfg(Config const&)`) and
  "Detector clocks and properties" and "Geometry and wire readout" gave the exact boundary
  shape. "Collection helpers" correctly warned that `declare_products` declares products
  without a visible `produces<>`.
- The "Associations written by the module" note that `fill_ptr_vector` keys equal indices
  justified replacing `eventHits[key].key()` with `key`.
- `check_purity.py` accepting a `// PHLEX-TRANSITIONAL:` comment on the line above kept
  the moved one-liners unchanged. It passed first time: `python3 $S/check_purity.py <alg .h> <alg .cxx>`.
- `contract-diff --before git:<base>:... --after ...` worked first time and gave a clear
  "contract unchanged (13 items)".
- Telling the extractor to confirm whether the target class is shared (step 1) was quick
  here (`grep` found no other users of the typedefs or helpers).

## Cost

About 27 tool calls, including one lost to the zsh glob (point 1) and one long-running
`find /` I started while looking for canvas sources (point 6; my choice, not a kit
instruction).

## Tester feedback

1. The skill says to use LArSoft's geometry test environment when a function needs `geo::WireReadoutGeom`, but gives no way to decide quickly whether that is feasible. Here `WireReadoutGeom`'s constructor dereferences `GeometryCore::ROOTGeoManager()` and needs a builder and sorter, so a stub subclass is impossible, and `DetectorPropertiesData` needs more set-up. Add a short feasibility checklist (is there a default or test constructor; does the experiment have a standalone, non-art geometry setup; is a GDML in the checkout) so the tester reaches "needs fixture" in minutes.
2. The skill's example cites `geometry_standardchannelmapping_test.cxx`, but that fixture gives one wire per channel and cannot exercise multi-segment induction channels, which is the whole point of this module. Say so, and say which DUNE test (`dunecore/Geometry/test`) is the closest model and that it depends on `dunecore::ArtSupport`.
3. With a geometry-bound entry point (`disambiguateHits` takes `WireReadoutGeom const&` unconditionally), only the one geometry-free public helper (`mapSpacePointsToTPC`) was testable, so 10 of ~28 cases are written. The skill should tell the extractor, upstream, to keep geometry-independent logic (vote scoring, neighbour scoring, leftover policy over a `ChannelToWire` result) in functions that take plain data, so more can be tested without a fixture. Consider a note in `art-phlex-extract` or the tester's report asking the manager for that refactor as a follow-up.
4. "Add the test directory to the parent CMakeLists.txt only if not already there" is ambiguous when the package has no `test/` and `art_make` globs sources. I appended `add_subdirectory(test)` to the package `CMakeLists.txt` (after `art_make`/`install_*`), but also the rule "write only test files and the CMake lines that register them" does not say that editing a package CMakeLists counts. State it explicitly.
5. The library target name in the skill's cmake snippet is a placeholder. For `art_make(LIBRARY_NAME HitFinderDUNE)` in a package whose project is `dunereco` the target is `dunereco::HitFinderDUNE` by convention, but the repo only ever uses the bare name in `MODULE_LIBRARIES` and no test in the repo confirms the namespaced form. Tell the tester how to confirm (grep other packages for `dunereco::` usage) and that the answer is unverifiable without a configure.
6. Trace comments need line numbers in the original at the base ref. I took them from a `sed` print and was off by 2 to 4 lines at first. Recommend `git show <base>:<path> | grep -n` or `cat -n` of the exact range, and have the skill require the tester to re-verify every cited line against that output before finishing.
7. The skill does not say what to do with an oddity found while tracing that is not in the notes (here: a collection hit with an invalid TPC collides with the `InvalidID` sentinel, so the space point is skipped). I named the test `..._quirk` and recorded it in TESTS.md, and flagged it in the report; the skill should say to do this and to tell the manager to add it to the notes.
8. The rule "do not include art or FHiCL headers" is fine, but `recob::Hit` has a 19-argument constructor; the skill should suggest a small `makeHit(...)` helper that fills only the fields the algorithm reads, with a comment naming them (already implied, make explicit).
9. Not stated: when the skill's expected-value rule (trace from the original) can be satisfied by reading the original only, whether the tester must also diff against the extracted code. I compared the extracted `mapSpacePointsToTPC` with the original loop by eye (the loop bound changed from `spHandle->size()` to `hitsFromSp.size()`, equal for a `FindManyP`); a sentence on that comparison step would help.
