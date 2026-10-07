# Static verification: `DisambigFromSpacePoints` pass 1 (round 2)

| | |
|---|---|
| Verdict | PASS WITH NOTES |
| Findings | 0 blocker, 0 major, 4 minor, 1 nit |
| Working tree and base | `<worktree>` (branch `phlex-extract/DisambigFromSpacePoints`, uncommitted) against `ffc89e0d97c413cbfc3a1b17d7e278f734ba8cd9` |
| Notes reviewed | `$KIT/runs/dunereco-DisambigFromSpacePoints/MIGRATION_NOTES.md`, including "Round 2 changes" (KIT_FEEDBACK.md not read) |
| Previous report | `VERIFICATION-round1.md` (FAIL: 0 blocker, 1 major, 5 minor, 3 nit), byte-identical to the round-1 report |
| Verifier / model / date | Claude Code verifier (live kit `$KIT`, art-phlex-verify), claude-opus-5, 2026-09-15 |
| Compilation | none, by design |

## Summary

- Round 2 made five code edits: `fNMissedByNeighbors` is copied only when `UseNeighbors` ran
  (F1); `hitsFromSp` is back to `FindManyP` and resolved with `.get()` in `produce()` (F3); the
  MessageLogger include moved to the `.cxx` (F4); the duplicate `fMaxDistance`/`fExcludeTPCs`
  members were dropped (F7); comments were updated. Everything else was notes. A diff of the
  round-1 and round-2 patches confirms that the algorithm bodies did not change.
- Data products (hit collection, hit-wire and hit-spacepoint associations) are preserved
  statement for statement, including output order. The contract is unchanged (13 items, now
  including `declare_products`). The `hitstats` TTree now has the same write sites as the base.
- No blocker or major remains. The four minors are: two narrow error-path differences created
  by the new `.get()` loops, which need unusual or corrupt input and which the notes wrongly say
  are documented (N1); stale line references after the round-2 edits (N2); a validation-plan
  step that compares an indeterminate TTree branch across jobs (N3); and a wrong claim about
  out-of-bounds behaviour (N4).
- Before build and regression: run the plan in §8 but exclude `fNMissedByNeighbors` from the
  `UseNeighbors: false` comparisons (N3), use a fresh CMake configure, and compare products in
  produced order.

## Round 1 findings status

| # | Round 1 severity | Status | Evidence (current file:line) |
|---|---|---|---|
| F1 | major | resolved | `DisambigFromSpacePoints_module.cc:283-290`: `fNHits`/`fNMissedBySpacePoints` are always copied; `fNMissedByNeighbors` is copied only `if (fUseNeighbors)`. The base writes `fNMissedByNeighbors` only in `resolveUnassigned` (base L374-375, L455), reached only through base L224. The branch buffers are read only by `Fill()`, so the observable writes are identical. Header comment corrected (`DisambigFromSpacePointsAlg.h:54-62`). Pre-existing bug logged (notes §4 issue 5). |
| F2 | minor | partially resolved | §8 now requires exact-order comparison and the full `UseNeighbors` x `MoveLeftovers` matrix. It also asks the `UseNeighbors: false` job to show that `fNMissedByNeighbors` "reproduces identically", which cannot be expected (N3). |
| F3 | minor | partially resolved | `DisambigFromSpacePoints_module.cc:171` restores `FindManyP<recob::Hit>`; `:184-193` resolves with `h.get()`, which throws `ProductNotFound` for a Ptr to an unavailable product, as base L201/L210 did. Two narrow differences remain from the new `.get()` loops, and the notes claim they are documented when they are not (N1). |
| F4 | minor | resolved | Include and marker at `DisambigFromSpacePointsAlg.cxx:5-6`; the header has no framework include (`check_purity.py`: `.h` 0 transitional). The header comment still contains the marker string (N5). |
| F5 | minor | resolved | Notes §4 issues 5-7 added (indeterminate branch, unchecked `plane` index, uncounted no-wire hits). Issue 6 contains a wrong "identical effect" claim (N4). |
| F6 | minor | partially resolved | The four named corrections were made (§2 item 2, §4 issue 3 type, "Module selection" CMake wording). The round-2 edits shifted lines again, so §2 items 2, 4 and 19, §4, §7, §9 and the "Round 2 changes" table now carry stale references (N2). |
| F7 | nit | resolved | Members removed (`DisambigFromSpacePoints_module.cc:80-91`); `fCfg{config().MaxDistance(), config().ExcludeTPCs()}` at `:103`. fhiclcpp `Atom::operator()` returns `auto const&` and `Sequence::operator()` returns by value, so there is no narrowing and the initialisation order stays safe (`fCfg` is declared last, `:91`). No leftover uses of the removed members. |
| F8 | nit | resolved | Notes §7 `ResolveUnassigned` row: `det_props` is now event-layer, and the `operator[]`/non-const blocker is named (its line reference is stale, N2). |
| F9 | nit | resolved | Notes "Build note for hand-off" (MIGRATION_NOTES.md L39-45). |

