# Static verification (delta, revision 2): `DisambigFromSpacePoints` pass 1

| | |
|---|---|
| Verdict | **PASS WITH NOTES** |
| Findings | 0 blocker, 0 major, 1 minor, 3 nit |
| Working tree and base | `<worktree>` against `5d619357` |
| Scope | Delta review of revision 2 only: module L173 and L178 (`&(*h)` / `&(*sp)` to `h.operator->()` / `sp.operator->()`), notes section 4, patch consistency, remaining `&*` / `.get()` resolutions. Not a full re-verification. |
| Notes reviewed | `examples/dunereco-DisambigFromSpacePoints-v1/MIGRATION_NOTES.md` (section 3 inputs, section 4, section 8) |
| Verifier / model / date | phlex-verifier, claude-opus-5-5, 2026-10-06 |
| Compilation | none, by design |
| Previous VERIFICATION.md / REVIEW.md | not read before writing these conclusions (as instructed) |

## Summary

- Both changed lines now resolve `art::Ptr` with `operator->()`, which in canvas 3.17 is the exact
  function the original's `h->` / `sp->` called. The pointer values are identical, and null or
  unavailable `Ptr`s fail through the same code path (`parentProduct_()` throws
  `art::Exception(errors::ProductNotFound)`) instead of the revision 1 `*get()` null dereference.
- Types line up: `operator->()` is a `const` member returning `T const*`; the results feed
  `std::vector<recob::Hit const*>` and `SpacePointRef::spacePoint` (`recob::SpacePoint const*`);
  `Ptr::key_type` is `std::size_t`, matching `SpacePointRef::key`.
- `git diff HEAD` (without `index` lines) is byte-identical to `extraction-with-tests.patch`.
  `extraction.patch` equals the same diff minus the `add_subdirectory(test)` hunk in
  `CMakeLists.txt`, as expected.
- No `&*`, `&(*`, or `.get()` resolution of `art::Ptr` remains in the module, the algorithm files or
  the test.
- The notes' updated paragraph is accurate on the space-point path. It does not say that the hit
  path (L173) had the same revision 1 defect and was changed too (minor).

## Dependency version

- Read: `~/.cache/rattler/cache/pkgs/canvas-3.17.0-h39d6d14_0/source/canvas/Persistency/Common/Ptr.h`.
- Cross-check: `/cvmfs/larsoft.opensciencegrid.org/products/canvas/v3_17_01/source/canvas/Persistency/Common/Ptr.h`
  is identical (`diff` empty). v3_17_01 is the newest canvas on CVMFS. I did not trace the exact
  canvas pin for dunereco `v10_26_00d02`; any 3.17.x matches the file read.

## Original behaviour (read first)

- `produce` L195-L212: for each space point `i`, `auto hits = hitsFromSp.at(i)`; loop 1 (L199-L202)
  calls `h->SignalType()` / `h->WireID()` until the first collection hit (`break`); if none is found
  (no break, so every hit was dereferenced) it `continue`s; otherwise loop 2 (L208-L211)
  dereferences every hit again. Every hit `Ptr` of every space point is therefore dereferenced, in
  `(i, j)` order, before anything else in the event touches a space point `Ptr`.
- `runOnSpacePoints` L317-L328: `sp->position()` is called only when `spToTPC` contains `sp.key()`
  (L319-L320) and some candidate wire is in that TPC (L326). Other space point `Ptr`s are never
  dereferenced.

## Item 1: the two changed lines

| New (file:line) | Original | Value | Null `Ptr` | Unavailable product |
|---|---|---|---|---|
| module L173 `hitsPerSpacePoint[i].push_back(h.operator->())` | L201, L210 `h->SignalType()`, `h->WireID()` | identical: `operator->()` returns `reinterpret_cast<T const*>(core_.productPtr())` (Ptr.h L143-L152), the same pointer `h->` yields | same path. Ptr.h L146-L148: if `productPtr()` is null, `parentProduct_()`; with no product getter it throws `ProductNotFound` (Ptr.h L238-L260) | same path: `parentProduct_()` throws `ProductNotFound` ("cannot be found") |
| module L178 `SpacePointRef{sp.key(), sp.operator->()}` | L328 `sp->position()` | identical, as above | same path as `sp->`, earlier and unconditional | same path as `sp->`, earlier and unconditional |

