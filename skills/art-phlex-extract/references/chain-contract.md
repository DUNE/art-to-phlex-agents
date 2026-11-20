# The contract between modules (outer loop, first pass)

A phase-1 extraction is checked module by module: the verifier reads the diff, the
validator compares this module's products before and after. A port can pass all of that
and still break the chain around it. It can rename a product instance that a downstream
module reads, drop an `Assns` that another module navigates, or rename a FHiCL parameter
that another job's configuration sets. `scripts/art_graph.py` makes that contract
visible and checks it.

## What it reads

Two things art writes, so no module source is parsed:

- the resolved configuration of each stage:
  `lar -c <job>.fcl --debug-config <job>.cfg.fcl`;
- the product list of the stage's input file, and of its output file if you have one:
  `lar -c eventdump.fcl -s <file> -n 1 > <file>.dump`.

Run both inside the container with the release (and for an extraction, the build area) set
up. The output dump needs one event through the job. The FD 1x2x6 reco2 job takes about
two minutes for one event.

An **edge** is a string parameter of one module whose value names another module's label
as an input tag (`label`, `label:instance`, `label:instance:process`). The label is matched
against the job's modules (source `job`) and the producers in the input file (source
`input`). Parameters named like a tag (`...Label`, `...Tag`, `...Producer`, `...Module`)
that match nothing are kept as `unresolved`.

art's `--data-dependency-graph` does not replace this. It is built from `consumes` calls.
On the FD 1x2x6 reco1 and reco2 jobs (dunesw v10_22_00d01) it showed no product edge
beyond the path order, because many LArSoft modules read with `getByLabel` and declare
nothing. Phlex needs every input declared, so those undeclared reads are also phase-2 work.

## Commands

```sh
G=$KIT/skills/art-phlex-extract/scripts/art_graph.py
# one JSON per stage, chain order
python3 $G stage --config reco1.cfg.fcl --input-products detsim.dump --output-products reco1.dump -o reco1.json
python3 $G stage --config reco2.cfg.fcl --input-products reco1.dump --output-products reco2.dump -o reco2.json

python3 $G impact spsolve reco1.json reco2.json   # what reads this module, in this stage and later
python3 $G check reco1.json reco2.json            # path order, missing instances
python3 $G diff base.json extracted.json          # same stage, two builds; exit 1 if different
python3 $G dot reco1.json reco2.json > chain.dot  # picture
```

- **`impact LABEL`** is the downstream contract of one module: the products it makes
  (type, instance), every module in this and later stages that names it in a tag, with
  the parameter, and whether its products reach the next stage's input file. Give it to the
  extractor before the extraction, and put it in the hand-off.
- **`diff`** is the check for an extraction. Make the stage JSON once with the base build
  and once with the extracted build, from the same job and input. Any difference in
  modules, products or edges is DIFFERENT, a blocker like a DIFFERENT row-by-row.
- **`check`** reports a consumer that runs before its producer, or on another trigger path,
  as an error, and an instance name the producer does not make as a warning. Unresolved
  names are counted per module, never errors (see the limits below).

## What it caught in the first tests (2026-11-19)

- FD 1x2x6 reco1 and reco2: `spsolve` has one reader, `hitfd` (`SpModuleLabel`). `hitfd`
  has nine readers in reco2: `pandora`, `cvnmap`, `emtrkmichelid` and six `EnergyReco`
  instances, by `HitLabel`, `HitModuleLabel` and `HitFinderModuleLabel`.
- The real SpacePointSolver extraction (`mrb` against `mrb-after`, `sps_rerun.fcl`):
  `identical`.
- Planted changes, each caught: renaming the `noreg` instance in the output (`diff`: two
  products), pointing `hitfd.SpModuleLabel` at a missing label (`diff`: the edge becomes
  unresolved), and swapping `spsolve` and `hitfd` in the path (`check`: "producer runs after
  the consumer").

## Limits

- A tag built in C++ is invisible: an instance name appended in code, or a product found by
  type (`getMany`, a `getView` with no tag). `impact` reads FHiCL only. Check the consumers'
  source for those.
- A string that happens to equal a module label is reported as an edge. Look at the
  parameter name.
- Parameters named `...Label` are not always art tags. The Pandora shower tools in reco2
  name their own intermediate results that way (62 unresolved names in `pandoraShower`).
  That is why unresolved names are notes.
- Only the jobs you give it. The DUNE-wide survey (every production job, to choose the
  order of extractions) is the next step and needs the list of production jobs.
