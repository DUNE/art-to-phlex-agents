# Framework and domain logic separation

Condensed from *Migrating to Phlex*, chapter "Framework and Domain Logic Separation"
(phlex-examples `migration/doc/preparation.rst`, commit 5df307b). Code blocks are quoted
from the guide.

The goal is to remove, reduce, or isolate art concepts that would otherwise leak into
algorithm code. Not every art type goes at once. Decide which concepts are needed to
preserve the module's framework-visible output and which are only convenience.

For each art concept in the code:

1. decide whether it is required to preserve framework-visible output, or only a convenience;
2. remove it where it is only a convenience;
3. isolate it in framework-boundary code where it is still required;
4. convert the algorithm code to ordinary C++ inputs and outputs.

## Contents

- Cross-cutting rules
- `art::Ptr` and pointer-like access
- Product retrieval and event-boundary access
- Associations and navigation
- Services

## Cross-cutting rules

- keep framework API use at the module boundary
- do not cache event-scoped objects across events
- prefer explicit inputs over implicit framework access
- prefer ordinary C++ containers and references in helper code
- preserve art-specific types only where persisted behaviour requires them

## `art::Ptr` and pointer-like access

A module typically needs `art::Ptr` only when it puts an `art::Ptr`-based product into the
event: `art::Assns`, `art::PtrVector`, `art::PtrMaker`-produced pointers, or a
`std::vector<art::Ptr<T>>`. It may also need to stay at the boundary when association
chaining depends on `art::Ptr<T>::key()`.

It can usually be removed when the code only needs:

- read-only object access,
- stable ordering within one collection,
- a relationship expressed by an index or key, or
- temporary navigation during one computation.

In helper code, pass object values, references, indices, `std::vector<T> const&`,
`std::vector<T const*> const&`, or a lookup table built at the boundary.

Single-element access:

```cpp
// Before
art::Handle<std::vector<T>> h;
evt.getByLabel(label, h);
art::Ptr<T> p(h, 0);
p->method();

// After
T const& p = evt.getProduct<std::vector<T>>(label).at(0);
p.method();
```

Loop-local pointer construction:

```cpp
// Before
for (size_t i = 0; i < h->size(); ++i) {
  art::Ptr<T> p(h, i);
  p->method();
}

// After
for (auto const& p : *h) {
  p.method();
}
```

`FindManyP` to `FindMany` when only object access is needed:

```cpp
// Before
art::Handle<std::vector<T>> h;
evt.getByLabel(label, h);
std::vector<art::Ptr<T>> v;
art::fill_ptr_vector(v, h);
art::FindManyP<U> fm(v, evt, label2);
std::vector<art::Ptr<U>> const& items = fm.at(i);
items[j]->method();

// After
auto const h = evt.getValidHandle<std::vector<T>>(label);
art::FindMany<U> fm(h, evt, label2);
std::vector<U const*> const& items = fm.at(i);
items[j]->method();
```

Helper signatures that only read the object:

```cpp
// Before
void f(art::Ptr<T> const& p) { p->method(); }

// After
void f(T const& p) { p.method(); }
```

- Collection parameters, in order of preference: `std::vector<T> const&` (the product
  itself), `std::vector<T const*> const&` (a filtered subset), `std::vector<art::Ptr<T>>`
  (only when persisted references are needed).
- Use `FindMany<T>` when only the objects are needed and nothing chains further. Keep
  `FindManyP<T>` only when the code chains into another association through `.key()`.
  Never replace `.key()` with pointer arithmetic.
- Includes that often disappear with `art::Ptr`: `canvas/Persistency/Common/Ptr.h`,
  `canvas/Persistency/Common/FindManyP.h` (when `FindMany` suffices), and
  `lardata/Utilities/AssociationUtil.h` (when only used for `fill_ptr_vector`).

Review carefully when the module writes associations or other pointer-based products, when
`FindManyP` may still be needed for chaining, when the code depends on `.key()` or
provenance, or when a helper stores pointers beyond the event.

Mechanical replacement patterns and decision rules: `art-ptr-removal.md`.

## Product retrieval and event-boundary access

Rule: move retrieval to the top-level framework boundary and pass retrieved products as
explicit function parameters. Find every call path that reaches into the event, list the
products the algorithm really needs, and remove event access from helper classes unless they
are deliberately part of the framework layer.

`art::Handle` objects do not outlive the event and must never be module data members.
Event-scoped products, pointers, references, and derived data must not be cached across
events.

Choosing the retrieval call:

- `evt.getProduct<C>(tag)` when only the product is needed downstream,
- `evt.getValidHandle<C>(tag)` when a handle is needed and the product must exist,
- `evt.getHandle<C>(tag)` when the product may legitimately be absent; test with
  `if (!h)`, not `.isValid()`.

Do not introduce new `getByLabel(tag, handle)` code. Where older code throws on an invalid
handle, use `getProduct` or `getValidHandle` and drop the manual check.

