# Kit feedback: art-to-phlex-agents, pass-1 extractor run

Run: `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` against `origin/develop`
(`ffc89e0d9`), 2026-09-15. Ordered roughly by how much time/confidence each cost me.

## 1. `check_purity.py` (and `art_inventory.py`'s shared `INCLUDE_RE`) can attribute an
   `#include` line's findings to the wrong line — sometimes several lines away — whenever a
   blank line or a blanked-out comment immediately precedes the `#include`. This broke the
   documented transitional-marking workflow and cost real debugging time.

**Repro.** With this header (my first draft of `DisambigFromSpacePointsAlg.h`):

```cpp
#include "lardataobj/RecoBase/SpacePoint.h"

// Deep diagnostic messages inside the algorithm (see
// DisambigFromSpacePointsAlg.cxx) use mf::LogWarning; Phlex has not
// settled on a logging facility. See MIGRATION_NOTES.md section 6.
// PHLEX-TRANSITIONAL: logging
#include "messagefacility/MessageLogger/MessageLogger.h"
```

(marker on the line directly above the include, per SKILL.md step 8 and the `check_purity.py`
docstring: "on the line itself or on a comment line directly above"), running:

```
$ python3 check_purity.py DisambigFromSpacePointsAlg.h
DisambigFromSpacePointsAlg.h: 1 error(s), 0 warning(s), 0 transitional
  ERROR L29    #include messagefacility/MessageLogger/MessageLogger.h  (art MessageLogger)
FAIL: 1 error(s) across 1 file(s)
```

L29 is a **blank line**, five lines above the actual `#include` (at L34). The marker is
correctly placed by every rule the docs state, yet the check fails as if it weren't there.

**Root cause** (confirmed by instrumenting a scratch copy of the two scripts): `INCLUDE_RE =
re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)` is applied to the comment-blanked
text. `\s` matches `\n`. With `re.M`, `^` also matches at the start of every blank line
produced by blanking a comment (or a real blank line in the source). `finditer` finds the
*leftmost* match, so once several whitespace-only lines precede an `#include`, the match
starts at the *first* of those blank lines and `\s*` silently spans forward through every
following blank line to reach the actual `#`. `m.start()` — and therefore the reported line
number — lands on that first blank line, not the include's own line. I confirmed this by
tracing `INCLUDE_RE.finditer(with_strings)` directly inside `check()`: for this file it reports
`m.start()=1059` with `m.group(0)` containing five newline-joined blank lines followed by the
real `#include "messagefacility/..."` text, while a plain `with_strings.find("messagefacility")`
on the identical string correctly gives `1292` (line 34).