## Original module in brief

Carried over unchanged from round 1 (the base did not change); written before reading any new
code or notes.

DisambigFromSpacePoints reads `recob::Hit` (HitModuleLabel) and `recob::SpacePoint`
(SpModuleLabel) and writes each hit again on a resolved wire. Collection hits go to the first
wire of their channel. For induction hits, each associated spacepoint is mapped to a TPC
through its first collection hit, and a candidate wire in that TPC scores when the spacepoint's
wire coordinate is within one wire pitch; the TPC with the strictly highest score wins, with
ties broken by `unordered_map` iteration order. Unresolved induction hits can optionally
(UseNeighbors) be resolved by a k-nearest neighbour score within MaxDistance, skipping
ExcludeTPCs. Leftovers are dropped, put on the first allowed wire, or repeated on every allowed
wire. Contract: 8 FHiCL parameters without defaults, `HitCollectionCreator::declare_products(..., "",
true, false)` plus `Assns<recob::Hit, recob::SpacePoint>`, services WireReadout,
DetectorPropertiesService (per event), and TFileService with TTree `hitstats` when
MonitoringPlots is set. `fNMissedByNeighbors` is written only when UseNeighbors is set.

## Automated checks

Live kit, `S=$KIT/skills/art-phlex-extract/scripts`, run from the worktree, `D=dunereco/HitFinderDUNE`.

