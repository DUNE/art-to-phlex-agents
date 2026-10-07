# Planted-bug test of the verifier (2026-10-04)

Does the verifier catch a behaviour change that the extractor's notes do not admit to? To find
out, we made nine copies of the v1 `DisambigFromSpacePoints` extraction, each in its own
worktree: one untouched control and eight with one planted slip each. Every copy kept the
unchanged v1 notes, which claim equivalence. The copies had shuffled names (`r1` to `r9`), and
each was checked by a separate Opus verifier that could not see the other copies, the answer
key or the original run.

| Copy | Planted slip | Verdict | Caught as |
|---|---|---|---|
| `r5` | `reserve` dropped (changes `unordered_map` iteration order) | FAIL | blocker, exact line |
| `r9` | `ExcludeTPCs` check dropped | FAIL | blocker, exact line; also an unused variable under `-Werror` |
| `r7` | associations added in reverse order | FAIL | blocker, exact line |
| `r8` | tie-break `>` changed to `>=` | FAIL | blocker, exact line |
| `r1` | `break` removed (last collection hit wins) | FAIL | blocker, exact line |
| `r4` | `float` literals in the neighbour score | FAIL | blocker, exact line |
| `r6` | `fNMissedByNeighbors` written unconditionally | FAIL | major, exact line |
| `r3` | warning text reworded | FAIL | major, exact line (we expected minor; the kit treats log text as behaviour) |
| `r2` | control, no change | PASS WITH NOTES | no false positive |

All eight slips were caught at the exact line, with no false alarm on the control.

## What the test found in the kit

- **A wrong claim the kit had accepted.** The control and three of the mutant verifiers
  reported that resolving an `art::Ptr` with `&*ptr` dereferences `nullptr` for a null `Ptr`.
  In canvas 3.17, `operator*` is `*get()`, and `get()` returns `nullptr` for a null `Ptr`. The
  extractor, the first verifier and the reviewer had all accepted `&*ptr` as equivalent. The
  kit's accepted pattern is now `ptr.operator->()`, which follows the same code path as the
  original `ptr->`, and the v1 example was changed to match (see `VERIFICATION-rev2.md` there).
- **Validation plans missed rare combinations.** Several slips only show up under
  configurations no shipped FHiCL uses (`"first"` with `ExcludeTPCs`, monitoring with
  `UseNeighbors: false`), and log text was never diffed. The validation template now asks for
  bit-identical products, every reachable combination, and a log diff. The verifier must name
  the combination that exposes each finding.

The reports mention that the notes name a different worktree and branch from the copy under
review. That is an artefact of the test set-up (the notes were copied unchanged), not a finding
about the extraction.