This is **not specific to `PHLEX-TRANSITIONAL` comments** — it fires for *any* `#include`
preceded by a blank line, which is extremely common (e.g. a blank line separating "C++
includes" from "framework includes" groups, a style the very module I extracted uses). I
verified this independently: in the *original*, unmodified `DisambigFromSpacePoints_module.cc`,
`art_inventory.py report`'s "framework includes" table already mis-locates
`larcore/Geometry/WireReadout.h` by one line for the same reason (there is a blank line above
it in the source), silently, with no error — you'd only notice by cross-checking against the
file yourself. In `check_purity.py` the effect is worse: it can silently defeat the
`PHLEX-TRANSITIONAL` marking mechanism for `#include` findings specifically.

**Workaround I used**: put the marker as a single-line comment with *zero* blank or other
comment lines between it and the `#include` (and move the explanatory prose *after* the
`#include`, not before it):

```cpp
#include "lardataobj/RecoBase/SpacePoint.h"
// PHLEX-TRANSITIONAL: logging
#include "messagefacility/MessageLogger/MessageLogger.h"
// ^ Deep diagnostic messages inside the algorithm (see ...) ...
```

This works *by accident*: the buggy match still starts one line early (at the marker
comment's own line), but `is_transitional()`'s fallback (`MARKER in here`, where `here` is
whatever line the bug reports) happens to still be true because the reported line **is** the
marker's own line. `check_purity.py`'s printed line number for this finding is still
technically wrong (it reports the marker's line, not the include's), just no longer wrong in a
way that breaks the pass/fail result. A reviewer diffing the printed line number against the
file would still be confused.

**Suggested fix**: don't reuse a `^\s*#include` regex against comment-blanked text under
`re.M` scanning; either (a) run `INCLUDE_RE` per physical line (`text.splitlines()`) so `\s*`
can't cross a newline, or (b) require `include_lines` be recorded from the position of the
literal `#` character search (`with_strings.find('#include', ...)` type scan) rather than
`m.start()` of a regex whose leading `\s*` can absorb prior lines. This affects both
`check_purity.py`'s own `INCLUDE_RE` and `art_inventory.py`'s identical pattern (used in
`analyze()`'s "framework includes" table and in `contract()`, though I didn't find a case
where `contract()`'s output was affected).

## 2. `art_inventory.py`'s "member state written inside callbacks" heuristic misses scratch
   state mutated in a helper method *called from* the callback — exactly the case this task's
   own "good test module" criteria calls out ("per-event scratch in members").

**Repro**:

```
$ python3 art_inventory.py --repo <worktree> report git:ffc89e0d9:dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc
...
member state written inside callbacks (per-event scratch or cross-event state):
  L163   fRun in produce
  L164   fEvent in produce
  L271   fTree in produce
```

This is missing `fNHits[3]`, `fNMissedBySpacePoints[2]`, and `fNMissedByNeighbors[2]` — three
arrays reset and mutated throughout `runOnSpacePoints`/`resolveUnassigned` (original lines
287-289, 299, 305, 310, 356, 374-375, 455) — arguably the single most important separation
finding in the whole file, since it's the reason the module's private helper functions
couldn't be moved verbatim without first turning this state into a return value. The tool's
`CALLBACK_RE`/`body_span` logic only extracts the *lexical* span of `produce()` (etc.) itself,
and `MEMBER_MUTATION_RES` only scans inside that span; a mutation inside a private member
function invoked *from* `produce()` is invisible. I only found this by reading the whole file
per SKILL.md step 1 ("Read the whole module... every helper it calls from the same package"),
which is the right instruction, but the tool's own output actively suggested (by omission)
that there was nothing here beyond `fRun`/`fEvent`/`fTree`. Given how common "logic lives in a
private member function called once from produce()" is, I'd treat this as a real false
negative rather than a documented limitation, and would have appreciated at least a caveat in
SKILL.md step 2 or the tool's own help text ("only scans the callback's own body; check
private methods it calls by hand").

## 3. `contract`/`contract-diff` are blind to products declared via LArSoft collection
   helpers (`recob::HitCollectionCreator::declare_products`, and presumably
   `HitAndAssociationsWriterBase::declare_products` more generally) — a very common idiom for
   any hit-producing module.

`DisambigFromSpacePoints`'s constructor declares its actual output products with:

```cpp
recob::HitCollectionCreator::declare_products(producesCollector(), "", true, false);
```

which (per `lardata/lardata/ArtDataHelper/HitCreator.h`, confirmed by reading the header
locally) declares a `recob::Hit` collection *and* a `recob::Hit`↔`recob::Wire` `art::Assns`.
Neither shows up in `art_inventory.py contract`'s output (only the one explicit
`produces<art::Assns<recob::Hit,recob::SpacePoint>>()` line does), so "contract unchanged (12
items)" is real but *incomplete*: it did not, and structurally cannot, verify that I left the
`""`/`true`/`false` arguments to `declare_products` untouched. I checked this by hand (diffing
the constructor) and recorded it in MIGRATION_NOTES.md section 5, but the skill gives no
warning that `contract`/`contract-diff` have this blind spot, and I'd expect it to bite anyone
extracting a hit-finder/hit-filter module — a large fraction of LArSoft/DUNE `*_module.cc`
files in this category use exactly this helper. Worth a line in
`references/larsoft-boundary-patterns.md`'s "Collection helpers" section or in SKILL.md step 8
telling the extractor to manually diff any `declare_products`/`HitAndAssociationsWriterBase`
call since the automated contract check won't see it.

## 4. `art_inventory.py scan` ranks packages the task (and `AGENTS.md`) explicitly says to
   skip at the very top, with no signal to distinguish them.

`scan dunereco/dunereco --top 5` put all three CVN/RegCNN modules and RegCNN's evaluator/mapper
at score 9, the highest in the whole 63-module (or 190-module across all five repos) scan —
exactly the packages `AGENTS.md`/this task's instructions say to skip ("packages that already
separate art code from framework-free code (e.g. dunereco/CVN, RegCNN, TransformerCVN have
art/ subdirectories)"). The scanner has no notion of "does this module's directory already
have a sibling non-`art/` directory of framework-free code" or "does a `*Alg.h`/`*.h` of a
similar name already exist next to this module" — both cheap, purely path-based checks that
would catch this class of false positive automatically. As it stands, a first-time user
following AGENTS.md step 1 literally would need to already know (from the same document, a
paragraph later) to discard the top ~7 rows by hand before finding a legitimate candidate.
I did this by reading the instructions carefully, but the ranking itself doesn't reflect them.

## 5. `scan` only reads the filesystem, so it cannot be pointed at `origin/develop` — every
   other subcommand (`report`, `contract`, `contract-diff`) accepts `git:REV:PATH`, but `scan`
   takes plain directories via `os.walk`.

Given this task's setup (working trees pinned to a Feb-2026 tag, extraction required against
`origin/develop` fetched same-day), AGENTS.md step 1's example command
(`art_inventory.py scan <repo>/<package>`) necessarily scans the *stale* checkout, and step 2
("Confirm candidates exist and look the same on develop") has to be done by hand, one
candidate at a time, with no tool support — which is what I did (`git show
origin/develop:<path>` plus a `diff` against the working-tree copy, for 9 candidates). In this
run the differences were small (one candidate, `SolarOpFlash_module.cc`, had a 24-line diff
between the Feb tag and develop) but a module could just as easily have been deleted, renamed,
or restructured between the tag and develop, silently invalidating a `scan` ranking based on
the old tree. A `--repo`/`--rev` option on `scan` (walking `git ls-tree -r <rev>` and reading
files via `git show <rev>:<path>` the same way `report`/`contract` already do) would remove
this manual step and this whole class of staleness risk.

