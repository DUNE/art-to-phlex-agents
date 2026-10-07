# art-to-phlex-agents

Instructions, skills and subagents that let an AI coding agent move one *art* module at a time
toward [Phlex](https://github.com/Framework-R-D/phlex). The method follows the Phlex team's
[Migrating to Phlex](https://framework-r-d.github.io/phlex-examples/) guide. The kit works
with Claude Code, Codex, Antigravity (agy) and any other tool that reads `AGENTS.md` and agent
skills.

## Where this fits

The guide describes three stages: **separation** (confine art code to the module boundary),
**extraction** (move the algorithm into plain C++ with explicit inputs and outputs) and
**binding** (register that algorithm as Phlex nodes). DUNE plans to migrate in phases, and
this kit covers the first one.

| Phase | What happens | Status |
|---|---|---|
| 1. Prepare | Separation and extraction. The module stays an art module and must give identical art output before and after. The agent also writes a binding plan. | **This kit** |
| 2. Bind | Write Phlex plugins from the binding plans and compare Phlex output with art output. | Later, once Phlex can run DUNE workflows |
| 3. Retire | Remove the art module. | Later |

DUNE's Phlex-era code goes into new repositories under `DUNE/`, split by subsystem:
`dunecore` becomes `dune-core` (with `dune-geo-utils` and `dune-utils`), `dunereco` becomes
`dune-fd-reco` and the protoDUNE repositories, and so on. Phase 1 still changes the current
repositories, because the module must keep running in art. The binding plan records where
each extracted piece will live and which `dunecore` dependencies must move first.
`skills/art-phlex-extract/references/dune-repo-map.md` has the mapping guide.

Phase 1 is worth doing now because it can be checked today. Each module still runs in art, so
the before-and-after art comparison is the test. The binding plan is written against
**Phlex v0.4.1** (2026-09-30). The guide itself is still v0.1.alpha, so where the guide and
v0.4.1 disagree, `binding-crosswalk.md` follows the v0.4.1 code and says so.

## What's inside

| Path | Contents | Linked into your repository by `install.sh` |
|---|---|---|
| `AGENTS.md` (`CLAUDE.md` links to it) | the workflow, roles and rules | no |
| `skills/art-phlex-orchestrate/` | the manager's workflow, so it also works outside the kit | yes |
| `skills/art-phlex-extract/` | phase-1 skill: references condensed from the guide, LArSoft and DUNE patterns, templates, scripts | yes |
| `skills/art-phlex-verify/` | static review of an extraction, without compiling | yes |
| `skills/art-phlex-test/` | characterization unit tests for the extracted algorithm | yes |
| `skills/explain-ste/` | writes hand-off notes in ASD-STE100 style for readers whose first language is not English | yes |
| `skills/dune-pr-disclosure/` | adds the AI disclosure: a `Generated-by` or `Assisted-by` trailer on each commit and one footer line in the pull request | yes |
| `agents/` | Claude Code subagents: `phlex-extractor`, `phlex-verifier`, `phlex-reviewer`, `phlex-tester` | yes |
| `maintainers/agents/` | subagents for looking after the kit itself: `docs-writer`, `release-notes`, `security-auditor` | no |
| `.claude/settings.json` | denies commits, pushes, `gh`, network tools and reads of credential files; asks before fetches, builds and inline scripts | as `.claude/settings.local.json`, if you have none |
| `install.sh` | links the skills and agents into another repository | |
| `examples/` | finished, verified passes on real modules | |

The scripts need Python 3.8 or newer and nothing outside the standard library:

- `art_inventory.py scan --rev REV DIR` ranks `*_module.cc` files as first candidates.
- `art_inventory.py report FILE` lists art constructs with line numbers: product retrieval,
  `art::Ptr` and `Assns`, services, tools, FHiCL, logging, and member state written outside
  constructors.
- `art_inventory.py contract-diff --before git:REV:FILE --after FILE` compares what the
  framework sees: products, consumes, FHiCL names and defaults, callbacks.
- `check_purity.py FILES` fails when extracted algorithm files include art, FHiCL,
  MessageLogger, service or Phlex code.
- `art_compare.py wrap JOB.fcl --prefix before|after` writes a FHiCL wrapper with fixed output
  file names, and `art_compare.py diff BEFORE AFTER` compares the persisted products (or a
  TFileService tree) entry by entry, in stored order. `diff` needs `uproot`, `awkward` and
  `numpy`; install them in a virtual environment outside the experiment repository.

## Where to run it

Until there is a container set-up for shared machines, run the agents **only on your own
computer**, against a local clone of the experiment repository. That is how both examples
were made.

- Do not run the agents on shared interactive machines (the DUNE GPVMs and similar). DUNE
  has asked people not to run Claude Code there, and those machines hold grid credentials
  and other users' files.
- The agents never build. Copy the patch to a machine that can build the code (for DUNE, an
  AL9 GPVM or a container with the release) and build, test and run the comparison there
  yourself.
- A container without network access, usable on shared machines, is planned. This section
  will change when it exists.

## Quick start

Clone the kit and set `KIT`. The agents stop if `KIT` is not set.

```bash
git clone git@github.com:DUNE/art-to-phlex-agents.git ~/github/art-to-phlex-agents
export KIT=~/github/art-to-phlex-agents
```

Then use one of the two methods below.

**Method A: start the agent in the kit.** Use this method for a first try.

1. Go to the kit directory.
2. Start Claude Code and give it access to the experiment repository:
   `claude --add-dir ~/github/dune/dunereco`
3. Tell the agent which package to look at, for example: "Run phase 1 on one module from
   `dunereco/HitFinderDUNE`."

**Method B: link the kit into the experiment repository.**

1. Run `$KIT/install.sh ~/github/dune/dunereco`.
2. Start your agent in the experiment repository.
3. Tell the agent to use the `art-phlex-orchestrate` skill.

`install.sh` makes symbolic links and adds them to `.git/info/exclude`, so `git status` in the
experiment repository stays clean. If a file already exists at a link path, the script stops.
Use `--force` to replace it. The script never replaces an existing `.claude/settings.local.json`,
even with `--force`, and refuses to follow a symbolic link that leads out of the project.

## How a run works

Your main session is the **manager**. It picks the module, makes a git worktree, and gives
work to four subagents:

1. **Extractor** (`phlex-extractor`). Applies `art-phlex-extract` in the worktree and writes
   `runs/<repo>-<Module>/MIGRATION_NOTES.md`.
2. **Verifier** (`phlex-verifier`). Applies `art-phlex-verify`, reads the change without
   compiling, and writes `VERIFICATION.md` with PASS, PASS WITH NOTES or FAIL.
3. **Reviewer** (`phlex-reviewer`). Reads the same diff as ordinary C++ (lifetimes, moved-from
   values, iterator invalidation, build files) and writes `REVIEW.md`.
4. **Tester** (`phlex-tester`). Applies `art-phlex-test` and writes Boost.Test unit tests for
   the extracted algorithm. Each expected value is traced from the original module, not taken
   from the new code. The reviewer then reviews the tests.

Blocker and major findings go back to the extractor. After two failed rounds the manager
stops and asks you. The verifier and reviewer should run on a different model from the
extractor if you can arrange it.

The manager also writes the `art_compare.py` commands for the before-and-after comparison.

The agents never commit, push or build. You build both versions, run the unit tests and the
comparison, and open the pull request. Only the comparison and the tests you ran count as
validation; the agents' reviews are reviews. The manager suggests a commit message and the AI
disclosure: a trailer on every AI-assisted commit and one matching footer in the pull request.

```text
Generated-by: Claude Code (Opus 5.5)          last line of each commit message
🤖 Generated By: Claude Code (Opus 5.5)       last line of the pull request
```

Use `Assisted-by` / `🤖 Assisted By` instead when you wrote or substantially reworked the
change. Do not use `Co-Authored-By` for an AI tool.

## Safety

The agents read source code you did not write. A comment in that code can contain text aimed
at an agent. The kit tells every agent to treat source, comments, FHiCL and notes as data and
to report instructions it finds there.

`.claude/settings.json` reduces what a Claude Code session can do. It denies commits, pushes,
`gh`, Claude's web tools, common network and grid-copy commands, and reads of SSH keys, grid
proxies and Kerberos tickets. It asks before fetches, builds, compilers and inline
`python -c` or `bash -c` scripts. With Method B, `install.sh` links the same file in as
`.claude/settings.local.json` if the project has none. If it has one, the script tells you,
and you should merge the `permissions` block by hand.

These rules are a safety net, not a sandbox. A determined command can get round
pattern-matched rules, and Codex, Antigravity and other tools ignore this file. On shared
machines, see [Where to run it](#where-to-run-it).

## Limits

- The scripts use regular expressions. They point at lines worth reading and can miss
  unusual code. A clean result means nothing obvious was found.
- A review without a compiler can miss errors that a compiler would catch. Build before you
  merge.
- The guide is v0.1.alpha and parts of the Phlex API are still marked experimental. `NOTICE.md`
  records the guide commit the references come from.

## Examples

Both examples extract the same module, `dunereco/HitFinderDUNE/DisambigFromSpacePoints_module.cc`,
which did not change between the two runs. Comparing them shows what the kit changes did.

| | `examples/dunereco-DisambigFromSpacePoints-v0/` | `examples/dunereco-DisambigFromSpacePoints-v1/` |
|---|---|---|
| Date and kit | 2026-09-15, first version of the kit | 2026-10-04, current kit |
| Extractor model | Sonnet | Opus |
| First verifier round | FAIL: 1 major, 5 minor, 3 nit | PASS WITH NOTES: 0 major, 2 minor, 4 nit |
| Rounds to pass | 2 | 1 |
| Reviewer and tests | none | reviewer says ship; 10 characterization tests |
| Contract (13 items) | unchanged | unchanged |

Each folder holds the patch, the migration notes, the verifier reports, the framework contract
before and after, and the extractor's feedback on the kit. v1 also has the code review, the
tests and `VERIFICATION-rev2.md`, a delta review of one later change: `art::Ptr`s are now
resolved with `ptr.operator->()` instead of `&*ptr`. The model changed between the runs as well
as the kit, so not all of the improvement belongs to the kit.

Neither example has been built or run yet. `extraction-with-tests.patch` in v1 applies cleanly
to dunereco `v10_22_00d01`. `art_compare.py` has only been tested on synthetic TTrees, not real
art files.

`examples/verifier-mutation-test/` tests the verifier itself. Eight copies of the v1 extraction
each had one planted slip, and blind verifiers caught all eight at the exact line, with no false
alarm on an untouched control. The test also found a mistake the kit had accepted (the `&*ptr`
pattern above).

## Contributing

Open an issue or a pull request. If AI helped, add the trailer to each commit and the footer to
the pull request, as above. When the guide or Phlex changes, update
`skills/*/references/` and the commit recorded in `NOTICE.md`. The agents in
`maintainers/agents/` help with that: `docs-writer` keeps this README in step with the
skills, and `security-auditor` reviews the scripts and `install.sh` before a release.

## Licence and credits

Apache License 2.0, see `LICENSE`. The references quote and condense *Migrating to Phlex* and
its GausHitFinder example, written by the Phlex team at Fermilab under the same licence. See
`NOTICE.md`. The approach builds on work by Eric Church, Chris Jackson and colleagues at PNNL,
who used AI agents to refactor LArSoft's hit finder.