| Check | Command | Result |
|---|---|---|
| Scope | `git status --short`; `git diff --stat <base>`; `git ls-files --others --exclude-standard` | Same 3 files as round 1 (`A` .cxx 289 lines, `A` .h 127, `M` module +/-393). No build-file changes, nothing outside the directory, no untracked files. `extraction.patch` equals the worktree diff. |
| Purity | `check_purity.py $D/DisambigFromSpacePointsAlg.h $D/DisambigFromSpacePointsAlg.cxx` | PASS. `.h`: 0/0/0. `.cxx`: 0 errors, 0 warnings, 6 transitional (L6 include; L59, 155, 186, 249, 262 `mf::LogWarning`). Line numbers verified against the file. |
| Contract | `art_inventory.py --repo <wt> contract-diff --before git:<base>:$D/DisambigFromSpacePoints_module.cc --after $D/DisambigFromSpacePoints_module.cc` | `contract unchanged (13 items)`, including `declare_products recob::HitCollectionCreator(producesCollector(),"",true,false)`. `contract.before.txt` and `contract.after.txt` match fresh runs. |
| Algorithm inventory | `art_inventory.py report $D/DisambigFromSpacePointsAlg.h $D/DisambigFromSpacePointsAlg.cxx` | `.h`: no framework constructs. `.cxx`: one messagefacility include (L6) and 5 `MessageLogger` uses. |
| Module inventory | `art_inventory.py report $D/DisambigFromSpacePoints_module.cc` | All services, handles, `FindManyP` x2 (L170-171), `FindOneP`, Assns, PtrMaker, `declare_products` (L113), `produces` (L116), TFileService in the module. Member state written outside constructors: `fRun`/`fEvent` (L134-135), counter copies (L283-289), `fTree` (L291, the `Fill` call). All are TTree branch buffers and match base write sites (F1). |
| Transitional markers vs notes | `grep -rn PHLEX-TRANSITIONAL $D` | 6 markers (`.cxx:5, 58, 154, 185, 248, 261`) match the 6 rows of notes §6 (`.cxx:6, 59, 155, 186, 249, 262`, the guarded lines). One extra grep hit at `.h:31` is prose, not a marker (N5). |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| N1 | minor | `DisambigFromSpacePoints_module.cc:191, 205`; `DisambigFromSpacePointsAlg.cxx:25`; notes "Round 2 changes" F3 row | Error paths still differ in two narrow cases, both created by the new `.get()` loops. (a) **Null hit Ptr in the spacepoint-to-hit association.** `Ptr::get()` returns `nullptr` for a null Ptr without throwing, and `BuildSpacePointToTPCMap` then dereferences it. The base went through `Ptr::operator->`, which throws `ProductNotFound` when no product is reachable. (b) **Eager spacepoint resolution.** `.get()` resolves every spacepoint Ptr of every hit, including those of collection hits and spacepoints absent from `spToTPC`. The base dereferenced a spacepoint only after a `spToTPC` hit and a TPC match, and otherwise only copied the Ptr into the output Assns. A spacepoint Ptr into an unavailable product now throws where the base produced output. Both need unusual or corrupt input: the Assns must point at a spacepoint product other than the default-instance vector that `getValidHandle` already required (`:138`), or contain null Ptrs. The notes say the "residual (accepted, documented) eagerness difference [is] recorded in section 2 item 10 and section 4", but neither section mentions it (`grep -i "eager\|null Ptr\|isNull"` finds only the claim itself). | canvas 3.17.0 `Ptr.h:138-141` (`get`: `isNull() ? nullptr : operator->()`), `:204-214` (`isNull` means invalid key), `:144-151` and `:238-259` (`operator->` resolves the product and throws `ProductNotFound`); `detail/IPRHelper.h:394` (`FindManyP` passes Ptrs through unchanged, null included); `Assns.h:361-365` (`addSingle` stores Ptrs without dereferencing). Base L199-201, L208-210 (every hit dereferenced through `->`), L317-328 (spacepoint dereferenced only conditionally), L247-250 and L264-267 (output copies Ptrs only). | Record both as accepted deviations in §4 and fix the F3 row. Optionally throw at the boundary when `h.isNull()` (`:191`) so case (a) stays an exception. Case (b) can stay eager if documented, since binding will need resolved pointers anyway. |
| N2 | minor | `MIGRATION_NOTES.md` §2, §4, §7, §9, "Round 2 changes" | Line references went stale after the round-2 edits: the include move added 6 lines to the `.cxx`, and F7 removed 5 lines from the module. §2 item 2 "module ctor L123" (now L118); §2 item 4 "`produce()` L283-296" (copy is L283-290, `Fill` L291); §2 item 19 "`.cxx` L53, L149, L180, L243, L256" (now L59, L155, L186, L249, L262); §4 "Code moved verbatim" L8-32 / L44-122 / L135-229 / L238-257 / L266-280 (now L14-38 / L50-128 / L141-235 / L244-263 / L272-286); §4 issue 1 "L270" (L276); §4 issue 6 "L63, L70, L116 ... L218" (L69, L76, L122, L224); §7 "L171" (L177); §9 item 2 "`.h` L81-118" (L74-123); F3 row "`:180-189`" (L184-193). | Current files as listed. | Refresh the references, ideally as a last step after all code edits. |
| N3 | minor | `MIGRATION_NOTES.md` §8, first bullet and "Products to compare" | (a) The plan asks the `MonitoringPlots: true`, `UseNeighbors: false` job to show that `fNMissedByNeighbors` "reproduces identically rather than being masked by a coincidental zero". In that configuration the branch is never written in either version, so its content depends on each job's memory and will not reliably match. A mismatch says nothing about the extraction and a match proves nothing. Only the absence of writes can be checked, and that is a static property already confirmed here. (b) The ordering argument quotes the original as `eventHits.reserve(...)`; the base call is `hitToWire.reserve(eventHits.size())`. | Base L219, L224, L374-375; module L215, L286-290. | In `UseNeighbors: false` jobs compare `fRun`, `fEvent`, `fNHits`, `fNMissedBySpacePoints` and skip `fNMissedByNeighbors`, noting why. Correct the quoted call. |
| N4 | minor | `MIGRATION_NOTES.md` §4 issue 6 | The notes claim the base and the extraction "share the exact same member/array layout ... so the effect ... is identical". During the algorithm the counters now live in a stack-local `DisambigStats` (module L217), not in module members, so an out-of-bounds write lands in different memory. With `UseNeighbors: false`, an overflow of `nMissedBySpacePoints[2]` into `nMissedByNeighbors[0]` is no longer copied to the branch (L286-290). In the base the same overflow landed in `fNMissedByNeighbors[0]` directly. The issue also says "plane 2 or higher" for `fNHits`, which is sized 3. Only reachable with a non-collection hit on plane 2 or higher, which DUNE geometries do not produce (plane 2 is collection), so no practical output change. | Base L107-110 (member arrays followed by `fTree`), L305, L310, L356, L455. `.cxx:69, 76, 122, 224`. | Reword issue 6: undefined behaviour in both versions, and the concrete effect can differ. |
| N5 | nit | `DisambigFromSpacePointsAlg.h:30-34, 54-56` | The comment contains the literal string `PHLEX-TRANSITIONAL`, so the kit's marker grep reports 7 hits against 6 notes rows. The `DisambigStats` comment also says it "Replaces the module's fNHits and fNMissedBySpacePoints data members", which still exist as branch buffers. | `grep -rn PHLEX-TRANSITIONAL` output above. | Say "its transitional marker"; say "Holds the values the module copies into its ... branch buffers". |

