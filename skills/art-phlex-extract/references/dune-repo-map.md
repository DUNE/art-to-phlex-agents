# DUNE art-era repositories and their Phlex-era homes

Kit reference, written for this kit (not from the Phlex guide). Repository list checked
against the GitHub API for the `DUNE` organization on 2026-10-04; the descriptions on the
[DUNE Phlex project site](https://dune.github.io/dune-phlex-project/repositories.html) agree.
As of that date the Phlex-era repositories are placeholders with no substantive code.

DUNE is moving its Phlex-era code into new repositories, for example `dunecore` to
`dune-core`, with code review required from the start. The split is by subsystem, not one to
one: one art-era repository maps to several new ones, and the choice depends on what the
code does and which detector it serves. **DUNE has not published a file-by-file mapping.**
The table below is the kit's guide for writing a binding plan. The software management and
the Phlex Integration WG decide where code actually goes.

## What this changes in phase 1

- **The work is done in an art-era worktree.** Phase 1 keeps the module an art module that
  builds with the current release, so the extraction is made and checked on a local branch
  of `dunereco`, `dunecore` and so on. Where it lands afterwards (the Phlex-era repository,
  the art-era repository, or neither yet) is to be decided by the DUNE Software Lead and Code Management.
- **The binding plan names the Phlex-era home** of each extracted piece: one repository from
  the table, or two candidates and the question that decides between them.
- **Dependencies are recorded with their homes.** Every header the algorithm files include
  from a DUNE art-era repository is a dependency that must exist in a Phlex-era repository
  before the algorithm can move. List each one with its likely home (for example a
  `dunecore` geometry helper with `dune-geo-utils`). An algorithm in a subsystem repository
  may depend on `dune-core`, `dune-obj`, `dune-geo-utils` and `dune-utils`, not on another
  subsystem repository; if it needs one, say so as a blocker.
- **LArSoft modules are not DUNE code.** For a module in a LArSoft repository, record the
  target as "LArSoft (upstream)". Its Phlex-era home is a LArSoft decision. Note which DUNE
  jobs use it, because DUNE may need it before LArSoft moves.

## Mapping guide

| Art-era repository | Phlex-era home(s) | How to choose |
|---|---|---|
| `dunecore` | `dune-core`; `dune-geo-utils` for geometry, channel maps and wire readout; `dune-utils` for general utilities | by what the code is, not where it sits today |
| data product packages (for example `duneanaobj`, data products inside `dunecore`) | `dune-obj` | data product definitions only |
| `dunereco` | `dune-fd-reco`; `dune-nd-reco` for ND code; `dune-pd-hd`, `dune-pd-vd`, `dune-pd-sp` when only one protoDUNE uses it | which detectors' production jobs run it (`dunesw` FHiCL) |
| `duneprototypes` | `dune-pd-hd`, `dune-pd-vd`, `dune-pd-sp`, `dune-iceberg` | the prototype the code serves |
| `dunesim` | `dune-fd-sim`; `dune-nd-sim` | detector |
| `duneopdet` | `dune-op-det` | |
| `dunecalib` | `dune-calib` | |
| `duneana` | `dune-fd-ana`; `dune-nd-ana` | detector |
| `dunedataprep` | `dune-fd-hd`, `dune-fd-vd` for detector-specific preparation; `dune-core` for shared tools | open question |
| `dunendlar` | `dune-nd-lar` | |
| trigger code | `dune-trigger` | |
| `duneexamples` | `dune-examples` | |
| HD- or VD-specific detector code | `dune-fd-hd`, `dune-fd-vd` | |
| SAND, TMS | `dune-sand`, `dune-tms-phlex` | |

Rows marked "open question", and any module whose production jobs span far detector and
protoDUNE, go to the human with the candidates.

A module that more than one protoDUNE runs, and no far detector job, has no agreed home yet.
Record it as `ambiguous: dune-pd-hd / dune-pd-vd` (list the prototypes whose jobs run it) and
do not pick one. The Phlex Adoption WG decides where shared protoDUNE code goes; update this
paragraph when it does.

## How to find which detectors use a module

Grep the production configurations for the module's prolog names, as in `art-phlex-extract`
step 1, and list the jobs by detector: `dunesw/fcl/dunefd/` (far detector),
`dunesw/fcl/protodunehd/`, `dunesw/fcl/protodunevd/`, `dunesw/fcl/protodune/` (protoDUNE-SP),
and the ND directories. A module used by both far detector and protoDUNE jobs usually belongs
with the far detector code, with the protoDUNE configuration in the protoDUNE repository; say
so as a candidate, not a decision.