```cpp
// Only the product is needed
// Before
art::Handle<std::vector<recob::Wire>> wireVecHandle;
evt.getByLabel(fCalDataModuleLabel, wireVecHandle);
// After
auto const& wires = evt.getProduct<std::vector<recob::Wire>>(fCalDataModuleLabel);

// A handle is still needed (for example to build art::Ptr for associations)
// After
auto const wireVecHandle =
  evt.getValidHandle<std::vector<recob::Wire>>(fCalDataModuleLabel);
// art::Ptr<recob::Wire>(wireVecHandle, i) still works

// The product may legitimately be absent
// Before
art::Handle<std::vector<recob::Hit>> hitcol;
evt.getByLabel(fHitModuleLabel, hitcol);
if (!hitcol.isValid()) return;
// After
auto const hitcol = evt.getHandle<std::vector<recob::Hit>>(fHitModuleLabel);
if (!hitcol) return;

// getByLabel combined with fill_ptr_vector where art::Ptr is still required
// After: replace only the retrieval
auto const hitcol = evt.getValidHandle<std::vector<recob::Hit>>(fHitModuleLabel);
std::vector<art::Ptr<recob::Hit>> hits;
art::fill_ptr_vector(hits, hitcol);
```

A helper that receives the event and retrieves internally:

```cpp
// Before: helper retrieves data from the event
class SomeAlg {
  void run(art::Event const& evt) {
    auto const& tracks = evt.getProduct<std::vector<recob::Track>>(fLabel);
    // ...
  }
};
fAlg.run(evt);

// After: module retrieves at the boundary; helper receives explicit input
class SomeAlg {
  void run(std::vector<recob::Track> const& tracks) {
    // ...
  }
};
auto const& tracks = evt.getProduct<std::vector<recob::Track>>(fLabel);
fAlg.run(tracks);
```

Review carefully when optional products are part of the intended behaviour.

## Associations and navigation

Associations are still under development in Phlex. They may remain at the framework boundary
during a staged migration, especially when the module's output is defined in terms of
`art::Assns`. Even then, keep that representation out of reusable algorithm code.

Inventory `FindOneP`, `FindManyP`, and `art::Assns` construction, and separate
navigation-only use from persisted output. Review carefully when code builds new
associations or when helper logic depends on persistent references rather than object
access. See `larsoft-boundary-patterns.md` for the index-based pattern used by this kit.

## Services

Phlex has no services: nothing is looked up globally and there are no framework callbacks.
Since v0.4 a node can declare *resources*, shared objects registered once and passed
explicitly as trailing arguments; they are the Phlex-side target for many service-provided
helpers. An art service is a globally accessible stateful object
with framework callbacks and dependencies on other services, which makes it a frequent
source of hidden dependencies. **`art::ServiceHandle` use belongs at the framework boundary,
not inside reusable algorithm code.**

For each `ServiceHandle` or service-provided object, identify what downstream code needs:

- a read-only value or data structure,
- a helper object that can be passed in explicitly,
- a side effect such as logging or output production, or
- a service feature that cannot yet be represented another way.

Then:

- remove `ServiceHandle` construction from algorithms, helpers, and utility classes,
- retrieve the needed value or object in the module callback,
- replace hidden service access with explicit function parameters or constructor arguments,
- treat read-only shared state (geometry, calibration constants, channel maps) as data
  inputs rather than global handles, and
- record any remaining service dependencies as explicit migration-design items.

```cpp
// Before: service access inside algorithm (problematic)
Tracks make_tracks(Hits const& hits)
{
  art::ServiceHandle<Calibration> calibration;
  ScalarOffset const& offset = calibration->Offset();
  // ...
}

void TrackMaker::produce(art::Event& e)
{
  auto const& hits = e.getProduct<Hits>("GoodHits");
  Tracks tracks = make_tracks(hits);
  e.put(std::make_unique<Tracks>(std::move(tracks)), "GoodTracks");
}

// After: service access confined to module boundary
Tracks make_tracks(Hits const& hits, ScalarOffset const& offset)
{
  // no framework types; offset is an ordinary C++ value
  // ...
}

void TrackMaker::produce(art::Event& e)
{
  auto const& hits = e.getProduct<Hits>("GoodHits");
  art::ServiceHandle<Calibration> calibration;
  Tracks tracks = make_tracks(hits, calibration->Offset());
  e.put(std::make_unique<Tracks>(std::move(tracks)), "GoodTracks");
}
```

This is the intended shape even while the art service cannot be removed. Once the code runs
under Phlex, the algorithm function stays unchanged; only the registration declares where
the offset comes from.

Completion checks:

- `art::ServiceHandle` appears in no function or class that is not itself a module or
  framework-boundary object,
- every value extracted from a service is passed as a parameter or constructor argument,
- helpers that took an event or service handle now take the extracted value, and
- service dependencies that cannot be removed are recorded as migration-design items.

Do not introduce new services for:

- **logging**: ordinary C++ logging needs no framework wrapper (Phlex currently uses spdlog;
  algorithm code must not reconfigure the global spdlog logger, which Phlex prevents plugins
  from replacing),
- **profiling and monitoring**: the framework runtime will provide these,
- **global-state wrappers** such as TFileService: pass the managing object explicitly,
- **shared read-only objects** such as geometry: in Phlex these are data products of a
  long-lived data layer,
- **conditions and database-derived data**: a dedicated algorithm fetches them into the
  appropriate data layer.