## Behaviour-preservation walk-through

Base `DisambigFromSpacePoints_module.cc@ffc89e0d` (B), current module (M), `DisambigFromSpacePointsAlg.cxx` (A), `DisambigFromSpacePointsAlg.h` (H). The diff of the round-1 and round-2 patches shows the A function bodies byte-identical to round 1 apart from the include block, so the statement-level verdicts for A carry over at shifted line numbers. They were rechecked against the current text.

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|
| B:47-49 keymap typedefs | H:40-42 | identical | |
| B:122-133 member init | M:94-103 | mechanical edit OK | `fMaxDistance`/`fExcludeTPCs` fold into `fCfg{config().MaxDistance(), config().ExcludeTPCs()}`, same values. |
| B:134-137 NumNeighbors throw | M:105-108 | identical | |
| B:142 `declare_products` | M:113 | identical | Seen by the contract tool. |
| B:145 `produces<Assns>` | M:116 | identical | |
| B:147 WireReadout | M:118 | identical | |
| B:149-158 TTree booking | M:120-129 | identical | |
| B:163-164 fRun/fEvent | M:134-135 | identical | |
| B:166-167 handles | M:137-138 | identical | |
| B:172 FindOneP<Wire> | M:143 | identical | |
| B:176-180 hcol | M:147-151 | identical | |
| B:183 assns | M:154 | identical | |
| B:186-187 `fill_ptr_vector` | removed | mechanical edit OK | `key() == index`. |
| B:189-190 FindManyP x2 | M:170-171 | identical | Same types and construction order as base. |
| B:192 detProp | M:173 | identical | Once per event. |
| B:194-212 spToTPC loop | M:184-194 + A:14-38 | mechanical edit OK | Pointers resolved in `produce()`; same logic. Null-Ptr error path differs (N1a). |
| B:214-217 locals | M:210-213 | identical | |
| B:219 `hitToWire.reserve(eventHits.size())` | M:215 | identical | Same value, same bucket count. |
| B:221-222 | M:217-220 | mechanical edit OK | |
| B:224-228 | M:222-227 | mechanical edit OK | |
| B:230-232 | M:229-231 | mechanical edit OK | |
| B:234 PtrMaker | M:233 | identical | |
| B:236-251 hitToWire output | M:235-250 | mechanical edit OK | `hitsHandle->at(key)`, `spFromHit.at(key)`; same emplace and pair order. |
| B:253-269 hitToNWires output | M:252-268 | mechanical edit OK | |
| B:271 Fill | M:270-292 | mechanical edit OK | Same condition and position. Counter values equal the base members at `Fill` time; `fNMissedByNeighbors` written only when the base wrote it (F1 resolved). |
| B:274-275 put | M:295-296 | identical | |
| B:287-289 resets | A:50-52 | identical | |
| B:291-295 loop, cwids, warn | A:54-59 | identical | |
| B:296-300 collection | A:60-64 | mechanical edit OK | |
| B:303-311 induction, no SP | A:67-77 | mechanical edit OK | |
| B:314-336 SP scoring | A:80-102 | mechanical edit OK | Same iteration order and types. |
| B:337-357 best TPC / else | A:103-123 | identical | Same `unordered_map` and insertion sequence. |
| B:362 return | A:128 | identical | |
| B:374-387 | A:141-155 | identical | |
| B:389-390 dwMax/ddMax | A:157-158 | mechanical edit OK | `cfg.maxDistance`. |
| B:392-409 | A:160-177 | mechanical edit OK | `cfg.excludeTPCs`; `operator[]` kept. |
| B:410-452 | A:178-221 | mechanical edit OK | float arithmetic unchanged. |
| B:454-466 | A:223-235 | identical | |
| B:469-493 assignFirstAllowedWire | A:238-264 | mechanical edit OK | Warnings verbatim. |
| B:495-516 assignEveryAllowedWire | A:266-287 | mechanical edit OK | |

