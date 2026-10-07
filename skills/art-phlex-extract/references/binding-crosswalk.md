# Phlex binding crosswalk

For the binding plan in `MIGRATION_NOTES.md` section 7. Pass 1 writes no Phlex code.

Condensed from *Migrating to Phlex*, chapter "Phlex Binding" (phlex-examples
`migration/doc/mapping.rst`, commit 5df307b). API names (`product_selector`,
`input_family`, `output_product_suffixes`) are those used in phlex-examples at that commit.
Checked against Phlex v0.4.1 (2026-09-30) and phlex-examples `phlex-v0.4` (c55bbfc). Where
the guide's prose snippets and v0.4 code differ, this file follows the code. The Phlex API is
still changing, so the plan should name node shapes and data flow rather than exact calls.

Binding is not a line-by-line rewrite. One art module does not have to become one Phlex
node. A module that mixed boundary input, transformation, reduction, and validation often
becomes several nodes, and that split is the point: each node becomes simpler and its role
explicit.

The organising questions change from "what happens when the framework calls `produce()`,
`beginSubRun()`, `endSubRun()`, or `analyze()`?" to:

- what is the callable shape of the extracted algorithm?
- which data products are its explicit inputs?
- what layer does it run in?
- does it create, transform, accumulate, expand, or observe data?

## Node shapes

| Extracted design | Phlex node | Algorithm shape |
|---|---|---|
| computes one output from explicit inputs | `transform` | `Out f(In1 const&, In2 const&, ...)` |
| boundary adapter introducing data from outside the graph (files, services, configuration) | `provide` | `Out f(data_cell_index const&)` |
| accumulation across events, subruns, or runs spread over callbacks | `fold` | `void step(Accumulator&, In const&)` |
| loop that expands one input into many work items | `unfold` | class constructed from the input product(s), with `initial_value()`, `predicate(Value)`, `unfold(Value[, data_cell_index const&]) -> std::pair<Value, Product>` |
| filter decision | `predicate` | `bool f(In const&, ...)` |
| validation or terminal side effect, no new product | `observe` | `void f(In const&, ...)` |

These are not rigid categories.

## Registration shapes (quoted from the guide)

```cpp
// provide
s.provide("provide_geometry",
          [geometry_name](phlex::data_cell_index const& /* job */) -> examples::geometry
          {
            return examples::geometry{geometry_name};
          })
  .output_product("input", "geometry", "job");

// transform
m.transform("add", examples::add, concurrency::unlimited)
  .input_family(product_selector{.creator = "input", .layer = layer, .suffix = "i"},
                product_selector{.creator = "input", .layer = layer, .suffix = "j"})
  .output_product_suffixes("sum");

// fold: target layer "run", initial value 0
auto add = [](int& sum, int value) { std::atomic_ref(sum) += value; };
g.fold("run_add", add, concurrency::unlimited, "run", 0)
  .input_family(product_selector{.creator = "input", .layer = "event", .suffix = "number"})
  .output_product_suffixes("run_sum");

// unfold (plugin API: destination layer, then concurrency)
m.unfold<iota>("iota", &iota::predicate, &iota::unfold, "lower1", concurrency::unlimited)
  .input_family(product_selector{.creator = "input", .layer = "event", .suffix = "max_number"})
  .output_product_suffixes("new_number");

// observe
m.observe("verify", verify_sum, concurrency::unlimited)
  .input_family(product_selector{.creator = "input", .layer = "job"},
                product_selector{.creator = "add", .layer = layer});
```

The guide's unfold snippet uses the internal `framework_graph` order (concurrency, then
layer). Plugins use layer, then concurrency (Phlex v0.4.1 `phlex/core/graph_proxy.hpp`;
gauss_hit_finder designs 1 to 3), as above.

Providers are registered in their own plugin with `PHLEX_REGISTER_PROVIDERS(s, config)` and
configured under `sources:` in jsonnet. The algorithm plugin (`PHLEX_REGISTER_ALGORITHMS`)
cannot call `provide`. Output is declared with `.output_product(creator, suffix, layer[, stage])`.

## Binding rules

Transform (the usual target for an extracted `EDProducer`):

- `event.getProduct(...)` becomes `.input_family(...)` plus ordinary function arguments,
- `event.put(...)` becomes the algorithm return value plus the output declaration,
- module members that are configuration or helper setup become lambda captures or objects
  constructed during registration.

Fold:

- mutable module members become explicit fold state,
- reset logic in `beginSubRun()` becomes the fold initial value,
- per-event updates become the fold function,
- the fold's output product is the accumulator object itself, built per partition cell from
  the initial-value arguments; it must be move-constructible or have a `send()` overload,
- a separate finalisation step (`Summary finalize(State const&)`, what `endSubRun()` used to
  publish) becomes a `send()` overload or a downstream `transform` at the fold layer,