## 6. Something that worked very well: `art-ptr-removal.md`'s "key equals index" rule.

Not a complaint — flagging what was load-bearing. The single sentence "If the original built
`art::Ptr`s from a `std::vector<art::Ptr<Hit>>` produced by `fill_ptr_vector`, the key equals
the index into the handle's vector" (in `art-ptr-removal.md`, under "Associations written by
the module") is exactly the fact needed to justify removing `DisambigFromSpacePoints`'s
`eventHits` (`std::vector<art::Ptr<recob::Hit>>` built by `fill_ptr_vector` from a single
handle) throughout four functions and replace every `.key()` with the loop index, with
confidence rather than guesswork. Worth keeping prominent; it was the highest-leverage single
line in any reference file for this module.

## 7. Ambiguous: how much of a module's *own* control-flow (not just FHiCL defaults) belongs
   in the extracted config struct.

`extraction.md`'s GausHitFinder example bundles a control-flow flag (`filter_hits`) into the
algorithm's config struct alongside pure data thresholds, suggesting "cfg mirrors everything
FHiCL fed the algorithm, including switches." `DisambigFromSpacePoints`, by contrast, already
had its control flow (whether to call `resolveUnassigned` at all; which of
`assignFirstAllowedWire`/`assignEveryAllowedWire`/neither to call) hoisted into `produce()`
*before* this extraction, with only `fMaxDistance`/`fExcludeTPCs` read *inside* the four
private methods. I kept `UseNeighbors`/`MoveLeftovers`/`NumNeighbors` selection at the module
boundary (matching the module's own pre-existing decomposition) and put only
`maxDistance`/`excludeTPCs` in `DisambigFromSpacePointsCfg`, documenting the reasoning in
MIGRATION_NOTES.md section 3. SKILL.md step 3 and `extraction.md` don't say which philosophy
wins when a module already separates control-flow from computation across several functions
rather than one monolithic entry point; a sentence addressing "cfg holds what the callee
reads, not everything the caller decided" (or the opposite) would remove a judgment call I had
to make and justify myself.

## Script/tooling notes (minor)

- `check_purity.py --json` and `art_inventory.py --json` weren't needed for a single-module
  run this size; the tables were fine. Not a complaint, just noting the JSON paths went
  unexercised in this run.
- Both scripts leave a `__pycache__/` next to themselves in the kit's own `scripts/`
  directory (created the first time either is imported/run, e.g. by `check_purity.py`
  importing `art_inventory`) despite `check_purity.py` setting
  `sys.dont_write_bytecode = True` at its own top — that flag only stops the *current*
  process from writing bytecode; `art_inventory.py` run directly (as I did, for `scan`/
  `report`/`contract`) has no such guard and does write one. Already covered by the kit's
  `.gitignore` (`__pycache__/`, `*.pyc`), so no action needed — noting only because it cost me
  a few minutes suspecting a *stale-bytecode* explanation for finding 1 above before the
  scratch-copy experiment ruled it out.

## Round 2 (post-verification fixes)

Confirmed fixed against the current kit (not a snapshot): the `#include` line-attribution bug
(finding 1) — `DisambigFromSpacePointsAlg.h`'s single `#include` now reports its own correct
line and the header shows 0 transitional items instead of the round-1 off-by-several; the
member-state heuristic (finding 2) — `art_inventory.py report` on the base module now lists
`fNHits`/`fNMissedBySpacePoints`/`fNMissedByNeighbors` under "member state written outside
constructors" (relabelled from round 1's "...inside callbacks", and now also tags each row
`[callback]`/etc.), where round 1 only surfaced `fRun`/`fEvent`/`fTree`; `contract`/
`contract-diff` (finding 3) — now emit a `declare_products recob::HitCollectionCreator(...)`
line and correctly reported 13 unchanged items across this round's before/after; and `scan
--rev` (finding 5) exists and takes a git revision. All four fixes worked exactly as I'd
have wanted, on the first try, no further issues found while re-running this session's
checks against them.

One thing the verifier's own report caught that my kit feedback did not (worth the kit
authors' attention even though it's a verifier note, not an extractor one): `art_inventory.py
report`'s "framework includes" line numbers can be off by one even in the *original,
unmodified* module (a blank line before an `#include` was enough), which I never checked for
since I was focused on the `check_purity.py` marker-attribution symptom. Fixing the shared
regex root cause (finding 1) evidently fixed this too — I re-ran `report` on the base file
this round and its "framework includes" table now lines up with the file. Good to confirm the
fix was to the shared root cause, not a `check_purity.py`-local patch.