New code with no original counterpart:

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|
| M:103 | Builds `fCfg` straight from `config()` | None: same float and `std::vector<size_t>` values the base members held. |
| M:184-193 | Builds `hitsPerSpacePoint` with `h.get()` for every hit of every spacepoint | Outputs unchanged: the base dereferenced every one of these hits (B:199-201, B:208-210). Unavailable product: throws `ProductNotFound` here instead of at B:201, same type, no side effect between the two points (no logs, no puts). Null Ptr: `nullptr` then a crash at A:25 instead of a throw (N1a). |
| M:194 | Calls `BuildSpacePointToTPCMap` | Returns the map by value; used only through `find`. |
| M:196-208 | Builds `spacePointsPerHit`/`spKeysPerHit` with `sp.get()`/`sp.key()` for every hit | Outputs unchanged when products are available. Resolves spacepoints the base never dereferenced (collection hits' spacepoints, spacepoints not in `spToTPC`, TPC mismatches), so an unavailable spacepoint product now throws (N1b). A null spacepoint Ptr gives `nullptr`, but its invalid key fails `spToTPC.find` at A:85-86 before any dereference, as in the base. |
| M:217 | `DisambigStats stats` with zero defaults | Only `nHits`/`nMissedBySpacePoints` are copied unconditionally, and those are reset by `RunOnSpacePoints` anyway. |
| M:283-285 | Copies `nHits`, `nMissedBySpacePoints` into branch buffers | Same values the base wrote at B:287-310 and B:356; nothing changes them before `Fill`. |
| M:286-290 | Copies `nMissedByNeighbors` only `if (fUseNeighbors)` | Matches the base write sites. The base also wrote them with MonitoringPlots off, but nothing reads the buffers then. |
| A:5-10 | Transitional include and comment | None. |

Also checked with no change: random draws (none), service data (per event), references into event data kept past `produce()` (none; the pointer vectors are locals), cross-event state (branch buffers only).

## Validation plan

The plan in §8 would catch the changes looked for above, with one correction. It runs every
`UseNeighbors` x `MoveLeftovers` combination (6 jobs), so every branch the extraction touched is
exercised. It compares the hit collection and the `Assns<Hit,SpacePoint>` pairs in produced
order, with sorting only as a fallback, which matches the preserved container types, `reserve`
and insertion sequence. It dumps `hitstats` when monitoring is on, which covers the counter
move even though monitoring is off in the shipped configurations. The correction (N3): in
`UseNeighbors: false` jobs, `fNMissedByNeighbors` holds indeterminate content in both versions
and must be excluded from the base-versus-new comparison. The error-path differences (N1) are
not something a regression job should try to reproduce; documenting them is enough.

## Compile-risk review

Checked by reading (round-1 checks still hold for unchanged code):

- `fCfg{config().MaxDistance(), config().ExcludeTPCs()}`: fhiclcpp 4.19.0 (`~/.cache/rattler`) `Atom<T>::operator()` returns `auto const&` (`types/Atom.h:42-46`); `Sequence<T>::operator()` returns `auto` by value (`types/Sequence.h:200-205`). Aggregate init of `float` from `float const&` is not narrowing; the vector is copied or moved. `fCfg` is declared last (M:91), after every member it could depend on. No remaining uses of the removed members.
- `hitsFromSp.at(i)` on `FindManyP<recob::Hit>` returns `std::vector<art::Ptr<recob::Hit>> const&` (canvas `FindMany.h:60, 197`); `Ptr::get()` returns `T const*` (`Ptr.h:138`). `FindManyP` is visible through `AssociationUtil.h:88`.
- Include move: `mf::LogWarning` in A is covered by A:6. The module has its own MessageLogger include (M:31) for `mf::LogInfo`. The header now includes only framework-free headers, and no other file includes it.
- Declarations (H:74-123) still match definitions (A:14, 40, 131, 238, 266) and call sites (M:194, 218-219, 224-225, 229, 230).
- Build files unchanged; `art_make` globs the `.cxx` at configure time (fresh configure needed, noted in the notes).

Needs build to confirm: nothing specific; compile-error likelihood judged low.

Unverified assumptions: header versions. LArSoft from the local v10_16_00 checkout, canvas 3.17.0 and fhiclcpp 4.19.0 from the rattler package cache, while dunereco v10_24_00d00 builds against newer releases. The APIs relied on (`Ptr::get`, `FindManyP::at`, fhiclcpp accessors, `HitCreator(Hit const&, WireID const&)`) are long-standing, but their exact match with the build release was not verified.

## Guide conformance

- Separation checks: `ServiceHandle` only in the module (M:118, M:122, M:173); service values passed explicitly; no helper receives the event, a handle, `FindManyP` or `art::Ptr`; nothing event-scoped cached. Branch buffers are written before each `Fill`, where the base wrote them.
- Extraction checklist 1 to 5: (1) yes; (2) yes, all inputs are parameters; (3) out-parameters plus returned counts, acceptable for pass 1 and flagged for binding; (4) yes, `fCfg` built once from `config()`; (5) yes, 6 transitional items all in the `.cxx` and listed. The accepted error-path deviations in N1 still need writing down.
- Binding plan: plausible. `det_props` is event-layer, and the non-const `operator[]` blocker is named. `unlimited` concurrency stays consistent with `check_purity.py` (no statics or mutable state).

## Notes accuracy

- "Round 2 changes" F3 row: claims the residual eagerness difference is documented in §2 item 10 and §4; it is not (N1). §4 "Intentional deviations: none" therefore omits N1a and N1b.
- §4 issue 6: "exact same member/array layout ... identical" is wrong, and the `fNHits` bound is misstated (N4).
- §8: the indeterminate-branch comparison, and the misquoted `eventHits.reserve(...)` (N3).
- Stale line references listed in N2.
- Confirmed accurate: F1 description and §4 issue 5; F3's description of `FindMany` null filling and `Ptr::operator->` throwing; F4, F7, F8, F9 descriptions; §5 contract (13 items); §6 transitional table; §9 separation text about branch buffers.

## Notes on the verification procedure

Feedback on the updated `art-phlex-verify` (not about the code):

1. The new-to-original walk earned its place: N1 came straight from it. The `FindMany`/`FindManyP`
   bullet in step 4 is still incomplete, though. `Ptr::get()` returns `nullptr` for a null Ptr
   without throwing, and resolving pointers eagerly in `produce()` can throw where the original
   dereferenced lazily or never. Suggest: "compare when each Ptr is dereferenced in the original
   and in the new loops, and what `get()` does on a null Ptr".
2. The indeterminate-values bullet tells the extractor to preserve write sites, but step 7 does
   not warn that such branches cannot be compared across jobs. Add that. On re-verification
   rounds, a step to re-check the notes' line references would also help, because fixes shift
   lines. Tool papercut: `art_inventory.py --repo <wt> contract <relative path>` resolves plain
   paths against the working directory, not `--repo` (FileNotFoundError when run from elsewhere).
