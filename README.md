# art-to-phlex-agents

Instructions, skills and subagents that let an AI coding agent move one *art* module at a time
toward [Phlex](https://github.com/Framework-R-D/phlex). The method follows the Phlex team's
[Migrating to Phlex](https://framework-r-d.github.io/phlex-examples/) guide. The kit works
with Claude Code, Codex, Antigravity (agy) and any other tool that reads `AGENTS.md` and agent
skills.

> [!WARNING]
> **Experimental.** This kit is a tool of the DUNE Phlex Adoption Working Group. It is not a
> product of the Phlex team and not yet an agreed DUNE workflow. Two extractions made with it
> have been built and compared with art output, outside any release: dunereco
> `DisambigFromSpacePoints` and larreco `SpacePointSolver`, both identical in every tested
> configuration. The agents' reviews are reviews, not validation:
> you are responsible for any change you take from a run, and only your own build, unit
> tests and before-and-after comparison count as evidence that it is right.

## Before you start

- **Your code goes to an AI provider.** The agents send the source they read to the model
  provider (Anthropic for Claude Code, OpenAI for Codex, Google for Antigravity). Use the kit
  only on code you may share that way. DUNE's public repositories are fine. Do not point it at
  unreleased or private code, or at directories that hold credentials, without checking first.
- **Follow the collaboration's AI guidance** and disclose AI help on every commit and pull
  request, as described under [How a run works](#how-a-run-works).
- **You need your own access** to one of the supported tools (a subscription or an API key).
  A run on a small module costs a few dollars; see [Models and cost](#models-and-cost).
- **Questions and problems:** open an issue in this repository, or raise it with the Phlex
  Adoption Working Group.

## Where this fits

The guide describes three stages: **separation** (confine art code to the module boundary),
**extraction** (move the algorithm into plain C++ with explicit inputs and outputs) and
**binding** (register that algorithm as Phlex nodes). DUNE plans to migrate in phases, and
this kit covers the first one.

| Phase | What happens | Status |
|---|---|---|
| 1. Prepare | Separation and extraction, made in a local worktree. The module stays an art module and must give identical art output before and after. The agent also writes a binding plan. | **This kit** |
| 2. Bind | Write Phlex plugins from the binding plans and compare Phlex output with art output. | Later, once Phlex can run DUNE workflows |
| 3. Retire | Remove the art module. | Later |

DUNE's Phlex-era code goes into new repositories under `DUNE/`, split by subsystem:
`dunecore` becomes `dune-core` (with `dune-geo-utils` and `dune-utils`), `dunereco` becomes
`dune-fd-reco` and the protoDUNE repositories, and so on. The kit makes and checks each
extraction in a local worktree of the current repository, because only art can run the
before-and-after comparison today. Where the result then lands is **to be decided** by the DUNE
Software Lead and Code Management; see [Where the change goes](#where-the-change-goes). The binding plan
records where each extracted piece would live and which `dunecore` dependencies must move
first.
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
| `agents/` | Claude Code subagents: `phlex-extractor`, `phlex-verifier`, `phlex-reviewer`, `phlex-tester`, `phlex-validator` | yes |
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
  file names. `art_compare.py diff BEFORE AFTER` compares flat trees entry by entry; it needs
  `uproot`, `awkward` and `numpy` in a virtual environment outside the experiment repository,
  and it cannot read real art event files.
- `art_physics.py flatten` writes art products and associations to flat TTrees (one row per
  object or pair, in stored order), and `art_physics.py compare` checks two such files row
  by row and draws before-and-after histograms with ratio panels, KS and chi2 tests. Run it
  with PyROOT from the experiment environment, where `lar` runs.

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
work to four subagents, and to a fifth if you allow building:

1. **Extractor** (`phlex-extractor`). Applies `art-phlex-extract` in the worktree and writes
   `runs/<repo>-<Module>/MIGRATION_NOTES.md`.
2. **Verifier** (`phlex-verifier`). Applies `art-phlex-verify`, reads the change without
   compiling, and writes `VERIFICATION.md` with PASS, PASS WITH NOTES or FAIL.
3. **Reviewer** (`phlex-reviewer`). Reads the same diff as ordinary C++ (lifetimes, moved-from
   values, iterator invalidation, build files) and writes `REVIEW.md`.
4. **Tester** (`phlex-tester`). Applies `art-phlex-test` and writes Boost.Test unit tests for
   the extracted algorithm. Each expected value is traced from the original module, not taken
   from the new code. The reviewer then reviews the tests.
5. **Validator** (`phlex-validator`, optional). Only when you allow building: builds the base
   and the extracted version in a container, runs the unit tests and the comparison matrix,
   and writes `VALIDATION.md`. It never edits source.

The verifier and the reviewer only read the change, so the manager runs them in parallel.
Blocker and major findings go back to the extractor. After two failed rounds the manager
stops and asks you. See [Models and cost](#models-and-cost) for which model each role uses.

The manager also writes the `art_compare.py` and `art_physics.py` commands for the
before-and-after comparison.

The agents never commit or push, and only the validator builds, and only when you allow it.
Without it you build both versions, run the unit tests and the comparison, and open the pull
request. Only the comparison and the tests you ran count as
validation; the agents' reviews are reviews. The manager suggests a commit message and the AI
disclosure: a trailer on every AI-assisted commit and one matching footer in the pull request.

```text
Generated-by: Claude Code (Opus 5.5)          last line of each commit message
🤖 Generated By: Claude Code (Opus 5.5)       last line of the pull request
```

Use `Assisted-by` / `🤖 Assisted By` instead when you wrote or substantially reworked the
change. Do not use `Co-Authored-By` for an AI tool.

## Where the change goes

**To be decided.** A run ends with uncommitted changes in a local worktree of the art-era
repository and the reports in `runs/<repo>-<Module>/`. Whether those changes go anywhere,
and where, is a decision for the DUNE Software Lead and Code Management, not for the person running the kit.
The options are:

- **the Phlex-era repository only** (for example `DUNE/dune-pd-hd`): copy the
  framework-free algorithm and its tests there, and leave the art-era repository unchanged.
  This is the current leaning.
- **the art-era repository** (for example `dunereco`): a pull request with the thinner module
  and the algorithm, so the art module itself uses the extracted code.
- **neither yet**: keep the patch and the notes until phase 2.

Until they decide, do not open pull requests from a run. The manager's
hand-off ends with a **Where the change goes** section: the Phlex-era home from the binding
plan, the commands for each option, and the dependencies that must move first, all marked as
waiting for that decision. The agents never run those commands. Building, the unit tests and
the art comparison are still worth doing in the worktree, because they are how you know the
extraction is right wherever it ends up.

This stays manual until they are happy to automate it. When that changes, this
section and the manager skill will say so.

## Models and cost

Each subagent's model is the `model:` line in its file in `agents/`. The manager is your own
session, so it uses whatever model you started with.

| Role | Default | What we have seen |
|---|---|---|
| Manager | your session | Opus in every run so far |
| Extractor | `opus` | Sonnet needed two verifier rounds on the v0 example; Opus passed in one on v1 and on `NumberOfHitsFilter` |
| Verifier | `opus` | caught 8 of 8 planted bugs; made one arithmetic slip, which the tester caught |
| Reviewer, extraction | `opus` | no defects in either extraction; Sonnet not tried yet |
| Reviewer, tests | `sonnet` (the manager starts it on Sonnet) | Opus found a real bug in the tests on the dry run; Sonnet not tried yet |
| Tester | `sonnet` | 25 traced test values, and caught the verifier's slip |

Only Opus has been tried for the extractor and the verifier. The verifier is meant to be
independent of the extractor, and two copies of the same model can share blind spots. For a
stronger check, run the verifier step in a different tool (the skill works in Codex and
Antigravity as well).

To change models:

- for one run, tell the manager, for example "run the reviewer on Sonnet";
- for every run, edit the `model:` line in `agents/<role>.md`;
- for all subagents at once, set `CLAUDE_CODE_SUBAGENT_MODEL`.

The commit trailer names the model that wrote that commit. With the defaults, the extraction
commit is Opus and the tests commit is Sonnet.

**Cost of one run.** The fresh-clone run on `dunereco/HitFinderDUNE/NumberOfHitsFilter_module.cc`
(2026-10-06; extractor, verifier, two reviews, tester with one fix, Opus manager) took
17 minutes of model time and 27 minutes in total, and used about 5 USD at API prices: 4.46 USD
of Opus and 0.54 USD of Sonnet. On a subscription it used about a third of one five-hour
usage window. A larger module, or one that needs a second round, costs more. Opus did most
of the spending. The test review now runs on Sonnet; that run used Opus for it, so expect a
little less. A Sonnet reviewer for the extraction is the next saving to test.

A larger module costs more. The headless run on `larreco/SpacePointSolver` (2026-11-01; 540
lines plus helpers; extractor, verifier, review, tester, two test reviews, Opus manager) took
42 minutes and 11.46 USD at API prices: 9.74 USD of Opus and 1.72 USD of Sonnet, about 19.7
million tokens, 95% of them cache reads. Building and running the comparison matrix
afterwards took about an hour more in an SL7 container, most of it generating 40 test
events. As a rule of thumb from the two runs: about 3 USD per module plus 1.5 USD per 100
lines of module source.

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
- A review without a compiler can miss errors that a compiler would catch. Build and test
  before you use a result anywhere.
- The agents can be wrong in ways that look convincing: a confident report, a wrong number,
  a claim about an API that does not hold. The examples show each of these and how a second
  agent or a human caught it. Read the reports critically.
- Tested so far on two `dunereco` modules (`DisambigFromSpacePoints` twice,
  `NumberOfHitsFilter` once) and one LArSoft module (`larreco` `SpacePointSolver`), all in
  Claude Code, with Opus as extractor and verifier in the recent runs.
- Static review misses run-time faults. In the `SpacePointSolver` run all three reviewing
  agents read the line that makes the base module throw with `Fit: false`; only running that
  configuration found it. Other tools and models follow the same instructions but have not been tried.
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

v1 has been built and run (2026-10-17, Spack and MPD on EL9): `extraction-with-tests.patch`
applies to dunereco `v10_22_00d01`, the unit test passes, and the art output is identical
in all 8 configurations. A larreco `SpacePointSolver` run (2026-11-01, not in `examples/`)
was built in SL7 with `mrb` and compared over 40 single-particle events in 16 configurations
with `art_physics.py`: identical products and associations in all 14 that run, the same
exception in the 2 that throw, and DIFFERENT for a one-constant positive control.

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

## Copyright and licensing

Copyright © 2026 FERMI NATIONAL ACCELERATOR LABORATORY for the benefit of the DUNE
Collaboration.

This repository, and all software contained within, except where noted in `NOTICE.md`, is
licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Copyright is granted to FERMI NATIONAL ACCELERATOR LABORATORY on behalf of the Deep
Underground Neutrino Experiment (DUNE). Unless required by applicable law or agreed to in
writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

## Credits

The references quote and condense *Migrating to Phlex* and its GausHitFinder example, written
by the Phlex team at Fermilab under the same licence; see `NOTICE.md`. The approach builds on
work by Eric Church, Chris Jackson and colleagues at PNNL, who used AI agents to refactor
LArSoft's hit finder.
