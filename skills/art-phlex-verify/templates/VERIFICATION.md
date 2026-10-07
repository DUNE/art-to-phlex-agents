# Static verification: `<Module>` pass 1

| | |
|---|---|
| Verdict | PASS / PASS WITH NOTES / FAIL |
| Findings | `<n>` blocker, `<n>` major, `<n>` minor, `<n>` nit |
| Working tree and base | `<path>` against `<base sha>` |
| Notes reviewed | `<path to MIGRATION_NOTES.md>` |
| Verifier / model / date | `<agent>`, `<model>`, `<YYYY-MM-DD>` |
| Compilation | none, by design |

## Summary

Three to six bullets: what changed, whether it preserves behaviour, what must happen before a
build and regression test.

## Original module in brief

Written before reading the new code or the notes.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Purity | `check_purity.py ...` | |
| Contract | `art_inventory.py contract-diff ...` | |
| Algorithm inventory | `art_inventory.py report <algorithm files>` | |
| Module inventory | `art_inventory.py report <module>` | |
| Transitional markers vs notes | `grep -rn PHLEX-TRANSITIONAL` | |

## Findings

| # | Severity | file:line | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|

## Behaviour-preservation walk-through

Original to new:

| Original (base file:lines) | New location | Verdict | Note |
|---|---|---|---|

New code with no original counterpart (boundary glue, null checks, copies into members):

| New (file:lines) | What it does | Effect on outputs or error paths |
|---|---|---|

## Validation plan

Would the plan in `MIGRATION_NOTES.md` catch the changes looked for above (configurations
covered, exact ordering, monitoring outputs)?

## Compile-risk review

What was checked, what could only be settled by a build ("needs build to confirm"), and
unverified API assumptions.

## Guide conformance

- Separation checks:
- Extraction checklist 1 to 5:
- Binding plan:

## Notes accuracy

Claims in `MIGRATION_NOTES.md` that do not match the code.