Contrast with revision 1: `operator*()` is `*get()` (Ptr.h L130-L135) and `get()` is
`isNull() ? nullptr : operator->()` (Ptr.h L137-L141), so `&(*p)` on a key-null `Ptr` dereferenced
`nullptr` (undefined behaviour) where `p->` went into `operator->()`. Revision 2 removes that
difference.

Order and timing:

- Hits (L171-L174): every hit `Ptr` is resolved in `(i, j)` order before any space point, which is
  the order the original first dereferenced them. The first failing hit `Ptr` is the same one. Not a
  deviation, as the notes say.
- Space points (L176-L179): resolved for every hit and every associated space point, before
  `disambiguateHits` runs. The original resolved only those reaching L328. This throws earlier, and
  possibly where the original never threw, but only for a `Ptr` into a missing product or a null
  `Ptr`. On ordinary input the association points into the `SpModuleLabel` product already fetched
  by `getValidHandle` (module L143), so it cannot fire. This matches the kit's accepted pattern
  (`art-ptr-removal.md` L180-L189) and is recorded in notes section 4.

Callability and types:

- `FindManyP::at` returns `const_reference` to `std::vector<art::Ptr<T>>` (canvas v3_17_01
  `FindManyP.h` L197, L347-L348); `auto const & h` binds `art::Ptr<T> const&`.
  `operator->() const` (Ptr.h L144) is callable on it.
- Return type `T const*` (Ptr.h L143): `recob::Hit const*` matches
  `std::vector<std::vector<recob::Hit const*>>` (module L170; Alg.h L69, L79);
  `recob::SpacePoint const*` matches `SpacePointRef::spacePoint` (Alg.h L47-L50).
- `sp.key()` returns `key_type = std::size_t` (Ptr.h L77), so brace-initialising
  `SpacePointRef::key` (`size_t`) does not narrow.
- The algorithm uses the pointers with `->` only, with no null checks
  (`DisambigFromSpacePointsAlg.cxx` L83, L299, L308), so the change does not affect behaviour
  downstream.

## Item 2: notes accuracy

Notes L147-L163 (section 4, "Intentional deviations") and L110-L111 (section 3 inputs):

- "resolves every `art::Ptr<recob::SpacePoint>` ... with `sp.operator->()` ... (module L178)":
  correct.
- "The original dereferenced a space point only when its key was in the TPC map and a candidate
  wire was in that TPC (original L328)": correct (base L319-L328).
- "`operator->()` is the same code path as the original `sp->`": correct.
- "a null or unavailable `Ptr` throws `ProductNotFound` from `parentProduct_()`": correct for a
  default-constructed null `Ptr` (no product getter) and for a missing product. It is
  over-general for a key-null `Ptr` whose product *is* found (see nit N1). There is no behavioural
  consequence, since the original takes the same path.
- "An earlier revision used `&*sp`, which in canvas 3.17 is `*get()` and dereferences `nullptr` for
  a null `Ptr`": correct (the code was spelled `&(*sp)`, same thing). Incomplete: revision 1 also
  used `&(*h)` at L173 with the same defect, and the `hitsFromSp` bullet (L160-L163) does not
  mention it (finding M1).
- "`hitsFromSp` is also resolved eagerly (module L173) ... same order. The first failing `Ptr` is
  the same, so this is not a deviation": correct for revision 2 (see Item 1).

## Item 3: patch consistency

```
git -C <wt> diff HEAD | grep -v '^index ' > wt.diff
grep -v '^index ' extraction-with-tests.patch > patch.diff
diff wt.diff patch.diff            # empty, 1130 lines each
```

Identical. `extraction.patch` (without `index` lines) equals the diff of the four non-test files
except for the `add_subdirectory(test)` hunk in `dunereco/HitFinderDUNE/CMakeLists.txt`, which
belongs to the tests patch. `git status`: 6 paths (CMakeLists, Alg.h, Alg.cxx, module, test
CMakeLists, test source), with no stray files. The kit repository has no commits, so I could not
diff revision 1 against revision 2 at the patch level. The only `art::Ptr` resolution sites in the
module are L173 and L178, and both now have the revision 2 form.

