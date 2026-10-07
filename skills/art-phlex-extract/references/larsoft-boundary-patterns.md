# LArSoft and DUNE boundary patterns

These are kit additions, not part of the Phlex team's guide. They apply the guide's rule
("service access at the boundary, ordinary C++ inputs to the algorithm") to facilities that
appear in most LArSoft-based modules. Check each API against the LArSoft version the target
repository builds with; names moved between LArSoft 9 and 10.

## Contents

- Detector clocks and properties
- Geometry and wire readout
- Other providers and channel maps
- Histograms and TTrees
- Random numbers
- art Tools
- Associations written by the module
- Associations read by the module
- Collection helpers
- Logging and exceptions
- Event metadata
- Filters
- Accumulation across events
- Validated configuration
- Thread safety
- CMake

## Detector clocks and properties

LArSoft already has per-event data objects for this.

```cpp
// boundary (module callback)
auto const clockData = art::ServiceHandle<detinfo::DetectorClocksService const>()->DataFor(e);
auto const detProp =
  art::ServiceHandle<detinfo::DetectorPropertiesService const>()->DataFor(e, clockData);
auto result = find_things(fCfg, wires, clockData, detProp);

// algorithm header
#include "lardataalg/DetectorInfo/DetectorClocksData.h"
#include "lardataalg/DetectorInfo/DetectorPropertiesData.h"
Things find_things(ThingsCfg const& cfg,
                   std::vector<recob::Wire> const& wires,
                   detinfo::DetectorClocksData const& clockData,
                   detinfo::DetectorPropertiesData const& detProp);
```

Older helpers that call `lar::providerFrom<detinfo::DetectorPropertiesService>()` internally
get the same treatment. Call `DataFor` once per event at the boundary, as before; do not
move the call into a per-item loop.

## Geometry and wire readout

Pass the framework-free provider by reference:

```cpp
// boundary
geo::GeometryCore const& geom = *lar::providerFrom<geo::Geometry>();
geo::WireReadoutGeom const& wireReadout = art::ServiceHandle<geo::WireReadout const>()->Get();  // LArSoft 10+

// algorithm
#include "larcorealg/Geometry/GeometryCore.h"
#include "larcorealg/Geometry/WireReadoutGeom.h"
```

In Phlex, geometry will reach algorithms as a job-layer data product. A `const&` parameter
already has that shape. If the original code stored `fGeom` as a member pointer set in the
constructor, the module may keep that member; the algorithm receives the reference.

## Other providers and channel maps

- Channel status: `lar::providerFrom<lariov::ChannelStatusService>()` gives
  `lariov::ChannelStatusProvider const*`; pass `ChannelStatusProvider const&`.
- Other `lariov` calibration services follow the same service/provider split.
- DUNE channel-map services (for example `PdspChannelMapService`) usually have no provider
  split. If the algorithm needs only a few lookups, build a plain lookup table at the boundary
  and pass it. If that would change behaviour or cost too much, keep the service call where it
  is, mark it `PHLEX-TRANSITIONAL`, and say in the binding plan that the map will become
  run-layer data.

## Histograms and TTrees

Booking stays at the boundary (constructor or `beginJob` with `art::TFileService`). Prefer
that the algorithm returns the values and the module fills:

```cpp
struct HitDiagnostics { std::vector<double> chi2; std::vector<int> multiplicity; };
std::pair<std::vector<recob::Hit>, HitDiagnostics> find_hits(...);
// module: for (auto v : diag.chi2) fChi2Hist->Fill(v);
```

Preserve fill conditions exactly. If fills are interleaved with logic in a way that makes
returning values awkward, passing `TH1&` into the algorithm is an acceptable transitional step
(ROOT, not art), but the binding plan must mark it `serial`.

For an analyzer that fills a TTree, the algorithm computes a row struct (or a vector of rows)
and the module copies it into branch variables and calls `Fill()`. That is an `observe`
shape.

## Random numbers

