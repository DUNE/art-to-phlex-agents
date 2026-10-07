# Algorithm extraction

Condensed from *Migrating to Phlex*, chapter "Algorithm Extraction"
(phlex-examples `migration/doc/refactoring.rst`, commit 5df307b), with the design-0
GausHitFinder example from `migration/gauss_hit_finder/`.

## Two parts

**Algorithm part.** The domain logic. It operates on plain C++ values, experiment data
structures, and explicitly provided helper objects, with no framework callbacks, event
objects, handles, services, or registration machinery. It answers "what computation is
being performed?"

**Framework-dependent part.** Configuration lookup, input retrieval, helper construction,
registration, and output publication. It answers "how is this computation wired into the
framework?"

A good extraction leaves the algorithm usable from an ordinary unit test or standalone
driver. Because many modules have little test coverage, extraction should minimise changes
to the core logic while moving framework code into a separate boundary layer.

## Properties of a successful extraction

- The algorithm is defined in plain functions or small classes.
- The algorithm can be called from ordinary C++.
- The algorithm does not depend on callbacks such as `produce()` or `analyze()`.
- The algorithm contains no direct framework code.
- Configuration is gathered once and passed explicitly.
- Input products are passed in as parameters.
- Output products are returned as values.
- Remaining framework assumptions are visible and localised.

## Recommended pattern

1. Define a plain configuration structure.
2. Extract the core computation into a free function or small class.
3. Pass all required inputs explicitly.
4. Return outputs directly.
5. Keep framework registration in a separate translation unit.

Kit additions for Phlex v0.4.1 readiness (cheap under art, avoid rework at binding):

- inputs are `T const&` or by value; never mutate an input product in place,
- outputs are returned by value and are move-constructible; fixed multiple outputs are a
  struct or `std::tuple`, not out-parameters (optional outputs stay a recorded blocker),
- shared helpers that are not thread-safe (fitters, RNG engines, ROOT objects, providers that
  are not thread-safe) are explicit *trailing* parameters, named in the plan as serialized
  resource candidates,
- accumulation state is a separate type, constructible from its reset value and
  move-constructible; the step is `void step(State&, Inputs const&...)` and finalisation is a
  separate pure function.

### Example: GausHitFinder, design 0

The configuration structure mirrors the parameters of `GausHitFinder_module.cc` in larreco
but depends on neither art nor Phlex:

```cpp
struct find_hits_with_gaussians_cfg {
  bool filter_hits;
  std::vector<int> long_max_hits_vec;
  std::vector<int> long_pulse_width_vec;
  int max_multi_hit;
  int area_method;
  std::vector<double> area_norms_vec;
  double chi2_ndf;
  std::vector<float> pulse_height_cuts;
  std::vector<float> pulse_width_cuts;
  std::vector<float> pulse_ratio_cuts;
};
```

The algorithm is a normal function:

```cpp
using Hits = std::vector<recob::Hit>;
using CandHitStandardPtr = std::shared_ptr<CandHitStandard>;

Hits find_hits_with_gaussians(find_hits_with_gaussians_cfg const& cfg,
                              std::vector<recob::Wire> const& wires,
                              std::vector<CandHitStandardPtr> const& cand_hit_standard,
                              PeakFitterMrqdt const& peak_fitter_mrqdt,
                              HitFilterAlg const& hit_filter_alg);
```

The signature makes the boundary explicit: `cfg` is immutable configuration, `wires` is the
input product, the helper algorithms are dependencies passed in from outside, and the return
value is the output product.

These concerns belong outside the algorithm: framework configuration retrieval, event
product lookup, service lookup, plugin (tool) construction, output insertion into the event,
and registration macros. Moving them out often shows the core logic is smaller than
expected.

In the Phlex version the boundary is a registration file that builds the struct and helpers
once and captures them (from `register_find_hits_with_gaussians_design0.cpp`):

```cpp
PHLEX_REGISTER_ALGORITHMS(m, config)
{
  auto const layer = config.get<std::string>("layer");

  m.transform(
     "find_hits_with_gaussians_design0",
     [cfg = main_cfg(config),
      cand_hit_standard_vec = make_cand_hit_standard_vec(config),
      peak_fitter_mrqdt = make_peak_fitter_mrqdt(config),
      hit_filter_alg = make_hit_filter_alg(config)](std::vector<recob::Wire> const& wires) {
       return examples::find_hits_with_gaussians_design0(
         cfg, wires, cand_hit_standard_vec, *peak_fitter_mrqdt, *hit_filter_alg);
     },
     concurrency::unlimited)
    .input_family(product_selector{.creator = "wires", .layer = layer, .suffix = ""})
    .output_product_suffixes("hits");
}
```

In pass 1 of this kit, the art module's constructor and callback play the role of that
registration file (config struct built once, helpers constructed once, algorithm called per
event). The algorithm files are the same either way, which is why extraction first makes
binding a small step.

## What may stay in the algorithm temporarily

A migration can proceed with transitional framework assumptions if they are visible and
localised. The GausHitFinder example marks geometry limitations and comparison-oriented
output with comments. In this kit, mark such lines `// PHLEX-TRANSITIONAL: <reason>` and
list them in the notes, so `check_purity.py` and the verifier can account for each one.

## Extraction checklist (from the guide)

1. Can the core algorithm be described without mentioning framework callbacks?
2. Are all real inputs represented in the function signature or constructor?
3. Are all outputs represented as return values or explicit output objects?
4. Is configuration collected outside the algorithm?
5. Are remaining framework assumptions documented as transitional issues?

## Common extraction mistakes

- A helper class still reaches into framework state because that was convenient in the
  original module.
- Configuration parsing remains spread across several helper objects.
- Service access remains hidden inside low-level logic.
- The new code preserves the old module structure even when the algorithm itself is much
  simpler.

"The goal is not to preserve familiar structure. It is to expose the real computation
cleanly enough that it can be expressed in Phlex."

## Lessons from the GausHitFinder migration README

The Phlex prototype made choices that suit a Phlex job but would change art output. Pass 1
keeps art behaviour, so read these as "what binding will have to decide", not as edits to
make now.

- **Tools.** Phlex will not support art Tools. Design 0 replaced the two tool types with
  directly constructed classes configured by plain structs.
- **Optional and multiple outputs.** GausHitFinder can write one or two hit collections and
  optional `Assns`. The prototype writes one `std::vector<recob::Hit>` because Phlex has no
  association support yet.
- **Histograms.** Histograms booked in `beginJob` through TFileService were removed (no
  Phlex histogramming yet). Pass 1 keeps them at the art boundary.
- **Logging and geometry.** MessageLogger calls were commented out and geometry calls stubbed
  (plane 0, default `WireID`, signal type 0). Pass 1 keeps both working and passes geometry in
  explicitly.
- **Unused state.** `fEventCount` was dropped: reconstruction should not depend on event count.
- **Validation.** art and Phlex jobs ran on identical input (serialised `std::vector<recob::Wire>`)
  and hit printouts were compared after sorting, because multithreading changes the order of
  hits and events. Phlex v0.4 jobs also require a stage name (`--stage <name>` or top-level
  `stage:`).