- with `concurrency::unlimited` the step must be thread-safe on the shared accumulator (the
  guide's example uses `std::atomic_ref`),
- the fold target layer is declared at the registration site; no state machine is spread
  over callbacks.

Provide plus transform: when a module mixed boundary acquisition with algorithmic work, the
acquisition becomes a `provide` node and the algorithm a `transform`, with the extracted
function unchanged.

Unfold plus downstream nodes: a nested loop in one callback that splits an input, processes
the pieces, and reduces the results becomes `unfold` → `transform` → `fold`. GausHitFinder
designs 1 to 3 do this for the loops over wires and then ROIs, giving the layer hierarchy
spill → wire → roi.

Observe: analyzers, validation-only code, and producer-side checks that emit no product.

## Transitional binding issues

Valid intermediate states exist: stubbed geometry-dependent fields, a temporary file-based
provider for comparison testing, output sorting and printing to validate against art. They
are not failures of the binding. Document them openly and reduce them over time.

## Binding checklist (from the guide)

1. The extracted computation uses the appropriate node shape: `provide`, `transform`,
   `fold`, `unfold`, or `observe`.
2. Product retrieval from callbacks is replaced by explicit input declarations.
3. Configuration and helper setup appear in registration code, not in the algorithm.
4. Boundary-only work is separate from reusable algorithm code.
5. The chosen layer matches the real scope of the computation: event, subrun, run, job, or a
   derived lower layer.
6. A former art module that did several kinds of work is split into several nodes.
7. Transitional limitations are documented rather than hidden.

## Writing the plan (kit guidance)

One row per extracted piece:

- **node shape** from the table above,
- **inputs** as creator / layer / suffix; use the art module label and product instance
  names as provisional creator and suffix. Record the art process name, if the `InputTag`
  names one, as the Phlex *stage*. Creator matches either the producing plugin's label or its
  algorithm name. Names are word characters only. Type is part of the match, so the suffix can
  be empty when the type is unique (as in gauss_hit_finder). An `InputTag` FHiCL parameter
  maps to `config.get<product_selector>(...)`,
- **output suffix**,
- **layer**: what the computation really spans (a whole event, one APA, one wire, a subrun),
- **concurrency**: `unlimited` when the function is re-entrant; `serial` when it touches
  ROOT globals or fitters, a random engine, mutable static state, or a provider that is not
  thread-safe. Omitted concurrency defaults to `serial`. When a non-re-entrant dependency is
  shared by several nodes (fitter, RNG engine, ROOT object, non-thread-safe provider), prefer
  planning it as a *serialized resource* (`resource<T>{}` in `input_family`, registered by a
  `PHLEX_REGISTER_RESOURCES` plugin) with the node `unlimited`. Resource arguments are the
  function's trailing parameters,
- **resources**: shared objects the piece needs, each marked serialized or unlimited,
- **gate**: the predicate it runs under, if the art module sat behind a filter,
- **blockers**: Phlex gaps the piece depends on.

Gaps named by the guide and the GausHitFinder README as of 2026-09: persistable associations,
histogramming (TFileService), richer conditions access, tools/plugins, optional outputs
(fixed multiple outputs are supported via a `std::tuple` return since v0.4), no
random-number seeding facility, and a settled logging facility (spdlog for now).

Kit patterns for two common LArSoft shapes, so plans agree across modules:

- **Consumed associations** (`FindManyP<B>(handleA, evt, label)` as an input). Plan the
  association as an upstream product of index lists, for example
  `std::vector<std::vector<std::size_t>>` from A index to B indices, published by the
  producer of the association or by an adapter `transform`. Mark it blocked on persistable
  associations if the producer is still an art module. This representation is provisional:
  Phlex treats references and associations as active design work
  ([phlex-design: persistent references and associations](https://github.com/Framework-R-D/phlex-design/blob/main/persistent-references-and-associations.md);
  DUNE's requirement classes, including FD-TPC same-type associations, are on the
  [DUNE Phlex project I/O page](https://dune.github.io/dune-phlex-project/io-persistence.html)).
  Say in the plan which requirement class the association falls in, so the plan can be
  updated when Phlex settles the design.
- **Output built through an art-dependent helper** (`recob::HitCreator`,
  `HitCollectionCreator`, other `lardata/ArtDataHelper` classes). The algorithm returns the
  data (hits, index pairs); the plan names the helper as a blocker that needs a
  framework-free equivalent, and lists the associations it fills.

The guide does not yet cover `EDFilter`. Plan a filter as a `predicate` node
(`bool f(In const&...)`); downstream nodes gate on it with `.experimental_when("<predicate>")`
or jsonnet `experimental_when: [...]` (still experimental in v0.4.1). A Phlex predicate gates
only the nodes that name it, unlike an art path.