The engine is created and seeded at the boundary (constructor, NuRandomService or
`createEngine`). The algorithm takes `CLHEP::HepRandomEngine&`. Keep the number and order of
draws identical, including draws whose results are discarded. Mark the parameter
`PHLEX-TRANSITIONAL` (random engine) and plan `serial`, or note that Phlex will need
per-data-cell seeding.

## art Tools

Phlex will not support Tools. In pass 1, construct them at the boundary with `art::make_tool`
as before and pass the interface by reference. If the interface header is framework-free,
the algorithm can depend on it. If the interface has `art::Event` or `fhicl::ParameterSet` in
its methods, mark the dependency transitional and list it. Replacing a tool with a directly
configured class (as the GausHitFinder prototype did) is binding-stage work.

## Associations written by the module

The algorithm returns indices; the module builds `art::Assns`.

```cpp
// algorithm
struct ClusterResult {
  std::vector<recob::Cluster> clusters;
  std::vector<std::vector<std::size_t>> hit_indices;  // per cluster: indices into the input hits
};
ClusterResult make_clusters(ClusterCfg const& cfg, std::vector<recob::Hit> const& hits);

// boundary
auto const hitHandle = e.getValidHandle<std::vector<recob::Hit>>(fHitLabel);
auto result = make_clusters(fCfg, *hitHandle);
auto assns = std::make_unique<art::Assns<recob::Cluster, recob::Hit>>();
art::PtrMaker<recob::Cluster> const makeClusterPtr{e};
for (std::size_t c = 0; c < result.clusters.size(); ++c)
  for (auto const h : result.hit_indices[c])
    assns->addSingle(makeClusterPtr(c), art::Ptr<recob::Hit>{hitHandle, h});
e.put(std::make_unique<std::vector<recob::Cluster>>(std::move(result.clusters)));
e.put(std::move(assns));
```

Add pairs in the same order as the original code (for example the order of `util::CreateAssn`
calls), so the association collection is identical, not just equivalent. If the original
built `art::Ptr`s from a `std::vector<art::Ptr<Hit>>` produced by `fill_ptr_vector`, the key
equals the index into the handle's vector, so `art::Ptr<recob::Hit>{hitHandle, h}` matches.
If the original used a filtered or re-sorted pointer vector, carry the original keys, not
positions in the filtered list.

## Associations read by the module

Resolve them at the boundary into plain containers:

```cpp
auto const clusterHandle = e.getValidHandle<std::vector<recob::Cluster>>(fClusterLabel);
art::FindMany<recob::Hit> const hitsFromClusters{clusterHandle, e, fClusterLabel};
std::vector<std::vector<recob::Hit const*>> hitsPerCluster(clusterHandle->size());
for (std::size_t i = 0; i < clusterHandle->size(); ++i)
  hitsPerCluster[i] = hitsFromClusters.at(i);
auto result = make_tracks(fCfg, *clusterHandle, hitsPerCluster);
```

The pointers are valid only during this callback; the algorithm must not keep them. If the
algorithm needs keys (to write new associations to those hits), pass
`std::vector<std::vector<std::size_t>>` of keys next to the pointers, taken from
`FindManyP` at the boundary.

## Collection helpers

`recob::HitCollectionCreator`, `anab::FVectorWriter`, `util::CreateAssn`, and similar helpers
stay at the boundary. The algorithm returns plain objects (`recob::Hit` values, index lists),
and the module feeds them to the helper in the original order.

Helpers also declare products. `recob::HitCollectionCreator::declare_products(producesCollector(), "", true, false)`
declares a hit collection and a hit-wire association without a visible `produces<>`. The
contract check lists `declare_products` and `produces_using` calls with their arguments. Any
other helper idiom that declares products is invisible to it, so diff the constructor by hand
and say so in the notes. The helper's constructor arguments in the callback
(`HitCollectionCreator hcol(evt, doWireAssns, doRawDigitAssns)`) are not in the contract
either; check them by hand.

## Logging and exceptions

- Summary messages that use values available at the boundary: log in the module, unless
  that would change the order of log messages (for example a summary emitted between two
  algorithm passes that log warnings). Log order wins: keep the summary in the algorithm
  with a `// PHLEX-TRANSITIONAL: logging` marker.
