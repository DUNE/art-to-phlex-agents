# Notice

The following files condense and quote the *Migrating to Phlex* guide and the
`gauss_hit_finder` example from
[Framework-R-D/phlex-examples](https://github.com/Framework-R-D/phlex-examples)
(`migration/`, commit `5df307b`, 2026-09-14; guide version 0.1.alpha dated 2026-09-09):

- `skills/art-phlex-extract/references/separation.md`
- `skills/art-phlex-extract/references/extraction.md`
- `skills/art-phlex-extract/references/binding-crosswalk.md`
- `skills/art-phlex-extract/references/art-ptr-removal.md`

That material is Copyright (2025) Fermi Forward Discovery Group, LLC, produced under U.S.
Government contract 89243024CSC000002 for Fermi National Accelerator Laboratory, and licensed
under the Apache License, Version 2.0 (<https://www.apache.org/licenses/LICENSE-2.0.txt>).
The files above are modified (condensed, reorganised, annotated with kit notes) and are not
the version distributed by Fermilab.

`references/binding-crosswalk.md` was also checked against Phlex v0.4.1
([Framework-R-D/phlex](https://github.com/Framework-R-D/phlex), tag `v0.4.1`, 2026-09-30) and
phlex-examples branch `phlex-v0.4` (commit `c55bbfc`), both under the same copyright and
licence.

The worked examples in `examples/dunereco-DisambigFromSpacePoints-v0/` and `-v1/`, and the
reports in `examples/verifier-mutation-test/`, contain code moved from
`dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc` in
[DUNE/dunereco](https://github.com/DUNE/dunereco) (commits `ffc89e0d9` and `5d619357`; the
file is the same at both), which is licensed under the Apache License, Version 2.0. The
patches and notes are modified from that source.

Everything else in this repository (workflow, skills text outside quoted passages,
`references/larsoft-boundary-patterns.md`, scripts, templates, agent definitions) was written
for this kit and is released under the Apache License, Version 2.0. The full licence text is
in `LICENSE`.