## Item 4: remaining `&*` / `&(*` / `.get()` resolutions

```
grep -n -E '&\s*\*|&\s*\(\s*\*|\.get\(\)|operator->|art::Ptr|Ptr<' \
  DisambigFromSpacePoints_module.cc DisambigFromSpacePointsAlg.h DisambigFromSpacePointsAlg.cxx \
  test/DisambigFromSpacePointsAlg_test.cc
```

Hits: module L173 and L178 (`operator->()`), module L191 (`art::PtrMaker`, not a resolution), and
Alg.cxx L7 (a comment). None of the `&*`, `&(*` or `.get()` forms remain. `check_purity.py` on the
algorithm files: `PASS: 0 error(s) across 2 file(s)` (transitional MessageLogger lines only,
unchanged by this revision).

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| M1 | minor | `MIGRATION_NOTES.md` L156-L163 | The revision note names only `&*sp`. Revision 1 also resolved hits with `&(*h)` (module L173), which had the same null-dereference defect, and revision 2 changed it too. The `hitsFromSp` bullet does not say so, and a reader could think the hit path was always correct. | Task brief: both L173 and L178 changed; Ptr.h L130-L141 (`operator*` is `*get()`, `get()` is null for a key-null `Ptr`). | In the L156-L159 sentence, say "used `&(*sp)` and `&(*h)` (module L178, L173)". Or add to the `hitsFromSp` bullet: "revision 1 used `&(*h)`; now `h.operator->()`, the same path as the original `h->`". |
| N1 | nit | `MIGRATION_NOTES.md` L156-L157 | "a null ... `Ptr` throws `ProductNotFound`" holds when the `Ptr` has no product getter or its product is missing. A key-null `Ptr` (`isNull()` is key-based) whose product is found goes to `getElementAddress` with an invalid key instead. The original `p->` does the same, so behaviour is unchanged; only the wording is too broad. | Ptr.h L203-L214 (`isNonnull` checks `key_` only), L144-L152; Wrapper.h L324-L339 (canvas v3_17_01). | "a null or unavailable `Ptr` takes the same path as the original `p->` (for a missing product, `ProductNotFound` from `parentProduct_()`)". |
| N2 | nit | module L176-L179; notes L147-L155 | Because space point resolution is eager, on corrupt input the throw now comes before any `runOnSpacePoints` output: no "No wires for this channel???" warnings (base L295) and no partial `fNHits` writes (base L299, L305) before the exception. The tree is not filled on either path, and every counter is overwritten in the next event, so only the log text differs, and only on an event that throws. | base L287-L310 vs module L171-L181. | Optional: add "log lines from the hit loop that preceded the throw are no longer emitted" to the eager-dereference bullet. |
| N3 | nit | `MIGRATION_NOTES.md` section 8 (L227-L245) | The validation plan cannot exercise the null or unavailable `Ptr` path, so `&(*p)` and `operator->()` look the same in it. That is acceptable, because the path is unreachable with the `getValidHandle`-fetched `SpModuleLabel` product. The evidence for this revision is static only. | Notes L227-L245; module L143. | None required. Optionally state in section 8 that the error-path equivalence rests on the static `Ptr.h` reading. |

## Validation plan

The regression jobs in section 8 compare products, association pairs in produced order, and the
`hitstats` tree. They confirm value equivalence on ordinary input, which is the part of this change
that matters for data products. They cannot reach the error path (N3).

## Compile-risk review

- `operator->()` is a public `const` member of `art::Ptr<T>` (Ptr.h L143-L152): callable on
  `Ptr<T> const&`. Explicit `.operator->()` call syntax is valid C++.
- Aggregate brace initialisation `SpacePointRef{std::size_t, recob::SpacePoint const*}` matches the
  member types exactly (Alg.h L47-L50), so there is no narrowing.
- No new includes needed: `Ptr.h` comes in through `FindManyP.h`, which the module already uses.
- No compile risk was found in the two changed lines.

## Verdict

**PASS WITH NOTES**: 0 blocker, 0 major, 1 minor (M1, incomplete notes), 3 nits. Revision 2
correctly brings eager `Ptr` resolution into line with the kit's accepted pattern. Value and
failure behaviour match the original's `h->` / `sp->`, apart from the documented earlier failure
point for space points.