- Messages deep inside the algorithm: keep the `mf::Log*` call where it is with a
  `// PHLEX-TRANSITIONAL: logging` marker (and on the `messagefacility` include). Do not
  delete them or change their text. Phlex will choose a logging facility later.
- Algorithm code must not reconfigure the global spdlog logger; Phlex prevents plugins from
  replacing its default logger.
- `cet::exception` in the algorithm is acceptable (cetlib_except is a leaf library); keep
  category and message unchanged, because art configuration can act on categories.
- `art::Exception` in the algorithm: keep it, marked transitional, rather than changing the
  exception type in pass 1.

## Event metadata

`e.id().event()`, `e.run()`, `e.subRun()`, `e.isRealData()`, `e.time()` become explicit
parameters. In Phlex these come from the data-cell index (or from
`handle<T>::data_cell_index()` on an input product) or a provided product, so name them in
the binding plan.

## Filters

The algorithm returns the decision (`bool`, or a struct with products and the decision); the
module's `filter()` returns it. Keep the art-side behaviour when products are put only on
pass or fail.

## Accumulation across events

For `beginSubRun`/`endSubRun`, `beginRun`/`endRun`, or `endJob` summaries built from
per-event updates, extract:

```cpp
struct EfficiencyState { /* what the members accumulated */ };
void accumulate(EfficiencyState& state, Inputs const& perEvent);  // body of produce()/analyze()
Summary finalize(EfficiencyState const& state);                     // body of endSubRun()
```

The module keeps the state as a member, resets it where the original did, calls `accumulate`
per event and `finalize` where it published. `accumulate` maps onto a Phlex `fold`;
`finalize` onto the fold's `send()` overload or a following `transform`. Keep the state a
separate, move-constructible type.

## Validated configuration

When the module uses `fhicl::Table<Config>`, keep the `Config` struct in the module and add a
small `make_cfg(Config const&)` that copies into the plain configuration struct. Parameter
names, comments, and defaults stay in the FHiCL description, the single source of defaults.

## Thread safety

For each extracted function, state in the notes whether it is re-entrant: no mutable statics,
no ROOT global state (`gRandom`, `gMinuit`, `TF1::Fit` through global fitters), no mutable
members, no random engine, no non-thread-safe provider. Re-entrant functions can later run
with `concurrency::unlimited`; the rest need `serial` or redesign.

## CMake

DUNE repositories use two idioms. Check the directory before editing.

**`art_make(...)`.** Globs every `*.cxx` in the directory into the directory library
(`LIB_LIBRARIES`) and every `*_module.cc` into a plugin (`MODULE_LIBRARIES`). A new `.cxx`
needs no listing. Confirm that `LIB_LIBRARIES` covers what the algorithm uses (for example
`lardataobj::RecoBase`, `larcorealg::Geometry`, `lardataalg::DetectorInfo`, `ROOT::Hist`) and
that `MODULE_LIBRARIES` includes the directory library.

**`cet_build_plugin(Name art::module LIBRARIES ...)`** (or legacy `simple_plugin`). The plugin
is built from `Name_module.cc` only. The algorithm needs a library target:

- If the directory already has `cet_make_library(...)` or `art_make_library(...)`, add the
  source there (check whether it lists `SOURCE` explicitly or globs).
- Otherwise add one and link the plugin to it, following the naming of neighbouring targets:

```cmake
cet_make_library(LIBRARY_NAME <package>_<Name>Alg
  SOURCE <Name>Alg.cxx
  LIBRARIES PUBLIC lardataobj::RecoBase larcorealg::Geometry)

cet_build_plugin(<Name> art::module
  LIBRARIES PRIVATE <package>_<Name>Alg ...existing libraries...)
```

Do not add `art::*`, `canvas::*`, `fhiclcpp::*`, or `messagefacility::*` to the algorithm's
library unless a transitional item requires it; needing them means the extraction is not
finished.
